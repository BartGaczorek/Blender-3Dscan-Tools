# Algorytmy v0.2

## Podział pracy

Główna instancja Blendera zachowuje źródło i obsługuje UI. Modalny operator aktualizuje panel na zdarzeniach TIMER, a osobny proces tej samej instalacji Blendera wykonuje decymację i opcjonalną analizę. Dane są przenoszone przez lokalne pliki tymczasowe `.blend` i JSON. Nie używamy bpy w dowolnym wątku Pythona.

Natywny Decimate nie udostępnia callbacku z procentem. W tym etapie pokazujemy aktywność i czas; pasek całego zadania opisuje umowne wagi etapów. Zapis snapshotu i odczyt wyniku są synchroniczne i mogą chwilowo zatrzymać UI. Esc/anulowanie zatrzymuje proces roboczy, ale nie przerywa atomowo trwającego synchronicznego IO. Po normalnym zakończeniu/anulowaniu pliki są usuwane. Zamknięcie awaryjne może pozostawić pliki tymczasowe.

## Kopia i układy

Oryginalny punkt lokalny `p` trafia do wyniku jako `M_manual @ M_prepare @ M_source @ p`. Początkowe przygotowanie jest zapisane w geometrii kopii; jej macierz obiektu startuje jako jednostkowa, aby pivot był w wycentrowanym modelu. Domyślnie `M_prepare` jest przesunięciem o środek bbox. Opcjonalnie zawiera orientację PCA/RANSAC i dopasowanie symetrii z v0.1.

„Geometry to Origin” nie gwarantuje położenia w (0,0,0), jeżeli origin był gdzie indziej. Apply Transforms nie wyznacza środka geometrycznego. Jawne macierze pozwalają przenosić operacje na oryginalną siatkę bez kopiowania geometrii proxy do wyniku.

## Interaktywna baza

Raycast na kopii wskazuje trójkąt startowy. Adjacency jest oparta na współdzielonych krawędziach. Kandydat musi mieć normalną w zadanym kącie do wspólnej normalnej oraz wszystkie wierzchołki w pasie o określonej grubości względem wspólnej płaszczyzny. Porównanie tylko kolejnych normalnych sąsiadów mogłoby stopniowo przejść po walcu; porównanie do wspólnej bazy ogranicza ten problem. Po rozroście dopasowujemy płaszczyznę i powtarzamy rozrost raz.

Dopasowanie TLS jest ważone powierzchnią i integruje drugi moment powierzchni każdego trójkąta. Nie zależy więc wyłącznie od nierównego zagęszczenia wierzchołków. Środek i kowariancja są liczone po odjęciu centroidu, co ogranicza utratę dokładności przy dużych współrzędnych. Najmniejsza wartość własna kowariancji wyznacza RMS od płaszczyzny; normalna dostaje znak zgodny z sumą zorientowanych pól trójkątów. Maksymalna odchyłka jest liczona po wierzchołkach zaznaczonego obszaru.

Zielony obszar i metryki umożliwiają użytkownikowi ocenę, czy wybrano zamierzoną ściankę. W v0.2 nie ma automatycznej segmentacji wszystkich regionów, rankingu ani semantycznego rozpoznawania podstawy. Dziury, rozłączna siatka i duży szum mogą wymagać ręcznego zaznaczenia w Edit Mode.

Przy wyrównaniu normalna zostaje przeliczona do świata macierzą odwrotnie transponowaną. Obrót dopasowuje ją do ±Z, zachowując środek zaznaczenia; następnie przesunięcie ustawia dopasowaną płaszczyznę w Z=0. Jest to płaszczyzna dopasowania — szum nie zostaje spłaszczony, a pojedyncze wierzchołki mogą leżeć nieznacznie poniżej Z=0.

## Interaktywne lustro

Nie optymalizujemy dwóch pełnych siatek i nie przebudowujemy mesha co klatkę. Obiekt kontrolny współdzieli siatkę kopii. Jego parent ma macierz `S=diag(-1,1,1,1)`, a constraint Copy Transforms kopiuje macierz świata podglądu do lokalnego układu obiektu kontrolnego. Otrzymujemy dokładnie `M_mirror = S @ M_preview`.

Działa to dla przesunięć, dowolnej kolejności obrotów, kwaternionów i skalowania. Nie wymaga odwracania znaków konkretnych kątów Eulera ani własnego handlera transformacji. Ujemny determinant pozostaje transformacją diagnostycznego obiektu; nie odwracamy windingu współdzielonej siatki, co uszkodziłoby podgląd. Negatywny determinant przy faktycznym zapisie geometrii wynikowej jest obsługiwany oddzielnie przez zmianę windingu.

Płaszczyzna lustra to zawsze globalne X=0. G X i R Z po ustaleniu dolnej bazy zachowują jej wyrównanie do XY. R X/R Y mogą bazę przechylić. Lustro pokazuje odchyłki geometryczne, nie dowodzi intencjonalnej symetrii ani nie naprawia skanu.

## Opcjonalna automatyczna symetria

Pozostaje algorytm v0.1: próbki ważone polem trójkątów, starty PCA, odbicie względem `n·p=d`, odległości próbka→powierzchnia BVH, minimum średnich kwadratów najmniejszych 80% reszt. W v0.2 dostaje callback etapów. Nie zmieniono go w rozwiązanie globalne; na trudnych częściach może wybrać niewłaściwą symetrię. Dlatego automatyczne ustawienie jest domyślnie wyłączone.
