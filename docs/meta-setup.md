# Meta: WABA, numer, token, webhook i pierwszy test szablonu

Bez zmiennych `META_*` API działa w trybie szkiców (wpis 14 w `docs/decisions.md`), a webhook
odpowiada 503 (wpis 17). Ten runbook podłącza prawdziwe konto Meta i prowadzi przez test
kryterium 1 z briefu: szablon utworzony w panelu trafia do Meta, a jego status wraca.

## 0. Co jest w kodzie (nic do zrobienia)

- `meta_client` mówi do Graph API `https://graph.facebook.com/<META_GRAPH_VERSION>`
  (domyślnie `v24.0`): `POST /<WABA_ID>/message_templates` (zgłoszenie szablonu),
  `GET /<WABA_ID>/message_templates?name=…&language=…` (status), `POST /<PHONE_NUMBER_ID>/messages`
  (wysyłka szablonu).
- `GET/POST /webhooks/meta`: uścisk dłoni z `META_WEBHOOK_VERIFY_TOKEN`, podpis
  `X-Hub-Signature-256` liczony z `META_APP_SECRET`; obsługiwane pola
  `message_template_status_update` (werdykty szablonów) i `messages` (statusy dostarczenia
  i wiadomości przychodzące). Bez obu sekretów trasa odpowiada 503, przy złym podpisie 401.
- Bezpiecznik wysyłki: `WA_SEND_MODE=test` i `WA_ALLOWED_TEST_RECIPIENTS` (numery E.164 po
  przecinku). PoC nigdy nie ustawia `live`.
- Kto czego używa:

  | Zmienna | API (Vercel) | Worker (Cloud Run) |
  |---|---|---|
  | `META_GRAPH_VERSION`, `META_WABA_ID`, `META_PHONE_NUMBER_ID` | tak | tak (substytucje builda) |
  | `META_SYSTEM_USER_TOKEN` | tak (Sensitive) | tak (sekret `meta-system-user-token`) |
  | `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN` | tak (Sensitive) | nie |
  | `WA_SEND_MODE`, `WA_ALLOWED_TEST_RECIPIENTS` | tak | tak |

## 1. Czego potrzebujesz w Meta

1. **Business Portfolio** (business.facebook.com) z kontem **WABA** i numerem, który działa
   w WhatsApp. Dla samego zgłaszania szablonów weryfikacja firmy nie jest potrzebna; jest
   potrzebna przed wysyłką na większą skalę. Dla wysyłki z prawdziwego numeru WABA musi mieć
   **metodę płatności** (Business settings → WhatsApp accounts → Payment methods).
2. **Aplikacja Meta** typu Business z produktem WhatsApp, przypięta do tego samego portfolio:
   developers.facebook.com → My Apps → Create App → Business → dodaj produkt WhatsApp. Jeśli
   aplikacja już istnieje, sprawdź w App Dashboard → WhatsApp → API Setup, że widzi Twoje
   WABA i numer.
3. Z **App Dashboard → WhatsApp → API Setup** spisz:
   - **WhatsApp Business Account ID** → `META_WABA_ID`,
   - **Phone number ID** numeru, z którego wysyłasz → `META_PHONE_NUMBER_ID`
     (to identyfikator, nie numer telefonu).
4. **Trwały token**: Business settings → Users → System users → Add (rola Admin) → Assign
   assets: aplikacja (Full control) i konto WhatsApp (Full control) → Generate token → wybierz
   aplikację, Expiration **Never**, uprawnienia `whatsapp_business_management`
   i `whatsapp_business_messaging`. Skopiuj od razu, Meta pokazuje go raz → `META_SYSTEM_USER_TOKEN`.
   Tymczasowy token z API Setup działa 24 godziny; nadaje się na pierwszą próbę, nie na dłużej.
5. **App Secret**: App Dashboard → App settings → Basic → App secret → Show → `META_APP_SECRET`.
6. **Verify token**: dowolny własny ciąg, np. `openssl rand -hex 24` → `META_WEBHOOK_VERIFY_TOKEN`.

Żadna z tych wartości nie trafia do repo ani do czatu.

## 2. API na Vercelu

1. Projekt API → Settings → Environment Variables (Production): `META_GRAPH_VERSION=v24.0`,
   `META_WABA_ID`, `META_PHONE_NUMBER_ID`, `META_SYSTEM_USER_TOKEN` (Sensitive),
   `META_APP_SECRET` (Sensitive), `META_WEBHOOK_VERIFY_TOKEN` (Sensitive), `WA_SEND_MODE=test`,
   `WA_ALLOWED_TEST_RECIPIENTS` z numerami, na które wolno wysyłać.
2. **Redeploy** (Deployments → ostatni → Redeploy): zmiana zmiennych nie wdraża się sama.
3. Sprawdź `https://<projekt-api>.vercel.app/healthz` → `{"status":"ok"}` i
   `https://<projekt-api>.vercel.app/webhooks/meta?hub.mode=subscribe&hub.verify_token=zly&hub.challenge=1`
   → 403 (a nie 503): sekrety są wczytane.

## 3. Pierwszy test: szablon do Meta (kryterium 1)

1. Panel → Templates → New draft: nazwa małymi literami i podkreśleniami (np.
   `poc_powitanie_1`), język `pl`, kategoria **UTILITY** (najszybsza akceptacja; MARKETING
   dla treści promocyjnych), treść z co najwyżej jedną zmienną na początek, np.
   `Cześć {{1}}, dziękujemy za wsparcie. Odpowiedz TAK, jeśli chcesz dostawać wiadomości.`,
   przykładowa wartość `Jakub`, szybka odpowiedź `TAK`. Save draft.
2. **Submit**. Oczekiwany wynik w tabeli: status `PENDING` i wypełniona kolumna Meta id. To
   dowód, że `POST /<WABA_ID>/message_templates` przeszedł. Błędy Mety wracają w czerwonym
   komunikacie nad tabelą (np. zła kategoria, zmienna na końcu treści, brak przykładu).
3. Werdykt: od minut do kilku godzin. Przed podłączeniem webhooka kliknij **Sync** przy
   szablonie: API odpyta Meta i zapisze `APPROVED` albo `REJECTED` z powodem.
4. Kontrola po stronie Meta: Business settings → WhatsApp Manager → Message templates: szablon
   widnieje z tym samym statusem.

## 4. Webhook (statusy same wracają)

1. App Dashboard → WhatsApp → Configuration → Webhook → Edit: Callback URL
   `https://<projekt-api>.vercel.app/webhooks/meta`, Verify token = `META_WEBHOOK_VERIFY_TOKEN`
   → Verify and save. API musi już być wdrożone z sekretami z sekcji 2.
2. Webhook fields → Manage → subskrybuj `message_template_status_update` i `messages`.
3. Sprawdź, że aplikacja jest zapisana na zdarzenia Twojego WABA:
   `GET https://graph.facebook.com/v24.0/<WABA_ID>/subscribed_apps` z nagłówkiem
   `Authorization: Bearer <token>` ma zwrócić aplikację; jeśli lista jest pusta, wyślij `POST`
   na ten sam adres.
4. Test: zgłoś drugi szablon i nie klikaj Sync. Status w panelu ma zmienić się sam, gdy Meta
   wyda werdykt. W logach funkcji na Vercelu widać `POST /webhooks/meta` z 200.

## 5. Wysyłka: worker na Cloud Run

Szablony i webhook obsługuje API. Wysyłkę wiadomości w przebiegach robi worker, więc on też
potrzebuje tokenu i identyfikatorów:

```bash
printf '%s' "$(pbpaste)" | gcloud secrets create meta-system-user-token --replication-policy=automatic --data-file=-
```

```bash
gcloud secrets add-iam-policy-binding meta-system-user-token --member="serviceAccount:wa-worker@$(gcloud config get-value project).iam.gserviceaccount.com" --role=roles/secretmanager.secretAccessor
```

Przebudowa z katalogu głównego repo (identyfikatory i numery wstaw swoje):

```bash
gcloud builds submit --config cloudbuild.yaml --region europe-west1 --substitutions '^|^_SUPABASE_URL=https://<ref>.supabase.co|_WA_ALLOWED_TEST_RECIPIENTS=+48600000001|_META_WABA_ID=<waba-id>|_META_PHONE_NUMBER_ID=<phone-number-id>|_SECRETS=SUPABASE_SERVICE_ROLE_KEY=supabase-service-role-key:latest,META_SYSTEM_USER_TOKEN=meta-system-user-token:latest' .
```

Test wysyłki pojedynczej wiadomości (kryterium 7) idzie przez API: Templates → przy
zatwierdzonym szablonie wpisz numer z `WA_ALLOWED_TEST_RECIPIENTS` → Send test. Strona Messages
pokazuje `sent`, a po webhookach `delivered` i `read`.

## 6. Kontakty do przebiegów

Formularz startu przebiegu nie tworzy kontaktów; tworzy je synchronizacja. Konektor `fake` daje
tylko trzy zmyślone numery, więc prawdziwy numer testowy ze zgodą `opted_in` wchodzi przez
konektor `postgres`: tabela źródłowa jak w `backend/sync/connectors/postgres_demo.sql`
(schemat `legacy`, kolumny `phone`, `first_name`, `country`, `consent`, `updated_at`), DSN
w sekrecie `sync-postgres-dsn` (dopisany do `_SECRETS`), konektor zarejestrowany na stronie
Sync z konfiguracją `{"table": "legacy.contacts", "default_region": "PL", "columns": {"external_ref": "id", "locale": null}}`.

## Rozwiązywanie problemów

- `GET /webhooks/meta` → 503: brak `META_APP_SECRET` albo `META_WEBHOOK_VERIFY_TOKEN` w Vercelu
  lub brak redeployu po ich dodaniu.
- Meta nie weryfikuje webhooka: inny verify token w Meta i w Vercelu.
- Submit → „Meta is not configured”: brak `META_SYSTEM_USER_TOKEN` (albo brak redeployu).
- Submit → błąd 190 / „Invalid OAuth access token”: token wygasł (tymczasowy) albo System User
  nie ma przypisanej aplikacji i WABA.
- Submit → błąd 100 z opisem pola: nazwa z wielkimi literami, zmienna na początku lub końcu
  treści, brak przykładowej wartości, więcej niż trzy szybkie odpowiedzi.
- `REJECTED` z powodem w panelu: najczęściej kategoria (treść promocyjna w UTILITY). Popraw
  treść lub kategorię i zgłoś pod nową nazwą.
- Statusy nie wracają mimo webhooka: brak subskrypcji pól albo aplikacja niezapisana na WABA
  (sekcja 4.3); 401 w logach Vercela to zły App Secret.
- Send test → „recipient not allowed”: numeru nie ma w `WA_ALLOWED_TEST_RECIPIENTS` (API) lub
  w substytucji builda (worker).
- Wysyłka z prawdziwego numeru → błąd 131042: brak metody płatności w WABA.
