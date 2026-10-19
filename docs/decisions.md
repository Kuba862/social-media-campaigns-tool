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

### 6. Odstępstwa w pierwszej migracji (2026-10-19)

Decyzja: trzy drobne różnice względem tabeli z sekcji 3 instrukcji w
`supabase/migrations/20261019105537_initial_tables.sql`: `journey_runs.journey_id` jest zdublowane
z `journey_versions`, `templates.status` ma lokalny stan `DRAFT` przed `PENDING`, a
`message_events.message_id` dopuszcza null.
Powód: reguła "jeden aktywny run na (journey, kontakt)" wymaga indeksu częściowego na kolumnach
tej samej tabeli; szablon utworzony w panelu istnieje, zanim Meta nada mu status; webhook statusu
może przyjść dla `wamid`, którego nie mamy, a tabela zdarzeń jest append-only i nie powinna go gubić.
Konsekwencje: API ustawia `journey_id` przy starcie runu na podstawie wersji; `DRAFT` nie jest
statusem Meta i nie trafia do synchronizacji; zdarzenia bez `message_id` dopasowujemy później po `wamid`.

### 7. Polityki RLS i strażnicy w bazie (2026-10-19)

Decyzja: lista dozwolonych domen panelu to tabela `panel_allowed_domains`, sprawdzana przez funkcję
`is_panel_user()` (`security definer`). Lokalnie wypełnia ją `supabase/seed.sql` wartością `example.org`;
na projekcie hostowanym prawdziwą domenę wstawia się raz, ręcznie. Service role nie ma polityk, bo omija
RLS. Reguły "tylko insert" dla `consents` i `message_events` oraz niezmienność opublikowanej
`journey_versions` egzekwują triggery, nie uprawnienia.
Powód: domena w tabeli jest widoczna i zmienialna bez nowej migracji, a ta sama lista posłuży panelowi
(krok 7). Triggery działają także dla service role i superusera, więc błąd w API nie nadpisze śladu
audytowego.
Konsekwencje: osoba spoza listy po zalogowaniu widzi puste tabele, nie błąd; API tworzy nową wersję
journey zamiast edytować opublikowaną; zmiana zgody to insert nowego wiersza.

### 8. Weryfikacja tokenu przez Supabase Auth, domena także w API (2026-10-19)

Decyzja: API nie sprawdza podpisu JWT samo. `api/auth.py` wysyła token do
`GET {SUPABASE_URL}/auth/v1/user` z kluczem service role jako `apikey` i przyjmuje odpowiedź Supabase.
Dodatkowo API sprawdza domenę e-mail z `PANEL_ALLOWED_EMAIL_DOMAIN` (403), choć sekcja 10 instrukcji
przypisuje tę zmienną tylko do web.
Powód: service role omija RLS, więc sama poprawność tokenu nie wystarcza; osoba spoza listy mogłaby
wywołać API. Lokalny CLI 2.121 i projekty hostowane podpisują tokeny ES256 z JWKS, więc lokalna
weryfikacja też byłaby jedną ścieżką, ale wymaga pobierania i cache'owania kluczy; pytanie Supabase
to mniej kodu w PoC.
Konsekwencje: jedno wywołanie HTTP do Supabase na każde chronione żądanie; brak Supabase to 503,
nie 500. Lista domen istnieje w dwóch miejscach (tabela `panel_allowed_domains` dla RLS i env dla
API) i musi być zgodna.

### 9. Python przypięty do 3.12, worker z domyślnymi ustawieniami lokalnymi (2026-10-19)

Decyzja: `backend/.python-version` ustawia 3.12 dla uv; `requires-python` zostaje `>=3.12`. Worker
czyta `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE` i `TEMPORAL_API_KEY` z domyślnymi wartościami
lokalnego serwera deweloperskiego (`localhost:7233`, `default`, brak klucza); pusty klucz oznacza
połączenie bez TLS. Kolejka zadań nazywa się `wa-journeys`, jak w sekcji 2 instrukcji.
Powód: bez pliku uv brał najnowszego zainstalowanego Pythona (3.14), a obrazy na Vercel i Cloud Run
oraz natywne koła SDK (temporalio) są pewniejsze na 3.12; jeden interpreter lokalnie i w chmurze.
Domyślne ustawienia pozwalają uruchomić workera komendą bez `.env`, API celowo ich nie ma, bo tam
brak klucza Supabase jest błędem.
Konsekwencje: Temporal Cloud wymaga ustawienia wszystkich trzech zmiennych; testy workflow idą na
serwerze testowym SDK z przeskakiwaniem czasu, pobieranym przy pierwszym uruchomieniu.

## Later

- Wartości warunków `branch` są tylko tekstem: `Condition.if` to `dict[str, str]`, a
  `condition_matches` porównuje przez `==`. Rozgałęzienie po atrybucie bool (np.
  `attributes.interested: true` ustawionym przez `update_contact`) wymaga rozszerzenia typu
  `Condition.if` (np. o `bool` i `int`) oraz testów porównania typów.
- Weryfikacja JWT lokalnie przez JWKS z cache (PyJWT, `PyJWKClient`) zamiast wywołania
  `/auth/v1/user`; API czyta listę domen z `panel_allowed_domains` zamiast z env, żeby było jedno
  źródło prawdy.
