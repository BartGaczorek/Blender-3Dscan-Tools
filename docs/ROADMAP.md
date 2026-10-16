# Kolejne etapy — sugerowane Issues

1. **Pierwszy test w Blenderze i regresje.** Uruchomić Actions. Sprawdzić instalację ZIP-a i Undo, poprawność eksportu STL, pamięć i zachowanie na 3–5 reprezentatywnych skanach: płaska baza, element prawie symetryczny, duży asymetryczny występ, brak płaskich ścianek. Porównać ręczną orientację z automatyczną; ustalić akceptowalny błąd kątowy i liniowy.
2. **Wskazanie bazy.** Region z zaznaczonych trójkątów → odporny fit płaszczyzny. Kilka propozycji z area/odchyłką, przyciski góra/dół i przód/tył. Opcja: środek układu lub podstawa na Z=0. Oddzielić wybór osi symetrii od wyboru bazy.
3. **Wiarygodność symetrii.** Maski pomijanych fragmentów, kara za małe obustronne pokrycie, normalne powierzchni, porównanie najlepszych kandydatów. Wykrywać niejednoznaczność zamiast arbitralnie nazywać wynik pewnym. Metryki przeliczać po korekcie ręcznej.
4. **Wydajność i responsywność.** Pomiar czasu/RAM na 1/5/15 mln trójkątów, lepszy proxy z kontrolą błędu, obliczenia etapowe i bezpieczne anulowanie. Nie wywoływać bpy z dowolnych wątków. W razie potrzeby izolowany proces Blendera.
5. **Decymacja z kontrolą odchyłki.** Pomiar dwustronnych odległości próbka→powierzchnia, ochrona granic/ostrych krawędzi, raport w jednostkach fizycznych, testy otworów i detali.
6. **Automatyzacja produkcyjna.** Własne presety części, eksport STL i JSON, jawne jednostki, wsadowy tryb CLI z timeoutem, raport błędów per plik. Automatyczna akceptacja dopiero po kalibracji progów na własnym zestawie skanów.

Kryterium akceptacji v0.1: działa instalacja, analiza, lustro i utworzenie wyniku; oryginał niezmieniony, transformacja wynikowa zatwierdzona, liczba trójkątów raportowana; błędne orientacje da się skorygować ręcznie. Brak obietnicy stuprocentowo automatycznego ustawienia dowolnego skanu.
