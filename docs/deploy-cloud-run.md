# Worker na Cloud Run i Temporal Cloud

Worker Temporala to kontener z `backend/Dockerfile`, uruchamiany jako **Cloud Run worker pool**
(stała liczba instancji, bez adresu HTTP; to wariant "worker pool preferred" z sekcji 1
instrukcji). Cloud Build buduje obraz z każdego pusha na `master` i wdraża go według
`cloudbuild.yaml` w katalogu głównym repo. Sekrety mieszkają w Secret Managerze, reszta
konfiguracji w substytucjach triggera.

## 0. Co jest w repo (nic do zrobienia)

- `backend/Dockerfile` (uv z lockfile, Python 3.12, użytkownik bez roota),
  `backend/.dockerignore`.
- `backend/worker/main.py` odpowiada 200 na `/healthz`, gdy ustawisz `PORT`; worker pool tego
  nie potrzebuje, ale dzięki temu ten sam obraz zadziała też jako Cloud Run *service*
  z `--min-instances=1 --no-cpu-throttling`.
- `cloudbuild.yaml`: build, push do Artifact Registry, `gcloud run worker-pools deploy`
  z `--instances=1`, zmiennymi z substytucji i sekretami przez `--set-secrets`.

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

## 3. Cloud Build: trigger z GitHuba

1. Cloud Build → Triggers → **Connect repository** (GitHub, aplikacja Cloud Build) → wybierz
   `Kuba862/social-media-campaigns-tool`.
2. **Create trigger**: nazwa `worker-master`, event *Push to a branch*, branch `^master$`,
   configuration *Cloud Build configuration file*, lokalizacja `/cloudbuild.yaml`, region
   `europe-west1`.
3. **Substitution variables** w triggerze (nadpisują wartości domyślne z pliku):

   | Zmienna | Wartość |
   |---|---|
   | `_TEMPORAL_ADDRESS` | `wa-campaigns.<id-konta>.tmprl.cloud:7233` |
   | `_TEMPORAL_NAMESPACE` | `wa-campaigns.<id-konta>` |
   | `_SUPABASE_URL` | Project URL z Supabase |
   | `_WA_ALLOWED_TEST_RECIPIENTS` | numery testowe E.164 po przecinku |
   | `_META_WABA_ID`, `_META_PHONE_NUMBER_ID` | później, z konta Meta |
   | `_SECRETS` | zostaw domyślne; dopisz `,META_SYSTEM_USER_TOKEN=meta-system-user-token:latest,SYNC_POSTGRES_DSN=sync-postgres-dsn:latest`, gdy te sekrety istnieją |

4. Pierwsze wdrożenie uruchom ręcznie przyciskiem **Run** przy triggerze (gałąź `master`).
   Krok `deploy` tworzy worker pool `wa-worker` przy pierwszym uruchomieniu; przy kolejnych
   podmienia obraz. Jeśli `gcloud` zapyta o konto usługi, w kroku deploy dopisz
   `--service-account=wa-worker@<projekt>.iam.gserviceaccount.com` (albo dodaj to do
   `cloudbuild.yaml`).
5. Cloud Run → Worker pools → `wa-worker` → **Logs**: po starcie ma być linia
   `worker ready on wa-campaigns.<id-konta>.tmprl.cloud:7233, task queue wa-journeys`.

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
