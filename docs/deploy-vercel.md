# Wdrożenie na Vercel (plan Hobby)

Z jednego repo powstają dwa projekty Vercel: **API** (katalog `backend`, FastAPI na Pythonie 3.12,
preset FastAPI Vercela) i **panel** (katalog `web`, Next.js). Oba budują się z gałęzi `master`
jako produkcja i z każdego PR-a jako podgląd. Sekrety wpisuje się tylko w ustawieniach Vercela
i w Supabase; nigdy do repo ani do czatu.

## 0. Co jest w repo (nic do zrobienia)

- `backend/pyproject.toml` → `[tool.vercel] entrypoint = "api.main:app"`; wersja Pythona
  z `backend/.python-version`; zależności z `backend/uv.lock` (Vercel używa `uv`).
- `backend/vercel.json` → region `fra1` (Frankfurt; dobierz do regionu Supabase) i wykluczenie
  testów z paczki funkcji.
- `web/package.json` → `engines.node >= 24` (Vercel buduje na Node 24; lokalnie i w CI jest 26).

## 1. Supabase w chmurze (wymagane przed Vercelem)

1. https://supabase.com → New project. Region EU (np. Frankfurt), zapisz hasło bazy w menedżerze
   haseł.
2. Project Settings → API: skopiuj **Project URL**, **anon public** i **service_role** (sekret).
3. Migracje z repo, z katalogu głównego (CLI zapyta o hasło bazy):

   ```bash
   ./bin/supabase link --project-ref <ref-projektu>
   ```

   ```bash
   ./bin/supabase db push
   ```

4. SQL Editor → dozwolona domena logowania (ta sama, którą wpiszesz w `PANEL_ALLOWED_EMAIL_DOMAIN`):

   ```sql
   insert into public.panel_allowed_domains (domain) values ('citizengo.org');
   ```

5. Authentication → Users → **Add user** → *Create new user*: Twój e-mail z tej domeny, hasło,
   zaznacz *Auto Confirm User*. Panel loguje hasłem, nie ma rejestracji.

## 2. Projekt API na Vercelu

1. https://vercel.com/new → Import repo `Kuba862/social-media-campaigns-tool`.
2. **Project Name**: np. `wa-campaigns-api`. **Root Directory**: `backend` (Edit → wybierz
   katalog). **Framework Preset**: FastAPI (wykryty automatycznie).
3. **Environment Variables** (Production i Preview):

   | Nazwa | Wartość |
   |---|---|
   | `SUPABASE_URL` | Project URL z Supabase |
   | `SUPABASE_SERVICE_ROLE_KEY` | klucz service_role (Sensitive) |
   | `PANEL_ALLOWED_EMAIL_DOMAIN` | `citizengo.org` |
   | `WA_SEND_MODE` | `test` |
   | `WA_ALLOWED_TEST_RECIPIENTS` | numery testowe E.164 po przecinku, np. `+48600000001` |
   | `META_GRAPH_VERSION`, `META_WABA_ID`, `META_PHONE_NUMBER_ID`, `META_SYSTEM_USER_TOKEN`, `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN` | dopiero gdy będzie konto Meta; bez nich API działa w trybie szkiców |

4. **Deploy**. Po zbudowaniu sprawdź `https://<projekt-api>.vercel.app/healthz` →
   `{"status":"ok"}`. Zapisz ten adres: to `API_URL` panelu.

## 3. Projekt panelu na Vercelu

1. Ponownie https://vercel.com/new → to samo repo. **Project Name**: np. `wa-campaigns-panel`.
   **Root Directory**: `web`. **Framework Preset**: Next.js.
2. **Environment Variables** (Production i Preview); zmienne `NEXT_PUBLIC_*` są wbudowywane
   w czasie budowania, więc muszą być ustawione przed pierwszym deployem:

   | Nazwa | Wartość |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | Project URL z Supabase |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | klucz anon |
   | `PANEL_ALLOWED_EMAIL_DOMAIN` | `citizengo.org` |
   | `API_URL` | `https://<projekt-api>.vercel.app` (bez ukośnika na końcu) |

3. **Deploy**. Wejdź na `https://<projekt-panel>.vercel.app/login` i zaloguj się użytkownikiem
   z kroku 1.5. Strony Templates, Journeys, Messages i Sync powinny się otworzyć (puste).

## 4. Co dalej

- **Konto Meta**: pełne kroki (identyfikatory, token, webhook, pierwszy test szablonu) są
  w `docs/meta-setup.md`.
- **Webhook Mety**: w aplikacji Meta → WhatsApp → Configuration → Callback URL
  `https://<projekt-api>.vercel.app/webhooks/meta`, Verify token = wartość
  `META_WEBHOOK_VERIFY_TOKEN` z projektu API; subskrypcje `messages`
  i `message_template_status_update`.
- **Silnik przebiegów**: API nie łączy się z Temporalem; polecenia idą przez tabelę
  `dispatch_queue`, a wykonuje je worker na Cloud Run (`docs/deploy-cloud-run.md`). Bez workera
  przebiegi i synchronizacje czekają w kolejce jako `queued`.
- Każdy push na `master` wdraża oba projekty; PR daje adres podglądu (na planie Hobby podgląd
  jest chroniony logowaniem do Vercela, produkcja jest publiczna, więc webhook Mety celuje
  w produkcję).

## Rozwiązywanie problemów

- Build API nie wykrywa FastAPI → upewnij się, że Root Directory to `backend`, a nie katalog główny.
- Panel: "API is not reachable" → sprawdź `API_URL` i czy `/healthz` odpowiada; 401 po
  zalogowaniu → `PANEL_ALLOWED_EMAIL_DOMAIN` różni się między projektami albo brakuje domeny
  w `panel_allowed_domains`.
- Przebieg zostaje `queued` → worker na Cloud Run nie działa albo nie czyta tej bazy
  (`SUPABASE_URL` workera inne niż API).
