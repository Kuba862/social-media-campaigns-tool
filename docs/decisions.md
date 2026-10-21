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

### 10. CI w GitHub Actions na push do mastera i na PR (2026-10-19)

Decyzja: jeden workflow `.github/workflows/ci.yml` z jednym jobem `backend`: `uv sync --locked`,
`ruff check`, `ruff format --check`, `mypy`, `pytest`, czyli to samo co lokalnie z AGENTS.md.
Uruchamia się na push do `master` i na każdy pull request; kolejny push na tę samą gałąź anuluje
poprzedni bieg. Bez sekretów: testy nie dotykają Supabase ani Temporal Cloud.
Powód: te same cztery komendy w CI i lokalnie oznaczają, że zielone CI znaczy dokładnie to, co
zielony terminal; `--locked` wyłapuje `uv.lock` niezgodny z `pyproject.toml`.
Konsekwencje: test workera pobiera serwer testowy SDK na maszynę GitHuba przy każdym biegu
(ok. 10 s); jeśli zacznie przeszkadzać, dojdzie cache. Wymaganie zielonego checku `backend`
przed merge to ustawienie gałęzi w GitHubie, które włącza właściciel.

### 11. Panel Next.js 16 z sesją w ciasteczkach i domeną sprawdzaną przed logowaniem (2026-10-20)

Decyzja: `web/` to Next.js 16 (App Router, TypeScript strict, bez Tailwinda i React Compilera),
wygenerowany flagą `--empty`. Sesję Supabase trzyma `@supabase/ssr` w ciasteczkach; `proxy.ts`
(następca `middleware.ts` w Next 16) odświeża ją przy każdym żądaniu, przekierowuje niezalogowanych
na `/login` i wylogowuje zalogowanych spoza domeny. Logowanie e-mailem i hasłem przez akcję
serwerową, która sprawdza `PANEL_ALLOWED_EMAIL_DOMAIN` przed wywołaniem Supabase; zmienna jest
bez prefiksu `NEXT_PUBLIC_`, bo czyta ją tylko serwer. Nazwy zmiennych panelu są w `web/.env.example`.
Powód: sesja w ciasteczkach pozwala komponentom serwerowym i akcjom czytać tego samego użytkownika,
co przeglądarka, bez własnego API; sprawdzenie domeny przed logowaniem nie zakłada sesji osobie
spoza listy. Hasło zamiast magic linka, bo lokalnie nie ma poczty, a PoC testuje panel, nie Auth.
Konsekwencje: trzy miejsca pilnują domeny (RLS w bazie, API, panel) z dwóch źródeł: tabela i env.
Lint to goły `eslint`, bo Next 16 usunął `next lint`; typy sprawdza skrypt `typecheck`
(`tsc --noEmit`). Testy Vitest i Playwright oraz job CI dla `web/` to krok 7b.

### 12. Narzędzia jakości dla `web/`: Prettier, Vitest, Playwright, Node 26 (2026-10-20)

Decyzja: Prettier z domyślnymi ustawieniami i szerokością 100 (jak ruff) formatuje cały `web/`;
`AGENTS.md`, `pnpm-lock.yaml` i pliki generowane są pominięte. Vitest testuje tylko czyste funkcje
w `lib/`; komponenty i akcje serwerowe testuje Playwright w Chromium przeciw lokalnemu Supabase,
zakładając użytkownika testowego przez `/auth/v1/signup`. Node przypięty do 26 w `web/.node-version`.
CI dostaje drugi job `web`: format, lint, typy, testy jednostkowe, build; Playwright zostaje poza CI.
Powód: formatter zamiast dyskusji o wcięciach; jednostkowo tylko to, co nie potrzebuje DOM ani
sieci; test w przeglądarce sprawdza proxy, akcje i ciasteczka razem, czego nie da się udawać.
Playwright w CI wymagałby Supabase na maszynie GitHuba, czyli kilku minut obrazów Dockera na bieg.
Konsekwencje: przed commitem w `web/` obowiązuje `pnpm format`; `pnpm test:e2e` uruchamia się
lokalnie z działającym Supabase, `webServer` w konfiguracji sam startuje `pnpm dev`.

### 13. `meta_client` na fixture spisanych z dokumentacji, dwa typy błędów (2026-10-20)

Decyzja: `backend/meta_client` to jedyne miejsce znające JSON Meta. Trzy operacje: utworzenie
szablonu (`POST /{waba_id}/message_templates`, format pozycyjny `{{n}}` z `example.body_text`),
odczyt stanu szablonu (`GET .../message_templates?name=&language=`) i wysyłka wiadomości
szablonowej (`POST /{phone_number_id}/messages`). Błędy mapujemy na dwa typy: `MetaTransientError`
(sieć, 5xx, kody throttlingu 4, 17, 32, 613, 80007, 130429, 131048, 131056) i `MetaPermanentError`
(reszta 4xx), bo sekcja 4.3 instrukcji każe ponawiać tylko pierwsze. Fixture w
`tests/fixtures/meta/` są spisane z dokumentacji Cloud API, nie nagrane z konta.
Powód: pakiet da się napisać i przetestować bez konta Meta; typ wyjątku zamiast kodu w każdym
miejscu wywołania; throttling przychodzi jako HTTP 400, więc klasyfikacja idzie po kodzie Meta.
Konsekwencje: przy pierwszym prawdziwym wywołaniu trzeba potwierdzić i w razie potrzeby poprawić:
wartość `parameter_format` ("positional" wg przykładu w dokumentacji), kształt przycisków
quick reply (`BUTTONS` / `QUICK_REPLY`, nie zweryfikowany w dokumentacji) oraz pole `category`
w odpowiedzi na utworzenie szablonu; wtedy fixture zastępujemy nagranymi odpowiedziami. Pole
`rejected_reason` Meta mapujemy na nasze `rejection_reason`, a wartość `NONE` na brak powodu.

### 14. API czyta i pisze bazę przez Supabase REST, Meta opcjonalna lokalnie (2026-10-20)

Decyzja: API nie łączy się z Postgresem bezpośrednio. `api/db.py` woła PostgREST pod
`{SUPABASE_URL}/rest/v1` przez httpx z kluczem service role, z nagłówkiem
`Prefer: return=representation`; naruszenie unikalności wraca jako 409, inne błędy bazy jako 502,
brak połączenia jako 503. Zmienne `META_*` mają lokalne wartości domyślne, a pusty
`META_SYSTEM_USER_TOKEN` oznacza "Meta nieskonfigurowana": szkice i lista działają, `submit` i
`sync` odpowiadają 503. Statusy w `templates` rozszerzone migracją o pełny enum Meta.
Powód: bez nowej zależności, bez connection stringa i bez puli połączeń, co na Vercelu, gdzie każda
funkcja startuje osobno, jest realnym problemem; `ON CONFLICT DO NOTHING` z sekcji 4.3 ma w PostgREST
odpowiednik `Prefer: resolution=ignore-duplicates`. Opcjonalna Meta pozwala rozwijać i testować
szablony bez konta.
Konsekwencje: filtry w składni PostgREST (`id=eq.<uuid>`); brak transakcji między wierszami, co dla
PoC wystarcza; worker na Cloud Run może później dostać asyncpg, jeśli SQL okaże się potrzebny.
Testy tras używają podróbek bazy i Meta przez `dependency_overrides`, więc prawdziwy `Database`
sprawdza tylko próba na żywo.

### 15. Panel woła API tylko z serwera, wylogowanie lokalne, proxy nie przekierowuje POST (2026-10-20)

Decyzja: strony i akcje Next wołają FastAPI przez `web/lib/api.ts` z tokenem sesji z ciasteczka;
adres w zmiennej `API_URL` bez prefiksu `NEXT_PUBLIC_`, moduł oznaczony `server-only`. Przeglądarka
nigdy nie woła API. `logout` używa `signOut({ scope: "local" })`, proxy przekierowuje anonimowych
tylko dla żądań GET, a akcja, która dostanie z API 401, odsyła na `/login`.
Powód: bez CORS i bez wystawiania API w przeglądarce; API i tak weryfikuje token w Supabase.
Domyślny zakres `global` w `signOut` unieważnia wszystkie sesje użytkownika, więc wylogowanie w jednej
karcie psuło akcje w drugiej, a w Playwright test logowania zabijał sesję testu szablonów w drugim
workerze. Przekierowanie POST akcji serwerowej z proxy kończy się w React błędem "unexpected
response", bo zamiast strumienia akcji przychodzi HTML strony logowania.
Konsekwencje: Playwright uruchamia też API (`webServer` z `cwd: ../backend`), więc e2e przechodzi
przez przeglądarkę, serwer Next, API i bazę; test szablonów zostawia w lokalnej bazie szkice
`e2e_<czas>`, które czyści `db reset`.

### 16. Webhooki Meta: podpis i parser w `meta_client`, część kształtów założona (2026-10-21)

Decyzja: `meta_client/webhooks.py` sprawdza `X-Hub-Signature-256` jako `sha256=` + HMAC-SHA256
sekretu aplikacji z surowym ciałem, porównując w stałym czasie, i spłaszcza `entry[].changes[]`
do trzech typów zdarzeń: status szablonu, status naszej wiadomości, wiadomość przychodząca.
Nieznane pola i statusy są pomijane, nie zgłaszane; numery telefonów parser normalizuje do E.164
z plusem. Potwierdzone w dokumentacji: kształt `statuses`, pola `message_template_status_update`,
handshake `hub.verify_token`, nagłówek podpisu. Założone na podstawie ustalonego formatu Cloud API,
bo strony referencyjne renderuje JavaScript: odpowiedź przyciskiem (`type: button`,
`button.payload`), pole `context.id` i tablica `errors` w statusach.
Powód: pominięcie nieznanego statusu zamiast błędu, bo Meta ponawia webhook po każdej odpowiedzi
spoza 2xx i jeden nowy status zapętliłby dostawę; parser w `meta_client`, żeby trasa w API
widziała tylko nasze typy.
Konsekwencje: przy pierwszym prawdziwym webhooku trzeba porównać ładunek z fixture
`webhook_inbound.json` i poprawić założone pola; zapis do tabel i handshake to krok 3b,
sygnały do Temporal przyjdą z silnikiem Journey w fazie 3.

### 17. Webhook w API: zapis idempotentny, kontakt z numeru, STOP jako opt-out (2026-10-21)

Decyzja: `/webhooks/meta` to jedyna trasa bez logowania; `GET` obsługuje handshake, `POST` sprawdza
podpis z surowych bajtów i zapisuje zdarzenia przed odpowiedzią 200. Statusy trafiają do
`message_events` przez `ON CONFLICT DO NOTHING` na nowej unikalności `(wamid, type)`, wiadomości
przychodzące do `inbound_messages` z unikalnością `wamid`; nieznany numer dostaje nowy wiersz
w `contacts` (upsert po `phone_e164`); tekst ze słownika STOP tworzy zgodę `opted_out`. Pusty
`META_APP_SECRET` lub `META_WEBHOOK_VERIFY_TOKEN` oznacza 503. Sygnałów do Temporal jeszcze nie ma.
Powód: Meta ponawia każdą odpowiedź spoza 2xx, więc powtórka webhooka musi być bezpieczna;
`inbound_messages.contact_id` nie może być puste, a sekcja 4.4 każe najpierw zapisać, dlatego
kontakt powstaje z numeru. Lista słów opt-out to stała w kodzie, dopóki nie ma potrzeb językowych.
Konsekwencje: status wiadomości może cofnąć się z `read` na `delivered`, gdy webhooki przyjdą
w złej kolejności; sygnały `message_status`, `reply` i `opt_out` do workflow dojdą w fazie 3,
w tym samym miejscu po zapisie. Testy tras używają wspólnej podróbki bazy z `tests/_fakes.py`.

### 18. Wysyłka testowa: strażnik numerów w `core`, zgoda z listy testowej, `accepted` jako `sent` (2026-10-21)

Decyzja: `POST /messages/test` wysyła jeden zatwierdzony szablon na numer z `WA_ALLOWED_TEST_RECIPIENTS`.
Reguły "komu wolno wysłać" (`core/sending.py`) i "czy jest zgoda" (`core/consent.py`) są czystymi
funkcjami, które w fazie 3 przejmie aktywność `send_template` workera. Numer z listy testowej dostaje
przy pierwszej wysyłce zgodę `opted_in` ze źródłem `test_allowlist`, bo to nasze własne numery.
Wiersz w `messages` powstaje przed wywołaniem Meta z kluczem `test:<uuid>` i pustym `run_id`
(migracja zdejmuje `NOT NULL`); odpowiedź Meta `accepted` zapisujemy jako nasz status `sent`, bo
ograniczenie kolumny nie zna `accepted`, a webhook `sent` i tak przychodzi chwilę później.
`WA_SEND_MODE` spoza {`test`, `live`} zatrzymuje start API.
Powód: strażnik w `core` jest testowalny bez I/O i wspólny dla API i workera; zgoda z listy
testowej pozwala sprawdzić kryterium 6 briefu bez konektora; `GET /messages` korzysta z osadzania
tabel przez PostgREST zamiast własnego JOIN-a.
Konsekwencje: prawdziwe zgody przyjdą z konektora w fazie 4; panel i log to krok 4b; wysyłkę na
żywo da się sprawdzić dopiero z tokenem Meta i numerem testowym.

### 19. Panel: wysyłka testowa przy zatwierdzonym szablonie, log z osadzonych tabel, e2e przez webhook (2026-10-21)

Decyzja: formularz "Send test" renderuje się tylko przy szablonie `APPROVED`, w tej samej tabeli co
akcje; po wysłaniu panel przechodzi na `/messages`, a błąd API wraca na `/templates`. Strona logu
czyta jedno `GET /messages` z osadzonymi `templates`, `contacts` i `message_events` i pokazuje
zdarzenia dostarczenia w kolejności czasu. Test Playwright zatwierdza świeży szkic podpisanym
webhookiem do lokalnego API, dlatego `backend/.env` trzyma testowe `META_APP_SECRET` i
`META_WEBHOOK_VERIFY_TOKEN` o wartościach wpisanych w teście.
Powód: zatwierdzenie przez webhook to jedyna droga do stanu `APPROVED` bez konta Meta, a przy
okazji test przechodzi przez cały łańcuch: przeglądarka, serwer Next, API, PostgREST, webhook.
Konsekwencje: asercje e2e nie mogą zakładać pustej bazy (log może mieć wiersze z wcześniejszych
prób); sekrety e2e są jawnie testowe i nigdy nie trafiają do repo poza stałą w teście.

### 20. Klient PostgREST w pakiecie `storage`, wspólny dla API i workera (2026-10-21)

Decyzja: `storage/postgrest.py` to jedyny kod, który rozmawia z PostgREST; API trzyma w `api/db.py`
cienką podklasę zasilaną z `Settings`, a worker dostanie ten sam klient w aktywnościach. Błędy mają
własne klasy: `StorageUnavailable` (brak połączenia), `StorageRequestError` z kodem i polem
`transient` (5xx), `ConflictError`, `NotFoundError`. API mapuje je na 503, 502, 409 i 404 w jednym
handlerze w `main.py`; trasy nie znają już kodów bazy.
Powód: aktywność Temporal decyduje o ponowieniu po typie wyjątku, nie po kodzie HTTP, a jeden
klient oznacza jedną wiedzę o nagłówkach `Prefer`, `on_conflict` i osadzaniu tabel.
Konsekwencje: nowy pakiet najwyższego poziomu `storage` obok `core`, `api`, `worker`,
`meta_client`, `sync`; `core` nadal niczego z niego nie importuje; podróbka bazy w testach rzuca
te same klasy, a prawdziwy klient ma od tego kroku własne testy jednostkowe.

### 21. Aktywności Journey: klasa z wstrzykiwanymi klientami, dataclassy, dwie drogi błędów (2026-10-21)

Decyzja: aktywności workera są metodami `JourneyActivities`, która w konstruktorze dostaje bazę
i Meta jako protokoły (`Storage`, `TemplateSender`), więc testy podstawiają podróbki bez Temporal.
Wejścia i wyjścia to `dataclass`, bo domyślny konwerter Temporal serializuje je bez konfiguracji.
`send_template` realizuje sekcję 4.3: wiersz w `messages` przez `ON CONFLICT DO NOTHING` na
`idempotency_key` = `workflow_id:node_id:visit`, istniejący `wamid` wraca bez wołania Meta, odmowa
Meta i strażnik numerów kończą się wynikiem `failed` dla ścieżki porażki w workflow, a błędy
przejściowe są rzucane dalej, żeby Temporal ponowił aktywność. Brak kontaktu, szablonu albo tokenu
Meta to `ApplicationError(non_retryable=True)`. `update_contact` scala klucze `attributes.*`
z JSON-em atrybutów, inne klucze traktuje jako kolumny; `record_run_progress` ustawia `ended_at`
dla statusów końcowych.
Powód: brak globalnych klientów, czyste testy jednostkowe aktywności, a podział "wynik `failed`
kontra wyjątek" oddaje semantykę Temporal: wyjątek znaczy "spróbuj jeszcze raz".
Konsekwencje: ryzyko resztkowe z sekcji 4.3, awaria między odpowiedzią Meta a zapisem `wamid`,
może dać podwójną wysyłkę po ponowieniu; status `skipped_no_consent` wymaga migracji przy
workflow (5c); błędy bazy klasyfikuje dopiero polityka ponowień w workflow.

### 22. `JourneyWorkflow`: jeden interpreter, zgoda przed każdą wysyłką, porażka wysyłki kończy przebieg (2026-10-21)

Decyzja: `worker/workflows/journey.py` interpretuje definicję z `core` w pętli po węzłach; wejściem
jest `JourneyRunInput` z pełną migawką definicji, więc publikacja nowej wersji nie zmienia trwających
przebiegów. Przed każdym `send_template` idzie `check_consent`, a brak zgody kończy przebieg statusem
`skipped_no_consent` (migracja rozszerza ograniczenie `journey_runs.status`). Wynik `failed` z
aktywności kończy przebieg statusem `failed`, bo definicja nie ma portu porażki. Licznik odwiedzin
węzła daje trzeci człon klucza idempotencji. `update_contact` przeładowuje kontakt, żeby warunki
`branch` widziały świeże atrybuty. Zapytanie `current_state` zwraca węzeł i powód oczekiwania.
Węzeł `wait_for_reply` jest odrzucany do czasu kroku z sygnałami. Aktywności metodowe woła
`execute_activity_method`, bo `execute_activity` jest typowane dla samodzielnych funkcji.
Powód: sekcja 4.2 wymaga jednego generycznego workflow, determinizmu i zgody przed wysyłką;
przeładowanie kontaktu po `update_contact` jest tańsze od duplikowania logiki scalania w workflow.
Konsekwencje: porażka wysyłki w środku journey nie ma ścieżki alternatywnej (do rozważenia port
porażki w edytorze, "Later"); polityka ponowień `send_template` to 5 prób od 2 s; testy workflow
działają na serwerze testowym z przeskakiwaniem czasu, więc `wait` liczony w dniach trwa milisekundy.

### 23. Sygnały w `JourneyWorkflow`: odpowiedź oczekująca, opt-out przerywa czekanie (2026-10-21)

Decyzja: workflow przyjmuje trzy sygnały z sekcji 4.2. `inbound_message` niesie `ReplySignal`
(`wamid`, `text`, `button_payload`, `context_wamid`); odpowiedź leży jako oczekująca do najbliższego
`wait_for_reply`, a nowsza nadpisuje niezużytą. `opt_out` ustawia flagę sprawdzaną na początku
każdego węzła oraz przerywa `wait` i `wait_for_reply`, bo oba czekają przez `wait_condition`
z limitem zamiast `sleep`; przebieg kończy się statusem `opted_out` (migracja). `message_status`
jest tylko zapamiętywany, w ograniczonej liczbie, dla przyszłych węzłów. `wait_for_reply` wychodzi
portem `replied` z kontekstem `reply.*` albo `timeout` bez niego.
Powód: odpowiedź, która przyjdzie przed dojściem do `wait_for_reply`, nie powinna ginąć; opt-out
w sekcji 4.2 ma kończyć przebieg natychmiast, a `workflow.sleep` nie da się przerwać sygnałem.
Konsekwencje: odpowiedź z wcześniejszej, niepowiązanej wiadomości też zostanie zużyta, jeśli
webhook ją skieruje do tego przebiegu; dopasowanie po `context_wamid` należy do webhooka (5e).
Testy używają `env.sleep` do przesuwania zegara i `start_signal` dla sygnałów sprzed startu.

### 24. API journeys: publikacja = wersja, start przez bazę i Temporal, połączenie leniwe (2026-10-21)

Decyzja: `POST /journeys/{id}/versions` przyjmuje surową definicję, sprawdza ją schematem z `core`
i regułami grafu wobec zatwierdzonych szablonów, zapisuje bez zmian jako kolejny numer wersji
z `published_at` i przełącza journey na `active`; nie ma wersji roboczych po stronie API, szkice
żyją w edytorze (faza 4). `POST /journeys/{id}/runs` dla każdego kontaktu wstawia wiersz
`journey_runs` i startuje `JourneyWorkflow` z identyfikatorem `journey:{journey_id}:contact:{contact_id}`
na najnowszej wersji; konflikt z indeksu częściowego albo odmowa Temporal oznaczają "pominięty",
nie błąd. `POST /runs/{id}/cancel` anuluje workflow i ustawia status wiersza; `GET /runs/{id}`
dokłada stan z zapytania `current_state`. Klient Temporal powstaje przy pierwszym użyciu i jest
trzymany w `app.state`; brak Temporal to 503 tylko dla tras, które go potrzebują.
Powód: dwa niezależne strażniki jedynego aktywnego przebiegu, baza i Temporal, zgodnie z sekcją 4.2;
leniwe połączenie pozwala uruchamiać API i testy e2e panelu bez serwera Temporal.
Konsekwencje: API importuje `JourneyRunInput`, `JourneyWorkflow` i `TASK_QUEUE` z pakietu `worker`,
czyli zależy od jego kontraktu; wiersz przebiegu, którego Temporal odmówił, dostaje status
`cancelled`; segmenty jako filtr kontaktów (faza 3 w instrukcji) zostają na później.

### 25. Webhook kieruje sygnały do przebiegów: po `context_wamid`, inaczej do wszystkich biegnących (2026-10-21)

Decyzja: po idempotentnym zapisie webhook wysyła sygnały do `JourneyWorkflow`. Wiadomość
przychodząca z `context` (odpowiedź na konkretną wiadomość) trafia tylko do przebiegu, który tę
wiadomość wysłał (`messages.wamid` → `run_id`); bez `context` trafia do każdego biegnącego przebiegu
kontaktu. Słowo opt-out, po zapisaniu zgody, wysyła dodatkowo `opt_out` do wszystkich biegnących
przebiegów kontaktu. Status dostarczenia (`message_status`) idzie tylko do przebiegu, do którego
należy wiadomość. Adresatami są wyłącznie wiersze `journey_runs` ze statusem `running`; duplikat od
Mety (konflikt `wamid`) nie wysyła nic. Sygnały są "best effort": zapis jest pierwszy, błąd RPC
Temporal jest logowany, a Meta i tak dostaje 200; brak połączenia z Temporal (`OptionalRuns` daje
`None`) nie blokuje zapisu. Sygnał do zamkniętego lub nieznanego workflow (NOT_FOUND) jest
ignorowany w `TemporalJourneyRuns`. Nieudane połączenie SDK zgłasza jako `RuntimeError`, nie
`RPCError`; `get_runs` łapie oba (poprawka po 5e: e2e panelu bez Temporal dostało z webhooka 500).
Powód: sekcja 4.2 wymaga, by odpowiedź docierała do właściwego przebiegu, a opt-out kończył
wszystkie; webhook musi odpowiadać szybko i nie może zależeć od Temporal, bo Meta ponawia
dostarczenie przy błędzie, a ponowienie nie naprawiłoby sygnału, skoro zapis już jest.
Konsekwencje: przy STOP w `wait_for_reply` przebieg dostaje najpierw `inbound_message`, potem
`opt_out`; workflow zużywa odpowiedź, przechodzi do następnego węzła i tam kończy jako `opted_out`
(w teście na żywo `current_node_id` = `br`). Zdarzenie, które przyszło w czasie awarii Temporal, nie
jest sygnalizowane później (brak kolejki ponowień); taki przebieg skończy się timeoutem
`wait_for_reply`. Wiadomość bez `run_id` (wysyłka testowa) nigdy nie sygnalizuje.

### 26. Test replay z nagranej historii i mapa scenariuszy akceptacyjnych fazy 3 (2026-10-21)

Decyzja: historia jednego zakończonego przebiegu journey z sekcji 4.1 (wysyłka, dwa dni czekania,
`wait_for_reply`, odpowiedź przyciskiem, `update_contact`) jest nagrana na serwerze time-skipping
przez `tests/record_replay_history.py` i trzymana w repo jako
`tests/fixtures/temporal/journey_guide_example_history.json` (94 zdarzenia, 46 KB).
`tests/test_journey_replay.py` odtwarza ją przez `temporalio.worker.Replayer` na bieżącym kodzie
`JourneyWorkflow`, czyli robi to, co worker po restarcie, i osobno dowodzi, że wariant z jedną
dodatkową komendą kończy się `NondeterminismError`. Po celowej zmianie kolejności komend:
`workflow.patched()` i nowe nagranie tym samym poleceniem; samo nagranie od nowa bez `patched()`
ukryłoby niezgodność dla przebiegów trwających w produkcji. Scenariusz "aktywność pada po wywołaniu
Meta" symuluje `FakeDb.lost_responses`: zapis `wamid` się udaje, odpowiedź "ginie", Temporal
ponawia aktywność, która znajduje `wamid` (krok 2 z sekcji 4.3), więc Meta dostaje jedno wywołanie.
Powód: sekcja 6 wymaga ośmiu scenariuszy na `start_time_skipping()`, a sekcja 4.2 testu replay dla
każdej wydanej wersji; nagranie w repo jest jedynym sposobem, by test sprawdzał kod wobec historii
starszej niż on sam.
Konsekwencje: mapa scenariuszy z sekcji 6 (Phase 3) na testy, do raportu w fazie 5:

| Scenariusz | Test |
|---|---|
| happy path | `test_journey_workflow::test_happy_path_sends_waits_updates_and_branches` |
| reply before timeout | `test_journey_signals::test_button_reply_before_timeout_takes_the_replied_port` |
| timeout path | `test_journey_signals::test_no_reply_takes_the_timeout_port` |
| branch by button payload | j.w. oraz `test_journey_signals::test_text_reply_without_button_takes_the_else_branch` |
| opt-out mid-journey | `test_journey_signals::test_opt_out_during_a_wait_ends_the_run_at_once` i `..._before_the_first_send_sends_nothing` |
| no-consent skip | `test_journey_workflow::test_no_consent_skips_the_run_before_any_send` |
| send retry without duplicate | `test_journey_workflow::test_transient_meta_error_is_retried_without_a_second_send` (błąd przed Meta) i `..._crash_after_the_meta_call_is_retried_without_a_second_send` (po Meta) |
| worker restart (replay) | `test_journey_replay::test_current_code_replays_the_recorded_history` |

Demo end-to-end na numerach testowych czeka na konto Meta po stronie właściciela. Fixture zależy
od formatu historii SDK (protobuf JSON, stabilny), ma identyfikator `journey:j-1:contact:c-1`
i czasy serwera testowego, bez sekretów.

### 27. Szkice journey w API: jedna nieopublikowana wersja, kształt teraz, treść przy publikacji (2026-10-21)

Decyzja: szkic edytora to wiersz `journey_versions` bez `published_at`; indeks częściowy
`journey_versions_one_draft_idx` dopuszcza jeden taki wiersz na journey. `PUT /journeys/{id}/draft`
zakłada szkic z kolejnym numerem wersji albo nadpisuje istniejący (definicję i `layout` w całości)
i sprawdza tylko kształt (`schema_version` 1, listy `nodes` do 50 i `edges` do 200), bo
niedokończony węzeł, np. `send_template` bez szablonu, musi dać się zapisać.
`POST /journeys/{id}/publish` robi pełną walidację (schemat i reguły grafu wobec zatwierdzonych
szablonów), ustawia `published_at` i przełącza journey na `active`; szkic zachowuje swój numer.
Pozycje węzłów na kanwie leżą w nowej kolumnie `journey_versions.layout` (id węzła → x, y), nie
w definicji, która pozostaje ścisłym wejściem silnika. `GET /journeys/{id}` zwraca journey ze
wszystkimi wersjami od najstarszej. Start przebiegów bierze najnowszą opublikowaną wersję i pomija
szkic. `POST /journeys/{id}/versions` zostaje dla klientów API.
Powód: edytor (kroki 6c–6e) zapisuje w trakcie pracy, a serwer ma być autorytatywny przy
publikacji (sekcja 6, faza 4); wersja opublikowana musi pozostać niezmienna (sekcja 3).
Konsekwencje: numer wersji jest nadawany przy założeniu szkicu, więc publikacja przez
`POST /versions` w czasie życia szkicu da wersję o wyższym numerze, ale wcześniejszej dacie;
porządek wersji to numer, nie data. Równoległy zapis dwóch szkiców kończy się 409 z indeksu.
`PUT` zastępuje także `layout`, więc edytor zawsze wysyła komplet pozycji.

### 28. Panel journeys: lista z wersjami osadzonymi w API, strona journey, wspólny helper akcji (2026-10-21)

Decyzja: `GET /journeys` osadza `journey_versions(id, version, published_at)` przez PostgREST, więc
lista w panelu pokazuje "v2 published, draft v3" bez zapytania na wiersz. Strona `/journeys/{id}`
czyta `GET /journeys/{id}` i pokazuje wersje z liczbą węzłów; edytor (6c) i przebiegi (6f) dojdą
do niej jako linki. Helper `perform` przeniesiony z `app/templates/actions.ts` do `lib/actions.ts`
i rozszerzony o cel przekierowania liczony z odpowiedzi API, żeby po utworzeniu journey panel
przechodził na jej stronę. Playwright `journeys.spec.ts` tworzy journey i sprawdza listę.
Powód: jedna lista = jedno zapytanie; jeden sposób obsługi błędów akcji dla wszystkich stron.
Konsekwencje: typ `JourneyRow` ma opcjonalne `journey_versions`, bo `FakeDb` ignoruje `columns`
i testy API nie widzą osadzenia; `describeVersions` traktuje brak pola jak brak wersji. Pełny
zestaw e2e wymaga teraz uruchomionego Temporal albo poprawki `get_runs` (wpis 25).

### 29. Edytor: React Flow na kanwie, definicja jest źródłem prawdy, cele branch jako krawędzie (2026-10-21)

Decyzja: `@xyflow/react` (wybór z sekcji 1 instrukcji) rysuje kanwę na `/journeys/{id}/edit`.
Jedyną reprezentacją journey pozostaje definicja JSON plus `layout`; graf React Flow jest widokiem
liczonym czystymi funkcjami `toGraph` i `fromGraph` w `web/lib/journey-graph.ts`, z testem
round-trip na tej samej fixture co backend (`backend/tests/fixtures/journey_guide_example.json`).
Uchwyty wyjściowe wynikają z typu węzła: jeden `next`, `replied` i `timeout` dla `wait_for_reply`,
`cond-i` i `else` dla `branch`. Cele `branch` w definicji leżą w węźle (`conditions[i].next`,
`else`), więc na kanwie stają się krawędziami z tych uchwytów, a `fromGraph` wpisuje je z powrotem
do węzła i nie dodaje ich do `edges`. Jeden uchwyt prowadzi do jednego węzła: nowe połączenie
zastępuje poprzednie. Paleta dodaje węzły z domyślnymi wartościami szkicu (`PT1H`, `PT24H`, pusty
szablon, pusta lista warunków); konfigurację węzła da panel boczny (6d), walidację i publikację
krok 6e. Zapis to akcja serwera `saveDraft` zwracająca wynik zamiast przekierowania, bo edytor
zostaje na stronie. Punkt startu edytora: szkic, w jego braku kopia najnowszej opublikowanej
wersji, w jej braku `start` i `end`.
Powód: edytor nie może mieć własnego modelu, bo silnik czyta definicję; a cele `branch` w węźle
(sekcja 4.1) muszą dać się rysować jak zwykłe krawędzie.
Konsekwencje: usunięcie węzła czyści wskazania `next`/`else`, które do niego prowadziły; pozycje
są zaokrąglane do całych pikseli; e2e `editor.spec.ts` dodaje węzeł przyciskiem i zapisuje, bez
przeciągania krawędzi (to zostaje w 6e przez pole "następny węzeł" w panelu).

### 30. Panel węzła: formularz na typ, cele uchwytów w panelu, czasy jako liczba i jednostka (2026-10-21)

Decyzja: po kliknięciu węzła edytor pokazuje panel boczny z osobnym formularzem na typ
(`react-hook-form` + `zod`, resolver `@hookform/resolvers`, wybory z sekcji 1 instrukcji). Czyste
funkcje w `web/lib/node-forms.ts` tłumaczą węzeł i jego cele uchwytów na wartości formularza
i z powrotem (`xDefaults`, `xApply`), więc komponenty nie zawierają logiki i są testowane
Vitestem. Każdy formularz ma pola "dokąd dalej" dla uchwytów węzła (`next`, `replied`/`timeout`,
po jednym na warunek i `else`), a Apply przebudowuje krawędzie wychodzące węzła (`withTargets`),
więc panel jest pełnoprawną alternatywą dla przeciągania krawędzi. Czas w `wait` i `wait_for_reply`
to liczba plus jednostka (minuty, godziny, dni) tłumaczona na ISO 8601 (`P2D`, `PT3H`, `PT45M`);
nietypowy zapis (`PT1H30M`) pokazuje się w minutach. `send_template` wybiera tylko zatwierdzony
szablon, a liczba pól zmiennych wynika z najwyższego `{{n}}` w treści szablonu; zmienna to ścieżka
w kontekście (`contact.first_name`). Warunek `branch` to para ścieżka = wartość (tekst); `set`
w `update_contact` to pary klucz = wartość (tekst). Identyfikator węzła nie jest edytowalny.
Powód: definicja jest źródłem prawdy, więc formularz musi mapować się na nią jeden do jednego;
użytkownik myśli "2 dni", silnik czyta `P2D`.
Konsekwencje: warunek z kilkoma kluczami w `if` traci w panelu wszystkie poza pierwszym (edytor
tworzy tylko jednokluczowe); wartości warunków i `set` są tekstem (bool i liczby zostają
w "Later"); szablony spoza panelu mogą mieć `components` w innym kształcie (`[]`, lista Mety),
więc treść czytana jest defensywnie i taki szablon ma zero zmiennych.

### 31. Edytor: walidacja po stronie panelu jako lustro backendu, publikacja z edytora (2026-10-21)

Decyzja: `web/lib/journey-validation.ts` powtarza reguły grafu z `core/validation.py` z tymi
samymi komunikatami, a jej test Vitest przenosi przypadki z `tests/test_validation.py` i tę
samą fixture, więc obie strony muszą się zgadzać. Edytor liczy listę problemów przy każdej
zmianie (`problemsOf`): najpierw "niedokończone" pola szkicu powiedziane po ludzku (brak szablonu,
warunek albo `else` bez celu), potem reguły grafu bez echa tych samych braków. Przycisk Publish
jest zablokowany, dopóki lista nie jest pusta; po kliknięciu akcja serwera zapisuje szkic
i woła `POST /journeys/{id}/publish`, a 422 z API wraca jako lista problemów serwera, pokazana
osobno (serwer pozostaje autorytatywny). Po publikacji panel przechodzi na stronę journey.
`ApiError` niesie teraz `details` (lista), bo FastAPI zwraca problemy walidacji jako listę.
Po dodaniu węzła kanwa dopasowuje widok (`useNodesInitialized` + `fitView`), bo nowe węzły
trafiały poza ekran. Playwright `publish.spec.ts` buduje w edytorze journey z kryterium 2 briefu
(wyślij → czekaj → czekaj na odpowiedź → rozgałęź) i publikuje ją; `approveTemplate`
w `e2e/helpers.ts` zatwierdza szablon podpisanym webhookiem.
Powód: sekcja 6 (faza 4) wymaga walidacji po stronie klienta lustrzanej do serwera i testu
"build-journey, publish"; użytkownik ma widzieć, czego brakuje, zanim kliknie.
Konsekwencje: zmiana reguły w `core/validation.py` wymaga tej samej zmiany w lustrze (test po
obu stronach to wychwyci tylko dla wspólnych przypadków); w testach Playwright pola panelu wybiera
się po `name`, bo tekst etykiety obejmuje listę opcji, a krawędzie React Flow mają `aria-label`
z identyfikatorami węzłów; po kliknięciu węzła test czeka na "id: …" w panelu, bo formularz
podmienia się po ustaleniu zaznaczenia.

### 32. Widok przebiegów: start po numerach telefonów, stan z bazy; jeden arkusz stylów bez frameworka (2026-10-21)

Decyzja: `POST /journeys/{id}/runs` przyjmuje obok `contact_ids` listę `phones` (E.164); API
rozwiązuje numery na kontakty jednym zapytaniem `in.(...)` i zwraca `unknown` dla numerów bez
kontaktu, nic dla nich nie tworząc. Strona `/journeys/{id}/runs` pokazuje przebiegi ze stanem
z bazy (`status`, `current_node_id` zapisywane przez `record_run_progress` przy każdym węźle),
formularz startu po numerach i Cancel dla biegnących; nie odpytuje Temporal na liście, żeby
strona działała także bez niego (stan live zostaje w `GET /runs/{id}`). Panel dostaje jeden
globalny arkusz `app/globals.css` (tokeny kolorów z trybem ciemnym po `prefers-color-scheme`,
elementy bazowe, kilka klas układu) i wspólny pasek `components/nav.tsx`; bez Tailwinda ani
zestawu UI, bo sekcja 1 instrukcji każe uzasadniać każdą taką zależność, a PoC potrzebuje tylko
czytelności. Strony mają okruszki pod paskiem; link do sekcji w testach klika się w `navigation`.
Powód: sekcja 6 (faza 4): "lista przebiegów z bieżącym węzłem z bazy, opcjonalnie live"; start
po liście numerów zamiast identyfikatorów, bo tak myśli użytkownik panelu.
Konsekwencje: prosty filtr segmentu (kraj, atrybut) z "Later" nadal czeka; etykieta szablonu na
węźle to skrót identyfikatora, bo pełny UUID poszerzał węzeł na sąsiada (nazwa wymagałaby
słownika szablonów w widoku węzła); dopasowanie widoku po pierwszym renderze bywa za wczesne
(przycisk Fit View w kontrolkach); API w trybie dev warto uruchamiać z `--reload`, bo bez tego
zmiany w kodzie nie są widoczne, co kosztowało jedną turę przy tym kroku.

## Later

- Wartości warunków `branch` są tylko tekstem: `Condition.if` to `dict[str, str]`, a
  `condition_matches` porównuje przez `==`. Rozgałęzienie po atrybucie bool (np.
  `attributes.interested: true` ustawionym przez `update_contact`) wymaga rozszerzenia typu
  `Condition.if` (np. o `bool` i `int`) oraz testów porównania typów.
- Weryfikacja JWT lokalnie przez JWKS z cache (PyJWT, `PyJWKClient`) zamiast wywołania
  `/auth/v1/user`; API czyta listę domen z `panel_allowed_domains` zamiast z env, żeby było jedno
  źródło prawdy.
- Playwright w CI: Supabase na runnerze (`supabase/setup-cli` + `supabase start`) albo projekt
  testowy w chmurze; do decyzji, gdy testów e2e będzie więcej niż jeden plik.
- Webhook: konfigurowalna, wielojęzyczna lista słów opt-out (env lub tabela); ochrona przed
  cofaniem statusu wiadomości przy webhookach w złej kolejności (porządek sent < delivered < read).
- Port porażki dla `send_template` w definicji i edytorze, zamiast kończenia przebiegu statusem
  `failed` przy pierwszej odmowie Meta.
- Start przebiegów po prostym filtrze segmentu kontaktów (np. kraj, atrybut) zamiast listy
  identyfikatorów; wersje robocze journey po stronie API, gdy edytor będzie zapisywał szkice.
- Ponowny start zakończonego kontaktu w tej samej journey: `journey_runs.workflow_id` jest
  unikalny, więc drugi przebieg dla tej samej pary journey+kontakt jest pomijany także po
  zakończeniu pierwszego; identyfikator workflow z sufiksem (np. numer przebiegu) albo zdjęcie
  unikalności.
- Sygnały utracone w czasie awarii Temporal: kolejka ponowień (np. tabela `pending_signals`
  opróżniana przez workera) zamiast samego ostrzeżenia w logu.
- Edytor: dopasowanie widoku (`fitView`) po pierwszym renderze bywa za wczesne, gdy kanwa
  jeszcze nie ma rozmiaru; do sprawdzenia `onInit` albo `ResizeObserver` na kontenerze.
