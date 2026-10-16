# Changelog

## 0.2.0
- Domyślnie przygotowanie lekkiej kopii bez automatycznej zmiany osi; eksperymentalne PCA/RANSAC dostępne opcjonalnie.
- Decymacja i dopasowanie w drugim procesie Blendera; panel etapów, aktywny wskaźnik, czas pracy i anulowanie.
- Kliknięcie ścianki: spójny region z progiem normalnych i odległości od wspólnej płaszczyzny.
- Obszar bazy z zaznaczonych ścianek w Edit Mode jako alternatywa.
- Dopasowanie płaszczyzny ważone powierzchnią trójkątów; zielone zaznaczenie, RMS i maksymalna odchyłka.
- Wyrównanie bazy do XY/Z=0 z wyborem kierunku normalnej.
- Dokładne interaktywne lustro względem globalnego X=0, z natywną aktualizacją podczas transformacji.
- Lustro współdzieli siatkę; podgląd startuje z wycentrowanym origin.
- Wynik z oryginalnej geometrii uwzględnia transformację przygotowania oraz ręczną korektę.
- Dodatkowe testy matematyczne, integracyjne i rzeczywistego UI.

## 0.1.0
- Panel dla PCA/RANSAC, dopasowanie symetrii, statyczne lustro kontrolne i osobny decymowany wynik.
- Raport, testy i GitHub Actions.
