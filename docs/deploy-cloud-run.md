# Worker na Cloud Run (z wbudowanym Temporalem) i później Temporal Cloud

Worker Temporala to kontener z `backend/Dockerfile`, uruchamiany jako **Cloud Run worker pool**
(stała liczba instancji, bez adresu HTTP). W PoC kontener uruchamia też **własny serwer Temporala**
(`temporal server start-dev`, wpis 43), więc nic nie kupujesz. API na Vercelu nie łączy się
z Temporalem: zapisuje polecenia do tabeli `dispatch_queue` w Supabase, a worker je wykonuje
(wpisy 41 i 42). Przejście na Temporal Cloud to później zmiana konfiguracji workera, bez kodu.

## 0. Co jest w repo (nic do zrobienia)

- `backend/Dockerfile`: obraz z `uv` (Python 3.12, użytkownik bez roota) plus binarka CLI
  Temporala 1.9.1; `backend/docker-entrypoint.sh` startuje serwer dev, gdy `TEMPORAL_EMBEDDED=true`,
  i dopiero potem workera. `backend/.dockerignore`, `.gcloudignore`.
- `backend/worker/main.py` odpowiada 200 na `/healthz`, gdy ustawisz `PORT` (wariant Cloud Run
  *service*); worker pool tego nie potrzebuje.
- `cloudbuild.yaml`: build, push do Artifact Registry, `gcloud run worker-pools deploy`
  z jedną instancją (1 vCPU, 1 GiB), `TEMPORAL_EMBEDDED=true`, zmienne z substytucji
  i sekret `supabase-service-role-key` przez `--set-secrets`.
- `.github/workflows/deploy-worker.yml`: ta sama konfiguracja z GitHub Actions przez Workload
  Identity Federation (sekcja 3B).

Ograniczenie wbudowanego serwera: historie workflow żyją w instancji; restart albo nowa wersja
kasuje przebiegi w toku. Dyspozytor po starcie oznacza takie wiersze jako `failed`, więc panel
nie pokazuje ich jako `running`. Dla przebiegów trwających minuty to ryzyko pomijalne; dla
czekania dniami przejdź na Temporal Cloud (sekcja 5).

## 1. Google Cloud

1. https://console.cloud.google.com → **New project**, np. `wa-campaigns`, z rozliczeniami
   (worker pool z jedną instancją 1 vCPU/1 GiB to ok. 20–30 $ miesięcznie).
2. **APIs & Services → Enable**: Cloud Run Admin API, Cloud Build API, Artifact Registry API,
   Secret Manager API.
3. **Artifact Registry → Create repository**: nazwa `wa`, format Docker, region `europe-west1`
   (to `_REPO` i `_REGION` z `cloudbuild.yaml`).
4. **Secret Manager → Create secret**: `supabase-service-role-key` z kluczem service_role
   z Supabase (ten sam co w Vercelu). Później, gdy będą: `meta-system-user-token`,
   `sync-postgres-dsn`, `temporal-api-key`.
5. **IAM → Service accounts → Create**: `wa-worker`; nadaj mu rolę **Secret Manager Secret
   Accessor**.
6. **IAM**: konto, na którym działa Cloud Build (`<numer-projektu>-compute@developer.gserviceaccount.com`
   w nowych projektach albo `<numer-projektu>@cloudbuild.gserviceaccount.com` w starszych; numer
   projektu jest na Dashboardzie), dostaje role **Cloud Run Admin**, **Artifact Registry Writer**
   i **Service Account User**. W razie wątpliwości nadaj obu.

## 2. Supabase

Projekt w chmurze z migracjami już istnieje (`docs/deploy-vercel.md`). Migracje dodane po
pierwszym wdrożeniu wgrywasz tym samym `./bin/supabase db push`; worker potrzebuje tabeli
`dispatch_queue` (migracja `20261021220000_dispatch_queue.sql`).

## 3. Uruchamianie builda: trzy drogi

`cloudbuild.yaml` jest ten sam; różni się tylko to, kto go uruchamia. Substytucje:

| Zmienna | Wartość |
|---|---|
| `_SUPABASE_URL` | Project URL z Supabase (ten sam co w Vercelu) |
| `_WA_ALLOWED_TEST_RECIPIENTS` | Twoje numery testowe E.164 po przecinku |
| `_META_WABA_ID`, `_META_PHONE_NUMBER_ID` | później, z konta Meta |
| `_SECRETS` | zostaw domyślne; dopisz sekrety Mety i konektora, gdy istnieją |
| `_TEMPORAL_EMBEDDED`, `_TEMPORAL_ADDRESS`, `_TEMPORAL_NAMESPACE` | zostaw domyślne (wbudowany serwer); zmieniasz przy przejściu na Temporal Cloud |

### 3A. Z laptopa, bez podłączania repo (polecana na start)

```bash
gcloud auth login
```

```bash
gcloud config set project <id-projektu-gcp>
```

Z katalogu głównego repo, na aktualnym `master` (listę numerów oddzielaj przecinkami; `^|^` czyni
kreskę pionową separatorem substytucji):

```bash
gcloud builds submit --config cloudbuild.yaml --region europe-west1 --substitutions '^|^_SUPABASE_URL=https://<ref>.supabase.co|_WA_ALLOWED_TEST_RECIPIENTS=+48600000001' .
```

`.gcloudignore` wysyła tylko `backend/` i `cloudbuild.yaml`. Kolejne wdrożenia to to samo polecenie.

### 3B. GitHub Actions przez Workload Identity Federation (po pushu na master)

Repo jest prywatne, a GCP firmowe, więc zamiast podłączać repo do Cloud Build, GitHub loguje się
do GCP tokenem OIDC. Workflow `.github/workflows/deploy-worker.yml` uruchamia `gcloud builds submit`
jak w 3A. Konfiguracja w GCP (raz):

1. IAM → **Workload Identity Federation** → Create pool `github` → Add provider: OpenID Connect,
   nazwa `github`, issuer `https://token.actions.githubusercontent.com`, mapowanie
   `google.subject = assertion.sub`, `attribute.repository = assertion.repository`, warunek
   `attribute.repository == "Kuba862/social-media-campaigns-tool"`.
2. Service account `github-deploy` z rolami **Cloud Build Editor**, **Service Account User**,
   **Storage Object Creator** (bucket źródeł Cloud Build), **Viewer**.
3. Na `github-deploy` → Permissions → Grant access: principal
   `principalSet://iam.googleapis.com/projects/<numer-projektu>/locations/global/workloadIdentityPools/github/attribute.repository/Kuba862/social-media-campaigns-tool`
   z rolą **Workload Identity User**.
4. GitHub → repo → Settings → Secrets and variables → Actions → **Variables**:
   `DEPLOY_WORKER=true`, `GCP_PROJECT_ID`, `GCP_REGION=europe-west1`,
   `GCP_WORKLOAD_IDENTITY_PROVIDER=projects/<numer>/locations/global/workloadIdentityPools/github/providers/github`,
   `GCP_DEPLOY_SERVICE_ACCOUNT=github-deploy@<id-projektu>.iam.gserviceaccount.com`,
   `SUPABASE_URL`, `WA_ALLOWED_TEST_RECIPIENTS`, oraz `TEMPORAL_ADDRESS=127.0.0.1:7233`
   i `TEMPORAL_NAMESPACE=default` (wbudowany serwer).
5. Actions → **deploy-worker** → Run workflow.

Bez puli WIF: klucz JSON konta `github-deploy` w sekrecie `GOOGLE_CREDENTIALS` i `credentials_json`
w kroku `google-github-actions/auth@v3` (klucz długowieczny, traktuj jak hasło).

### 3C. Trigger Cloud Build z GitHuba (gdy repo da się podłączyć)

Cloud Build → Triggers → Connect repository → Create trigger: push na `^master$`, plik
`/cloudbuild.yaml`, region `europe-west1`, substytucje z tabeli.

## 4. Sprawdzenie

1. Cloud Run → Worker pools → `wa-worker` → **Logs**: kolejno `embedded Temporal dev server
   ready`, `worker ready on 127.0.0.1:7233, task queue wa-journeys`, `dispatcher ready`.
2. W panelu: Journeys → journey z samym `wait` (np. `prod smoke`) → Runs → Start dla numeru,
   który ma kontakt w bazie. Wiersz przechodzi `queued` → `running` → `completed` w kilka
   sekund; w Supabase tabela `dispatch_queue` ma wiersz `start_run` z `done_at`.
3. Sync → `fake` → Run now i Apply schedule: wiersz w Runs i stan "next …" w kolumnie Schedule.

Jeśli `gcloud` odmówi wdrożenia z powodu konta usługi, dopisz do kroku `deploy` w `cloudbuild.yaml`
`--service-account=wa-worker@<id-projektu>.iam.gserviceaccount.com`.

## 5. Przejście na Temporal Cloud (po akceptacji PoC)

1. https://cloud.temporal.io → namespace `wa-campaigns`, region EU, uwierzytelnianie **API key**;
   ze strony namespace skopiuj **Namespace** (`wa-campaigns.<id-konta>`) i **gRPC endpoint**
   (`wa-campaigns.<id-konta>.tmprl.cloud:7233`); **Generate API Key** (ważność do 2 lat).
2. Secret Manager: sekret `temporal-api-key` z kluczem.
3. Build z substytucjami `_TEMPORAL_EMBEDDED=false`, `_TEMPORAL_ADDRESS=<endpoint>`,
   `_TEMPORAL_NAMESPACE=<namespace>` i `_SECRETS` rozszerzonym o
   `,TEMPORAL_API_KEY=temporal-api-key:latest`. Nic w API ani w panelu się nie zmienia.
4. Przebiegi w toku na wbudowanym serwerze przepadają przy przełączeniu (dyspozytor oznaczy je
   `failed`); zrób to w przerwie między kampaniami.

## Rozwiązywanie problemów

- Deploy pada z `Permission denied on secret ... for Revision service account ...-compute@`: pool
  startuje na domyślnym koncie zamiast `wa-worker`; `cloudbuild.yaml` przekazuje
  `--service-account=${_WORKER_SA}@<projekt>.iam.gserviceaccount.com` (od 2026-10-21).
- `the --mount option requires BuildKit` w kroku `build`: krok dockera w `cloudbuild.yaml` musi mieć
  `env: ["DOCKER_BUILDKIT=1"]` (jest od 2026-10-21); `Dockerfile` używa `RUN --mount`, `COPY --chmod`
  i `ARG TARGETARCH`, które działają tylko z BuildKitem.
- Build pada na `push`: brak roli Artifact Registry Writer dla konta Cloud Build.
- Deploy pada na sekretach: sekret nie istnieje albo `wa-worker` nie ma roli Secret Accessor.
- Log `embedded Temporal did not start`: za mało pamięci w instancji; zostaw 1 GiB.
- Przebiegi zostają `queued`: worker nie działa albo ma inne `SUPABASE_URL` niż API.
- Przebiegi `failed` zaraz po wdrożeniu: to sprzątanie po restarcie wbudowanego serwera;
  w toku były przebiegi sprzed nowej wersji.
