# Walidacja wydania 0.2.0

Wykonano lokalnie na Blenderze 4.2.0 / Linux x86_64. Użyto geometrii syntetycznej; nie otrzymano źródłowego STL części ze zrzutów.

| Sprawdzenie | Wynik |
|---|---|
| 12 testów matematycznych (w tym szum, krzywizna, rozłączne regiony, gęstość triangulacji) | PASS |
| Walidacja manifestu folderu i instalacyjnego ZIP-a przez Blender Extension CLI | PASS |
| Smoke: snapshot → worker → proxy → wynik, redukcja liczby trójkątów, zachowanie źródła | PASS |
| Lustro na żywo: 24 różne transformacje, kwaterniony i skala niejednorodna | PASS |
| Płaszczyzna wybranego regionu trafia w światowe Z=0 z normalną -Z | PASS |
| Zaznaczone ścianki z Edit Mode jako baza | PASS |
| Przeniesienie pełnej macierzy przygotowania i korekty na oryginalne punkty | PASS |
| Anulowanie procesu usuwa pliki tymczasowe, źródło pozostaje bez zmian | PASS |
| Błąd obliczeń nie jest zgłaszany jako sukces | PASS |
| Rzeczywiste okno Blendera w Xvfb: operator modalny, panel, odbiór wyniku | PASS |
| Rzeczywiste zdarzenie kliknięcia w viewport → region → wyrównanie | PASS |
| Rzeczywiste zdarzenie Esc → anulowanie aktywnego zadania | PASS |

W teście UI zarejestrowano 17 tyknięć głównej pętli i 16 odrysowań panelu podczas aktywnego zadania. To test responsywności na małej siatce, nie benchmark dla skanów wielomilionowych. Wizualna ocena z-fightingu na rzeczywistym skanie, Windows/macOS i koszty pamięci dla bardzo dużych plików wymagają testu użytkownika.

Nie twierdzimy, że pasek podaje dokładny procent natywnej decymacji. Dla niej dostępne są nazwa etapu, aktywny wskaźnik, czas pracy i anulowanie; czas pozostały jest nieznany. Synchroniczny snapshot i wczytywanie wyniku nadal mogą chwilowo blokować UI.
