# Dziennik decyzji

Wpisy numerowane: data, decyzja, powód, konsekwencje. Pomysły poza zakresem PoC trafiają do
sekcji "Later" na końcu. Instrukcja implementacji i brief leżą poza repo, patrz `AGENTS.md`.

### 1. Nazwa repozytorium (2026-10-19)

Decyzja: repozytorium nazywa się `social-media-campaigns` (GitHub: `Kuba862/social-media-campaigns-tool`),
a nie `whatsapp-campaigns-poc` jak w sekcji 2 instrukcji.
Powód: wybór właściciela przy zakładaniu repo; nazwa nie wiąże projektu z jednym kanałem.
Układ wewnątrz repo pozostaje zgodny z instrukcją, z wyjątkiem wpisu 2.

### 2. Pakiety Pythona w `backend/` (2026-10-19)

Decyzja: `core/`, `api/`, `worker/`, `meta_client/`, `sync/`, `tests/` i `pyproject.toml` leżą
w `backend/`, nie w korzeniu repo. `web/` (Next.js), `supabase/`, `docs/` i `bin/` zostają w korzeniu.
Powód: jeden projekt uv (`pyproject.toml`, `uv.lock`, `.venv`) obejmuje cały backend, a panel
Next.js ma własny `package.json` obok, bez mieszania narzędzi dwóch ekosystemów w jednym katalogu.
Konsekwencje: komendy `uv run ...` uruchamiamy z `backend/`; importy są zakotwiczone w `backend/`
(`from core... import ...`, `pythonpath = ["."]` w pytest); ścieżki z sekcji 2 instrukcji czytamy
z prefiksem `backend/`.

### 3. mypy strict dla całego backendu (2026-10-19)

Decyzja: `[tool.mypy] strict = true` w `backend/pyproject.toml`, z pluginem `pydantic.mypy`,
dla wszystkich pakietów, nie tylko `core/`.
Powód: interpreter Journey i aktywności Temporal przenoszą dane między Meta, Temporal i Supabase;
błąd typu wykryty przy commicie jest tańszy niż w czasie działania. Strict od początku oszczędza
późniejsze sprzątanie.
Konsekwencje: flaga wchodzi z PR-em kroku 1 (gałąź `feature/core-tests`); kod bez adnotacji
nie przechodzi `uv run mypy .`.

### 4. `wait_for_reply.timeout` zamiast `duration` (2026-10-19)

Decyzja: węzeł `wait_for_reply` ma pole `timeout` (ISO 8601); węzeł `wait` zachowuje `duration`.
Powód: zgodność z JSON-em z sekcji 4.1 instrukcji. Definicja jest zapisywana w
`journey_versions.definition`, więc nazwa pola jest częścią kontraktu z edytorem i workerem.
Konsekwencje: zmiana w kroku 1 (`feature/core-tests`, commit c74df0c); do czasu merge
`master` ma jeszcze `duration`.

### 5. Węzeł `branch` bez krawędzi (2026-10-19)

Decyzja: `branch` nie ma wpisów w `edges`; cele rozgałęzienia są w `conditions[].next` i `else`
wewnątrz węzła. Walidacja odrzuca krawędzie wychodzące z `branch` i `end`, a lista następników
(`successors` w `validation.py`) dolicza cele z węzła.
Powód: tak definiuje to sekcja 4.1; warunek i cel trzymane razem są prostsze do interpretacji
w workflow niż krawędzie z etykietami.
Konsekwencje dla edytora (React Flow w `web/`): edytor musi mapować porty wyjściowe węzła
`branch` na `conditions[i].next` i `else` przy zapisie i odtwarzać je z tych pól przy wczytaniu,
zamiast zapisywać je jako `edges`. Porty `replied` i `timeout` węzła `wait_for_reply` pozostają
zwykłymi krawędziami z polem `port`.

## Later

- Wartości warunków `branch` są tylko tekstem: `Condition.if` to `dict[str, str]`, a
  `condition_matches` porównuje przez `==`. Rozgałęzienie po atrybucie bool (np.
  `attributes.interested: true` ustawionym przez `update_contact`) wymaga rozszerzenia typu
  `Condition.if` (np. o `bool` i `int`) oraz testów porównania typów.
