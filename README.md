# CadXpert Scan Tools — 0.2.0

Dodatek Blendera do ustawiania skanów i redukcji osobnego wyniku. Wersja 0.2 skupia się na ręcznym bazowaniu z pomocą geometrii: kopia robocza → kliknięcie ścianki → płaszczyzna XY → dopasowanie symetrii z lustrem na żywo. Oryginał pozostaje zachowany. Domyślna automatyczna orientacja jest wyłączona, ponieważ PCA/RANSAC z v0.1 nie rozpoznaje wiarygodnie intencji projektowej.

## Instalacja / aktualizacja

1. Zapisz scenę `.blend`. Usuń pomocniczy podgląd v0.1 przyciskiem dodatku; zachowaj oryginalny skan.
2. Wyłącz poprzednią wersję dodatku. W razie pozostawionych klas zrestartuj Blendera.
3. Preferences → Get Extensions → menu → Install from Disk → `dist/cadxpert_scan_tools-0.2.0.zip`. To wewnętrzny instalator, nie całe repozytorium. Jeśli Blender zgłosi istniejący identyfikator, usuń poprzednie rozszerzenie i zainstaluj nowe.
4. Włącz dodatek. Panel w widoku 3D: `N` → **Scan Tools**. Nagłówek powinien pokazywać **0.2.0**.

Blender 4.2+; lokalnie testowany na Blenderze 4.2.0 pod Linuksem. Windows, macOS i nowsze wersje wymagają osobnej weryfikacji. Obliczenia działają lokalnie. Dodatek uruchamia drugi proces z tej samej instalacji Blendera i korzysta z katalogu tymczasowego; nie instaluje pakietów i nie wysyła skanów przez sieć.

## Praca krok po kroku

### 1. Kopia robocza i postęp

Zaimportuj STL, sprawdź jednostki i zaznacz źródło w Object Mode. Źródło powinno być samodzielną lokalną siatką bez rodzica, modyfikatorów, constraints i animacji.

Ustaw **Trójkąty kopii roboczej**, domyślnie 50 000, i kliknij **Przygotuj kopię roboczą**. Powstaje lekka kopia z wycentrowanym origin; oryginał zostaje ukryty po odebraniu wyniku. Mniejszy skan nie jest zagęszczany.

Panel pokazuje bieżący etap, pasek etapów, czas pracy i **Anuluj**; `Esc` także anuluje. Decymacja oraz opcjonalne dopasowanie działają w osobnym procesie, więc obliczenia nie zajmują głównej pętli UI. Pasek przedstawia ważone etapy zadania, nie dokładny udział czasu. Blender nie udostępnia mierzalnego procentu dla natywnego Decimate: na tym etapie wyświetlany jest aktywny wskaźnik i „ETA nieznane”, a nie fikcyjne odliczanie. Dokładnego czasu pozostałego nie obiecujemy.

Ważne ograniczenie: zapis wejściowego snapshotu oraz odebranie gotowej siatki muszą wykonać się w głównym Blenderze. Przy bardzo dużym pliku mogą nadal spowodować chwilową pauzę. Anulowanie nie przerwie trwającego synchronicznego zapisu, lecz zadziała po jego zakończeniu. Potrzebne są RAM, wolne miejsce w katalogu tymczasowym i działająca ścieżka `bpy.app.binary_path`. Zamknięcie Blendera awaryjnie może pozostawić pliki tymczasowe.

### 2. Wybór płaskiej bazy

Obróć widok tak, aby widzieć dolną ściankę. Kliknij **Kliknij płaską ściankę**, następnie kliknij jej wnętrze. Lustro jest na czas wyboru ukryte, a po zakończeniu przywracane.

Region rośnie tylko po połączonych krawędziami trójkątach, z kontrolą:

- kąta normalnych względem wspólnej normalnej (domyślnie 25°);
- odległości wierzchołków od wspólnej płaszczyzny (domyślnie 0.002 przekątnej modelu).

Płaszczyzna zostaje dopasowana ponownie do regionu. Stała baza porównania ogranicza stopniowe przejście zaznaczenia po walcu, typowe dla samego porównywania sąsiadujących normalnych. Zaznaczony region jest zielony; panel pokazuje RMS i maksymalną odchyłkę oraz względny RMS. Są to wskaźniki płaskości obszaru na kopii roboczej, a nie świadectwo dokładności skanu. Wartości liniowe są w jednostkach Blendera (BU); STL nie definiuje jednostek.

Jeżeli zaznaczenie jest za małe, zwiększ próg normalnych lub grubość pasa i kliknij ponownie. Jeżeli przechodzi na krzywiznę, zmniejsz tolerancje. Region zależy od klikniętego miejsca i spójności siatki. Niepołączone fragmenty pozostają osobne.

Alternatywa: wybierz niebieską kopię, `Tab` → Edit Mode → zaznacz ścianki fragmentu (np. Circle Select) → **Płaszczyzna z zaznaczonych ścianek**. Dodatek dopasuje płaszczyznę do całego zaznaczenia i wróci do Object Mode. W Edit Mode zaznaczaj, ale nie przebudowuj geometrii podglądu — zmiany jego geometrii nie przechodzą na oryginalny wynik.

Nie ma jeszcze automatycznej listy wszystkich face groups ani rankingu wszystkich ścianek. Wersja 0.2 robi interaktywne rozrastanie jednej wskazanej grupy.

### 3. Wyrównanie i lustro na żywo

Wybierz **-Z (dolna ścianka)** lub **+Z (górna ścianka)** i kliknij **Wyrównaj bazę do XY / Z=0**. Dopasowana płaszczyzna trafia w Z=0. Wybór kierunku opiera się na windingu siatki; jeśli część stoi do góry nogami, zmień kierunek i wyrównaj ponownie.

Lustro uruchamia się automatycznie po przygotowaniu kopii. **Pokaż / ukryj** steruje jego widocznością. Niebieski obiekt roboczy i pomarańczowe odbicie nakładają się podczas `G`, `R` i `S`, bez klikania odświeżania. Odbicie jest względem stałej globalnej płaszczyzny **X=0**, niezależnie od origin i kolejności obrotów. Odbicie nie jest przeznaczone do edycji ani eksportu.

Po ustaleniu dolnej bazy do dopracowania symetrii używaj głównie **G X** i **R Z**: zachowują płaszczyznę XY, pozwalając ustawić symetrię względem X=0. Swobodne obroty X/Y mogą ponownie przechylić podstawę — wtedy wyrównaj ją ponownie. Unikaj `S`, jeśli rozmiar skanu ma pozostać niezmieniony.

W Solid Shading ustawiane są kolory obiektów. Lustro współdzieli tę samą lekką siatkę: nie powiela milionów trójkątów ani nie przebudowuje geometrii podczas przeciągania. Odbicie nie jest naprawianiem ani wymuszaniem symetrii oryginalnej geometrii.

### 4. Wynik

Ustaw **Docelowe trójkąty**, domyślnie 1 000 000, i kliknij **Akceptuj i utwórz wynik**. Drugi proces bierze oryginalną geometrię, stosuje pełne przygotowanie i ręczne ustawienie kopii, a następnie redukuje do przybliżonego celu. Powstaje `_READY` z zatwierdzoną macierzą obiektu. Oryginalna siatka i transformacje źródła pozostają zachowane.

Raport jest w Text Editorze (`_READY_report.json`). Zaznacz wyłącznie `_READY` i eksportuj STL z opcją zaznaczonych obiektów. Przycisk **Usuń podgląd / wróć do źródła** usuwa pomocnicze obiekty, zachowując już utworzony wynik.

Nie zmieniaj źródła w trakcie pracy. Kontrola macierzy i liczby elementów nie wykrywa wszystkich możliwych edycji współrzędnych. W razie zmiany źródła przygotuj kopię od początku. Decymacja nadal nie mierzy odchyłki wymiarowej; obejrzyj otwory, krawędzie i drobne cechy.

## GitHub — aktualizacja istniejącego repozytorium

Nie trzeba tworzyć nowego repozytorium ani instalować integracji z ChatGPT.

1. Rozpakuj nową paczkę. W istniejącym repozytorium użyj **Add file → Upload files** i prześlij zawartość `scan_tools/`, `tests/`, `docs/` oraz pliki główne, zachowując foldery.
2. Nie przesyłaj katalogu `dist/` ani plików `.blend`/STL.
3. Zaktualizuj również `.github/workflows/ci.yml`. Jeśli upload ukrytego folderu nie zadziała, otwórz istniejący plik na GitHubie → ołówek → wklej zawartość nowego `ci.yml`.
4. Commit najlepiej na nowej gałęzi, np. `feature/scan-tools-v020`, i Pull Request do `main`.
5. Workflow testuje matematykę, walidację rozszerzenia, integrację Blendera oraz modalny UI. Po zielonym wykonaniu pobierz artifact `cadxpert-scan-tools-extension`.
6. Artifact zawiera wewnętrzny instalacyjny ZIP. Wersja w nagłówku panelu i manifeście powinna być 0.2.0.

W paczce jest też `UPDATE-v0.2.0.patch`. W Codespaces, po przesłaniu tego pliku do głównego katalogu repozytorium, możesz użyć:

```bash
git switch -c feature/scan-tools-v020
git apply --check UPDATE-v0.2.0.patch
git apply UPDATE-v0.2.0.patch
```

Patch jest względem pierwotnej paczki v0.1.0. Jeśli repo było zmienione, `--check` może zgłosić konflikt; nie wymuszaj wtedy aplikacji. Po zastosowaniu sprawdź zmiany, commituj i utwórz PR. Sam patch nie musi być commitowany.

## Testy / budowanie

```bash
python -m pip install numpy scipy
python -m unittest discover -s tests -p 'test_*.py' -v
blender --command extension validate scan_tools
blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_features.py
# Test rzeczywistego UI pod Linuksem (wymaga Xvfb):
xvfb-run -a blender --enable-event-simulate --factory-startup --python-exit-code 1 --python tests/blender_ui.py
python scripts/build.py
```

Kod: GPL-3.0-or-later. Skany pozostają własnością użytkownika. `.gitignore` nie zabezpiecza przed ręcznym przesłaniem poufnego skanu przez stronę GitHuba.
