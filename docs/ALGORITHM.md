# Automatyka i udział użytkownika

## Zalecana forma docelowa

Dodatek Blendera jako Extension, z panelem i oddzielonym modułem obliczeniowym. Jeden skan → propozycje baz → podgląd → akceptacja → wynik. Dopiero po zebraniu dobrych przypadków testowych: tryb wsadowy i headless CLI. Sam jednorazowy skrypt utrudnia iterację, ocenę orientacji i powtarzalne ustawienia.

GitHub przechowuje kod, wymagania, PR-y, testy i wydania. Obliczenia na skanach wykonuje Blender na komputerze użytkownika, bez serwera i API. GitHub Actions sprawdza procedurę na małych syntetycznych siatkach.

## Interpretacja ręcznego workflow

„Geometry to Origin” przesuwa geometrię do aktualnego origin obiektu, który nie zawsze jest w (0,0,0). „Apply All Transforms” zachowuje położenie geometrii w świecie i zapisuje transformację w siatce; nie wyznacza geometrycznego środka. Dlatego dodatek liczy środek i docelowy układ jawnie, niezależnie od kursora 3D i wcześniejszego origin.

Lustro z constraints jest wizualnym sposobem szukania płaszczyzny symetrii. Nie trzeba optymalizować dwóch pełnych siatek ani wszystkich sześciu stopni swobody. Płaszczyzna ma normalną o dwóch stopniach swobody i jedno przesunięcie. Symetria nie ustala przesunięć w jej obrębie ani obrotu wokół jej normalnej — te stopnie swobody wymagają bazy, głównej osi lub decyzji użytkownika.

## Etapy

| Etap | Automatyka | Interakcja |
|---|---|---|
| Wejście | Sprawdzenie obiektu i przygotowanie kopii | Import STL, jednostki, wybór skanu |
| Przygotowanie | Redukcja kopii roboczej i próbkowanie powierzchni | Zmiana jakości tylko w trudnych przypadkach |
| Bazy | PCA; przybliżona płaszczyzna RANSAC, odpornie na szum | Docelowo wybór ścianki lub zaznaczenie regionu; v0.1 ocena i korekta ręczna |
| Symetria | Start z 3 osi PCA lub wskazanej osi; numeryczne dopasowanie płaszczyzny | Włączenie symetrii i ewentualny wybór osi startowej |
| Ocena | RMS po odcięciu największych reszt i P95 wszystkich reszt | Ocena intencjonalnej symetrii i kierunków góra/przód |
| Wynik | Przeniesienie transformacji na kopię oryginału, decymacja, raport | Akceptacja, ocena detali, eksport |

## Matematyka

Dla jednostkowej normalnej n i przesunięcia d płaszczyzna spełnia n·p=d. Odbicie punktu to p'=p−2(n·p−d)n. Dla punktów odbitych liczymy odległość do najbliższej powierzchni trójkątowej skanu roboczego (BVH), a nie różnicę indeksów wierzchołków.

Funkcja celu to średni kwadrat najmniejszych domyślnie 80% odległości. Zapobiega dominacji pojedynczego dużego występu, ale może także ukryć ważny fragment: użytkownik musi ocenić wynik. Dobry docelowy wariant dodaje zgodność normalnych, obustronne pokrycie, minimalny udział powierzchni po obu stronach płaszczyzny i maski obszarów. Nie są one zaimplementowane w v0.1.

W v0.1 lokalny coordinate descent zmienia normalną i przesunięcie w malejących krokach. Trzy starty PCA zwiększają szansę znalezienia właściwego minimum, lecz go nie gwarantują. Nie jest to pełna globalna optymalizacja ani klasyczny sztywny ICP.

Płaska ścianka jest wykrywana przez RANSAC na punktach powierzchniowych, a następnie dopasowana przez TLS/PCA. „Płaska” oznacza pas o zadanej tolerancji, nie identyczne normalne trójkątów. Tolerancja 0.006 przekątnej jest startowym parametrem do kalibracji, nie tolerancją produkcyjną. W docelowym narzędziu lepsze będzie rozrastanie regionów z kontrolą odległości i normalnych oraz wybór kilku kandydatów. Obecny próg 12% poparcia odrzuca słabe propozycje, ale nie odróżni każdej krzywizny od ścianki.

Priorytetem orientacji jest płaszczyzna symetrii → X=0. Normalna znalezionej ścianki wyznacza kierunek Z po projekcji na płaszczyznę symetrii. Przy sprzecznych bazach nie da się jednocześnie spełnić obu warunków dokładnie. RANSAC wybiera kierunek normalnej na zewnątrz od środka próbki; użytkownik może odwrócić górę/dół. Centrowanie wykorzystuje średnią próbkowanej powierzchni, nie środek masy objętościowej.

## Decymacja i bezpieczeństwo danych

Kopia robocza powstaje przed dopasowaniem, wynik końcowy zawsze z oryginalnej siatki. Transformacja jest sztywna (bez zmiany rozmiaru), chyba że użytkownik sam przeskaluje podgląd. Reflection służy wyłącznie do analizy i kontroli, nie zastępuje finalnej geometrii.

Cel to liczba trójkątów, nie ogólnych poligonów. Decimate Collapse z ratio target/current daje wynik przybliżony. W v0.1 nie ma pomiaru odchyłki powierzchni przed/po; milion trójkątów nie zapewnia określonej dokładności. Dla dużych skanów trzeba zmierzyć czas i szczytowe zużycie RAM; kopiowanie pełnej siatki i natywna decymacja mogą być kosztowniejsze od samego dopasowania.

Nie należy przebudowywać skanu przez voxel remesh jako domyślnego kroku, bo zmienia powierzchnię. Nie należy wymuszać idealnej symetrii geometrii — celem jest orientacja skanu z jego rzeczywistymi odchyłkami.
