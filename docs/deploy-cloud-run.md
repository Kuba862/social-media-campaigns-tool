# Worker na Cloud Run i Temporal Cloud

Worker Temporala to kontener z `backend/Dockerfile`, uruchamiany jako **Cloud Run worker pool**
(stała liczba instancji, bez adresu HTTP; to wariant "worker pool preferred" z sekcji 1
instrukcji). Cloud Build buduje obraz i wdraża go według `cloudbuild.yaml` w katalogu głównym
repo; build można uruchomić z laptopa, z GitHub Actions albo z triggera (sekcja 3). Sekrety
mieszkają w Secret Managerze, reszta konfiguracji w substytucjach.

## 0. Co jest w repo (nic do zrobienia)

- `backend/Dockerfile` (uv z lockfile, Python 3.12, użytkownik bez roota),
  `backend/.dockerignore`.
- `backend/worker/main.py` odpowiada 200 na `/healthz`, gdy ustawisz `PORT`; worker pool tego
  nie potrzebuje, ale dzięki temu ten sam obraz zadziała też jako Cloud Run *service*
  z `--min-instances=1 --no-cpu-throttling`.
- `cloudbuild.yaml`: build, push do Artifact Registry, `gcloud run worker-pools deploy`
  z `--instances=1`, zmiennymi z substytucji i sekretami przez `--set-secrets`; obraz tagowany
  `$BUILD_ID`, więc działa z triggera, z `gcloud builds submit` i z GitHub Actions.
- `.gcloudignore`: `gcloud builds submit .` wysyła tylko `backend/` i `cloudbuild.yaml`.
- `.github/workflows/deploy-worker.yml`: wdrożenie z GitHub Actions przez Workload Identity
  Federation, włączane zmienną repo `DEPLOY_WORKER=true` (sekcja 3B).

## 1. Temporal Cloud

1. https://cloud.temporal.io → załóż konto (jest darmowy próg) i **Create Namespace**:
   nazwa np. `wa-campaigns`, region **Europe (eu-central-1, Frankfurt)**, uwierzytelnianie
   **API key** (nie mTLS; po utworzeniu nie da się tego zmienić).
2. Ze strony namespace skopiuj dwie wartości:
   - **Namespace**: `wa-campaigns.<id-konta>` (format `<namespace>.<account_id>`),
   - **gRPC endpoint**: `wa-campaigns.<id-konta>.tmprl.cloud:7233`.
3. Klucz API: na stronie namespace **Generate API Key** (klucz z uprawnieniami admina tego
   namespace, maksymalna ważność 2 lata) albo Profile → API Keys → Create API key. Klucz
   pokazuje się tylko raz; wklej go od razu do Secret Managera (krok 2.4) i do Vercela
   (krok 4), nigdzie indziej.
4. Zapisz termin ważności klucza w kalendarzu: Temporal przypomina 30, 20 i 10 dni przed.

## 2. Google Cloud

1. https://console.cloud.google.com → **New project**, np. `wa-campaigns`. Włącz rozliczenia
   (Cloud Run worker pool z jedną instancją kosztuje kilka dolarów miesięcznie).
2. Włącz API (APIs & Services → Enable): **Cloud Run Admin API**, **Cloud Build API**,
   **Artifact Registry API**, **Secret Manager API**.
3. Artifact Registry → **Create repository**: nazwa `wa`, format Docker, region
   `europe-west1` (to są wartości `_REPO` i `_REGION` w `cloudbuild.yaml`; jeśli wybierzesz
   inne, zmienisz je w triggerze).
4. Secret Manager → **Create secret**, po jednym na wartość:

   | Nazwa sekretu | Wartość |
   |---|---|
   | `temporal-api-key` | klucz API z kroku 1.3 |
   | `supabase-service-role-key` | klucz service_role z Supabase |
   | `meta-system-user-token` | później, gdy będzie konto Meta |
   | `sync-postgres-dsn` | później, gdy będzie źródło dla konektora Postgres |

5. IAM → **Service accounts** → Create: `wa-worker` (konto, na którym działa worker). Nadaj
   mu rolę **Secret Manager Secret Accessor** (IAM → Grant access).
6. Cloud Build potrzebuje prawa do wdrażania: IAM → znajdź konto usługi Cloud Build
   (`<numer-projektu>@cloudbuild.gserviceaccount.com` albo `<numer>-compute@developer.gserviceaccount.com`,
   zależnie od ustawień) i dodaj role **Cloud Run Admin**, **Artifact Registry Writer**,
   **Service Account User** (żeby mógł wdrażać jako `wa-worker`).

## 3. Uruchamianie builda: trzy drogi

`cloudbuild.yaml` jest ten sam w każdej z nich; różni się tylko to, kto go uruchamia. Wartości
substytucji są wspólne:

| Zmienna | Wartość |
|---|---|
| `_TEMPORAL_ADDRESS` | `wa-campaigns.<id-konta>.tmprl.cloud:7233` |
| `_TEMPORAL_NAMESPACE` | `wa-campaigns.<id-konta>` |
| `_SUPABASE_URL` | Project URL z Supabase |
| `_WA_ALLOWED_TEST_RECIPIENTS` | numery testowe E.164 po przecinku |
| `_META_WABA_ID`, `_META_PHONE_NUMBER_ID` | później, z konta Meta |
| `_SECRETS` | zostaw domyślne; dopisz `,META_SYSTEM_USER_TOKEN=meta-system-user-token:latest,SYNC_POSTGRES_DSN=sync-postgres-dsn:latest`, gdy te sekrety istnieją |

### 3A. Z laptopa, bez podłączania repo (najprostsza, działa od razu)

`gcloud builds submit` wysyła źródła z Twojego checkoutu do Cloud Build (plik `.gcloudignore`
ogranicza to do `backend/` i `cloudbuild.yaml`), a Cloud Build buduje obraz i wdraża worker pool.
Wymaga zainstalowanego `gcloud` (Google Cloud SDK jest na tej maszynie) i jednorazowego logowania:

```bash
gcloud auth login
```

```bash
gcloud config set project <id-projektu-gcp>
```

Z katalogu głównego repo, na gałęzi `master` po `git pull` (listę numerów oddzielaj znakiem `|`,
bo `^|^` zmienia separator na kreskę pionową):

```bash
gcloud builds submit --config cloudbuild.yaml --region europe-west1 --substitutions '^|^_TEMPORAL_ADDRESS=wa-campaigns.<id-konta>.tmprl.cloud:7233|_TEMPORAL_NAMESPACE=wa-campaigns.<id-konta>|_SUPABASE_URL=https://<ref>.supabase.co|_WA_ALLOWED_TEST_RECIPIENTS=+48600000001,+48600000002' .
```

Każde kolejne wdrożenie to to samo polecenie. Wada: ktoś musi je uruchomić ręcznie.

### 3B. GitHub Actions przez Workload Identity Federation (automatycznie po pushu)

Repo jest prywatne, a konto GCP firmowe, więc zamiast podłączać repo do Cloud Build, GitHub
loguje się do GCP tokenem OIDC (bez kluczy JSON). Workflow `.github/workflows/deploy-worker.yml`
jest w repo i uruchamia dokładnie `gcloud builds submit` jak w 3A. Konfiguracja w GCP (raz):

1. IAM → **Workload Identity Federation** → Create pool: nazwa `github`. W puli **Add provider**:
   OpenID Connect, nazwa `github`, issuer `https://token.actions.githubusercontent.com`,
   mapowanie atrybutów `google.subject = assertion.sub`,
   `attribute.repository = assertion.repository`, warunek
   `attribute.repository == "Kuba862/social-media-campaigns-tool"`.
2. Service accounts → Create: `github-deploy`. Role: **Cloud Build Editor**,
   **Service Account User** (na `wa-worker` i na koncie Cloud Build), **Storage Admin** albo
   **Storage Object Creator** na bucket źródeł Cloud Build (`gcloud builds submit` wrzuca tam
   archiwum), **Viewer** na projekt.
3. Na koncie `github-deploy` → **Permissions → Grant access**: principal
   `principalSet://iam.googleapis.com/projects/<numer-projektu>/locations/global/workloadIdentityPools/github/attribute.repository/Kuba862/social-media-campaigns-tool`
   z rolą **Workload Identity User**.
4. W GitHubie: repo → Settings → Secrets and variables → Actions → **Variables** (nie Secrets,
   bo żadna z nich nie jest tajna):

   | Zmienna repo | Wartość |
   |---|---|
   | `DEPLOY_WORKER` | `true` (włącza workflow) |
   | `GCP_PROJECT_ID` | id projektu |
   | `GCP_REGION` | `europe-west1` |
   | `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/<numer-projektu>/locations/global/workloadIdentityPools/github/providers/github` |
   | `GCP_DEPLOY_SERVICE_ACCOUNT` | `github-deploy@<id-projektu>.iam.gserviceaccount.com` |
   | `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`, `SUPABASE_URL`, `WA_ALLOWED_TEST_RECIPIENTS` | jak w tabeli substytucji |

5. Actions → **deploy-worker** → Run workflow (albo push na `master` ze zmianą w `backend/`).

Jeśli polityka firmowego GCP nie pozwala na pulę Workload Identity, zostaje wariant 3A albo
klucz JSON konta `github-deploy` w sekrecie GitHuba `GOOGLE_CREDENTIALS` i krok
`google-github-actions/auth@v3` z `credentials_json` zamiast WIF (klucz jest długowieczny,
traktuj go jak hasło).

### 3C. Trigger Cloud Build z GitHuba (gdy repo da się podłączyć)

Cloud Build → Triggers → Connect repository (GitHub) → Create trigger: push na `^master$`, plik
`/cloudbuild.yaml`, region `europe-west1`, substytucje z tabeli wyżej. Pierwsze uruchomienie
przyciskiem **Run**.

### Po pierwszym wdrożeniu (każda droga)

Cloud Run → Worker pools → `wa-worker` → **Logs**: po starcie ma być linia
`worker ready on wa-campaigns.<id-konta>.tmprl.cloud:7233, task queue wa-journeys`. Jeśli
`gcloud` odmówi wdrożenia z powodu konta usługi, dopisz do kroku `deploy` w `cloudbuild.yaml`
`--service-account=wa-worker@<id-projektu>.iam.gserviceaccount.com`.

## 4. Spięcie z API na Vercelu

W projekcie API na Vercelu dodaj zmienne `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`
i `TEMPORAL_API_KEY` (te same wartości co wyżej; klucz jako Sensitive) i zrób **Redeploy**.
Od tej chwili start przebiegów, Run now i Apply schedule w panelu działają: API startuje
workflow w Temporal Cloud, a worker na Cloud Run go wykonuje.

Sprawdzenie end-to-end: w panelu Journeys → journey `prod smoke` → Runs → Start dla numeru,
który ma kontakt w bazie (bez Mety wyślij najpierw journey bez `send_template`, np. z samym
`wait`); przebieg powinien przejść do `completed`, a w Temporal Cloud UI pojawi się workflow
`journey:<id>:contact:<id>`.

## Rozwiązywanie problemów

- Build pada na `push`: brak roli Artifact Registry Writer dla konta Cloud Build.
- Deploy pada na sekretach: sekret nie istnieje albo `wa-worker` nie ma roli Secret Accessor.
- Worker loguje `Failed client connect`: zły `_TEMPORAL_ADDRESS`/`_TEMPORAL_NAMESPACE` albo
  klucz z innego namespace; sprawdź, że namespace ma uwierzytelnianie API key.
- Worker startuje, ale przebiegi wiszą jako `running`: API na Vercelu i worker wskazują
  różne namespace, albo kolejka inna niż `wa-journeys`.
