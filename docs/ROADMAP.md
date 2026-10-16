# Następne etapy po v0.2

1. Próba na rzeczywistym skanie użytkownika: czas/RAM dla 1/5/15 mln trójkątów, poprawność klikniętej bazy i interaktywnego dopasowania w Windows; porównanie z ręcznym ustawieniem. Dostępne zrzuty nie zastępują testu na geometrii STL.
2. Lista wielu spójnych regionów bazowych, ranking według pola i RMS, wybór kilku regionów i maski wykluczeń. Lepsza obsługa rozłącznych i bardzo zaszumionych siatek.
3. Dokładniejsza ocena symetrii: zgodność normalnych, obustronne pokrycie, rankingi kandydatów, przeliczenie metryk po ręcznej korekcie. Autoakceptacja dopiero po kalibracji.
4. Kontrola błędu decymacji: dwustronne odległości powierzchni, jednostki fizyczne, ochrona granic, otworów i krawędzi.
5. Dalsze ograniczenie przerw IO i pomiar kosztu snapshotów. Trwały cache, zarządzanie dyskiem, obsługa bardzo dużych skanów i awaryjnego zamknięcia procesu.
6. Batch/CLI i eksport STL+JSON po ustabilizowaniu interaktywnego workflow.
