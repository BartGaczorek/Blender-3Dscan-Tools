# CadXpert Scan Tools

Eksperymentalny dodatek do Blendera: orientacja skanów STL, dopasowanie przybliżonej symetrii i decymacja osobnego wyniku. Wersja 0.1.0 jest punktem startowym do testów na rzeczywistych skanach, nie zweryfikowanym narzędziem produkcyjnym.

Docelowe API: Blender 4.2+. Referencyjny test GitHub Actions używa 4.2.0; zgodność z nowszymi wersjami wymaga sprawdzenia. NumPy jest jedyną zależnością algorytmów w Blenderze; SciPy służy wyłącznie testom poza Blenderem. Dodatek pracuje lokalnie, bez wysyłania skanów.

## Szybki start

1. Rozpakuj paczkę repozytorium. W `dist/` znajduje się osobny instalacyjny `cadxpert_scan_tools-0.1.0.zip`.
2. Blender → Edit → Preferences → Get Extensions → menu w prawym górnym rogu → Install from Disk. Wskaż **instalacyjny ZIP**, a nie paczkę całego repozytorium. Włącz dodatek, jeżeli nie został włączony automatycznie.
3. File → Import → STL. Jednostki i skalę importu ustaw świadomie: STL nie zapisuje jednostki długości.
4. Zaznacz skan w Object Mode. W widoku 3D naciśnij `N` → **Scan Tools**.
5. Zaznacz „Szukaj symetrii” tylko dla części, dla których ma to sens. Opcjonalnie wybierz przybliżoną normalną symetrii w bieżącym układzie świata (X/Y/Z), zamiast trzech startów PCA.
6. Kliknij **Analizuj zaznaczony skan**. Oryginał zostanie ukryty; podgląd bazuje na kopii do około 100 tys. trójkątów.
7. Kliknij **Odśwież lustro kontrolne X=0**. Obejrzyj nałożenie niebieskiej i pomarańczowej siatki w Solid Shading. Obracaj/przesuwaj niebieski obiekt jak zwykle (`R`, `G`); po każdej korekcie odśwież lustro. Lustro w v0.1 jest statyczne.
8. Oceń widoki ortogonalne. Możesz obrócić podgląd o 180° wokół X lub Z, aby zamienić górę/dół lub przód/tył przy zachowaniu płaszczyzny symetrii X=0. Obrót wokół Z o 90° zmienia docelową oś symetrii — lustro X przestaje wtedy być właściwym testem.
9. Ustaw cel, domyślnie 1 000 000 trójkątów, i kliknij **Akceptuj i utwórz wynik**. Powstaje `NAZWA_READY` na podstawie oryginału, z zatwierdzonym przekształceniem i redukcją. Mniejszy skan nie jest sztucznie zagęszczany.
10. Zaznacz wyłącznie wynik → File → Export → STL → zaznaczone obiekty. Raport JSON znajdziesz w Text Editorze Blendera (`NAZWA_READY_report.json`).

Przycisk **Usuń podgląd / wróć do oryginału** usuwa pomocnicze obiekty i pokazuje źródło; zachowuje już utworzony wynik. Operacje mają Undo. Nie edytuj geometrii podglądu w Edit Mode — wynik uwzględnia jedynie jego transformację obiektową. Nie zmieniaj też źródła pomiędzy analizą a akceptacją. Po takiej zmianie ponów analizę.

## Co jest zaimplementowane

- Niezależna kopia do analizy; oryginalna siatka i jej transformacje pozostają zachowane.
- Obliczenia na próbkach losowanych proporcjonalnie do powierzchni trójkątów, nie do zagęszczenia wierzchołków.
- PCA jako orientacja startowa, RANSAC + dopasowanie najmniejszych kwadratów jako przybliżona płaska ścianka.
- Dopasowanie normalnej i przesunięcia płaszczyzny symetrii do siatki roboczej przez odległości do powierzchni BVH.
- Odrzucenie domyślnie 20% największych reszt w funkcji celu; nie jest to automatyczne rozpoznanie semantyczne asymetrycznych detali.
- Ustawienie wybranej symetrii jako X=0. Płaska ścianka wyznacza kierunek Z w pozostałym stopniu swobody, o ile nie koliduje z normalną symetrii.
- Statyczne lustro kontrolne z poprawionym windingiem trójkątów.
- Osobny wynik, redukcja Decimate Collapse, raport, testy algorytmów i workflow CI.

## Czego v0.1 jeszcze nie robi

- Nie przedstawia listy wielu ścianek i wielu rozwiązań do wyboru. RANSAC zwraca jedną propozycję; może ona być zła, zwłaszcza na krzywiznach.
- Nie ma wskazywania obszaru bazowego, wykluczania fragmentów, batch processing ani automatycznego eksportu.
- Nie sprawdza tolerancji wymiarowej po decymacji. Cel liczby trójkątów jest przybliżony; zachowanie otworów i krawędzi trzeba obejrzeć.
- Nie wymusza kontaktu podstawy z Z=0: środek próbkowanej powierzchni trafia w okolice początku układu, a płaszczyzna symetrii dokładnie w X=0.
- Nie rozpoznaje intencji projektowej. Kula, walec, element z wieloma symetriami, ubytki skanu czy duże asymetryczne fragmenty mogą dać niejednoznaczny wynik.
- Analiza jest synchroniczna i może blokować interfejs. Natywna decymacja wymaga chwilowo kopii pełnej siatki; bardzo duży skan wymaga odpowiedniej pamięci RAM.
- Przyjmuje samodzielny obiekt siatkowy bez rodzica, modyfikatorów, constraints i animacji. Nie naprawia dziur, non-manifold ani błędów skanu.
- Metryki raportu opisują dopasowanie automatyczne na kopii roboczej, przed ręczną korektą. RMS/P95 nie są certyfikatem jakości ani dokładności wymiarowej.

## Rozwój całkowicie przez GitHub

Nie utworzyliśmy zdalnego repozytorium w Twoim koncie. Poniższa procedura nie wymaga lokalnej instalacji Gita ani VS Code.

1. Na GitHubie utwórz **prywatne** repozytorium, np. `cadxpert-scan-tools`, z README.
2. Rozpakuj tę paczkę, wejdź do katalogu `cadxpert-scan-tools` i przez **Add file → Upload files** prześlij jego zawartość bez dodatkowego katalogu nadrzędnego. Uwzględnij `.github/`, `.gitignore` i `AGENTS.md`. Katalogu `dist/` nie trzeba commitować — będzie budowany automatycznie.
3. Commituj zmiany. W **Actions** odszukaj „Test and build Blender extension”. Workflow uruchamia testy, test Blendera i tworzy instalacyjny ZIP. Jeśli workflow nie jest widoczny, sprawdź, czy `.github/workflows/ci.yml` rzeczywiście trafił do repozytorium i czy Actions są włączone.
4. Po zielonym zakończeniu pobierz artifact `cadxpert-scan-tools-extension`. Rozpakuj zewnętrzne archiwum artifactu; wewnętrzny ZIP to instalator Blendera.
5. Każdą kolejną zmianę opisuj jako Issue. Edycję rób przez edytor GitHuba lub **Code → Codespaces → Create codespace on main**. Pracuj na osobnej gałęzi i otwieraj Pull Request; po testach scalaj do `main`.
6. Przykładowe polecenie do agenta programującego w repozytorium: „Przeczytaj AGENTS.md i docs/ROADMAP.md. Zrealizuj etap 1: wybór ścianki z zaznaczonych trójkątów. Dodaj test na zaszumionej płaszczyźnie. Nie zmieniaj oryginalnego skanu.”
7. Testy matematyczne i pakowanie wykonują się na GitHubie. Ocenę wizualną oraz obsługę własnych dużych STL wykonujesz w lokalnym Blenderze; zwykły edytor GitHuba nie uruchamia jego viewportu.
8. Po udanym teście zaakceptowanej wersji utwórz tag/release `v0.1.0` i dołącz instalacyjny ZIP. Nie włączono automatycznego publikowania release'ów.

Nie umieszczaj poufnych skanów w Git. `.gitignore` pomaga przy pracy przez Git/Codespaces, ale nie blokuje ręcznego uploadu przez stronę. Kod paczki jest GPL-3.0-or-later, zgodnie z manifestem rozszerzenia; licencja nie zmienia własności skanów.

## Testy i budowanie poza GitHubem (opcjonalne)

```bash
python -m pip install numpy scipy
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/build.py
blender --command extension validate scan_tools
blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
```

Budowanie wymaga Python 3.11+ (tomllib). Blender korzysta z własnego Pythona. W środowisku przygotowania paczki przeszło 5 testów matematycznych; nie było zainstalowanego Blendera. Test integracyjny i walidacja manifestu są przygotowane do uruchomienia w Actions; nie należy traktować ich jako już zaliczonych.

Szczegółowy opis automatyki: [docs/ALGORITHM.md](docs/ALGORITHM.md). Kolejność dalszej pracy: [docs/ROADMAP.md](docs/ROADMAP.md).
