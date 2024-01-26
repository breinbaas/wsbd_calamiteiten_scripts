* Heeft het weghalen van de stages gevolgen voor de POP?
* Vergelijk uitkomsten tussen originele berekening en aangepaste (leeggemaakte) berekening en kijk of POP invloed heeft
* WNET - we reageren nu alleen op 1 type ondergrond combi (WNet creator), we moeten vastleggen als we een ander scenario tegenkomen of code schrijven die dat scenario opvangt
* Check of bij PL of Berm de uitkomsten binnen de grid vallen of dat deze toch mee moet bewegen
* BRAINSTORM - kunnen we wat met de thresholds die opgeslagen zijn?
* ipv ACOE lijnen kunnen we de 6 indelingen conform de handleiding toevoegen aan de FC grafieken -> Rik stuurt onderverdeling, zie mail 26-1-2024 15:04 of doc/kennis/bijlage3 tabel 2.3
* parameters.csv voor bermem waarin de limieten (hoogte en max x waarde) opgesteld kunnen worden
* nieuw idee -> berm iteratie, voor laagste h -> maak min b en max b, bereken SF, als de vereiste SF tussen de waardes valt dan interpoleren en dat als berm gebruiken, zo niet dan h omhoog en zelfde methode
* effect van slootdemping meenemen (simpel via de punten die al in het algorithme staan)