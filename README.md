# WSBD_calamiteiten_scripts

Een verzameling scripts die tot doel hebben om op een geautomatiseerde manier de grootte en
impact van calamiteiten maatregelen mogelijk te maken.

## Installatie

### Benodigde software

* git
* python 3.11
* (bij voorkeur) VSCode
* DStability en de DStabilityConsole

#### Clone de repository

```git clone https://github.com/breinbaas/wsbd_calamiteiten_scripts.git```

#### Creeer een nieuwe virtuele omgeving

```python -m venv .venv```

#### Activeer de nieuwe virtuele omgeving

```.\.venv\Scripts\activate``` 

Let op dat je nu (.venv) in de console zou moeten zien.

#### Installeer de vereiste packages

```python -m pip install -r requirements.txt```

#### Creeer het geolib.env bestand

In de root van de directory van de code dient een ```geolib.env``` bestand te komen met de volgende instellingen (met verwijzingen naar de juiste paden);

```
CONSOLE_FOLDER="Y:\\Apps\\Deltares\\Consoles" # Dit pad moet naar de reken console wijzen
COMPANY="WSBD"
```

## Fragility curves werkwijze

De fragility curves worden gegenereerd op basis van de bestaande berekeningen waarbij de freatische waterstand wordt gevarieerd. 

De automatisering kan enkel omgaan met een berekening waarin het eerste scenario en de eerste stage gebruikt wordt. Dit houdt in dat bestaande berekeningen aangepast dienen te worden door alle overige niet relevante stages te verwijderen. 

Tevens wordt er vanuit gegaan dat de waterstanden in de berekening berekend zijn met behulp van de waternet creator. 

De berekeningen dienen in een map geplaatst te worden die overeenkomt met het dijktraject bv 34-1 of 34a-1, 35-1 etc. De naam van de berekening dient te bestaan uit het dijktraject, begin_metrering, eind_metrering bv 34-1_0.45_0.81 voor een berekening die geldt voor dijktraject 34-1 van kilometrering 0.45 tot 0.81. 

In de map waar de berekeningen komen dient een parameterbestand te komen met de volgende waarden;

```
filename,min_level,max_level,step_size
34-1_0.45-0.81.stix,2,5.5,0.5
```

* filename = naam van het bestand 
* min_level = de laagste rivier waterstand
* max_level = de hoogste rivier waterstand
* step_size = de stapgrootte waarin de waterstand opgehoogd wordt tussen de minimale en maximale waarde

In dit geval wordt voor berekening 34-1_0.45_0.81.stix een minimale rivier waterstand van NAP + 2.0m en een maximale waterstand van NAP + 5.5m gehanteerd. Er worden stappen gemaakt van 0.5m dus de berekende waterstanden zijn NAP+2, 2.5, 3, 3.5, 4, 4.5, 5 en 5.5m. De parameters kunnen eenvoudig worden bepaald door de bestaande berekening te openen en te kijken wat acceptabele waterstanden zijn. Let op dat er geen situaties voorkomen waarbij de rivierwaterstand bijvoorbeeld een kleine ophoging in het voorland snijdt of dat de rivier waterstand boven de kruin van de dijk komt. In dat geval worden de berekeningen ongeldig.

Om de randvoorwaarden te bepalen waar de dijk aan moet voldoen is het nodig om het bestand settings.py aan te vullen. De benodige invoer kan berekend worden met de sheet die Karsten gemaakt heeft.

Het python script om de fragility curves te genereren is het bestand ```fc_plline.py```. In dit bestand dienen de volgende constante waarden te worden ingevuld;

```
PATH_TO_STIXFILES = "D:\\WSBD\\Calamiteiten\\StixFiles" # locatie naar de originele (gestripte) berekeningen 
PARAMETERS_FILE = "D:\\WSBD\\Calamiteiten\\StixFiles\\parameters_fc_plline.csv" # locatie van het parameter bestand
OUTPUT_PATH = "D:\\WSBD\\Calamiteiten\\Output\\FragilityCurves" # de locatie waar de uitvoer naar toe geschreven kan worden
CALCULATIONS_PATH = "D:\\WSBD\\Calamiteiten\\Output\\FragilityCurves\\calculations" # de locatie voor de tijdelijke rekenbestanden, let op het pad moet bestaan
```

Let op dat alle paden al moeten bestaan, ze worden niet automatisch aangemaakt.

### Fragility curves uitvoer

De uitvoer van het script bestaat uit een log bestand waarin het proces en eventuele fouten gemeld worden. Per berekening wordt een grafiek gemaakt met de faalkans als functie van de rivier waterstand.

## TODO / aandachtspunten

* De waternet creator kan (nog) niet geautomatiseerd worden aangeroepen waardoor het proces nu zo goed als mogelijk geemuleerd wordt. 
* Op dit moment is enkel nog het klei op zand scenario aangepakt, er dient nagegaan te worden of dit ook goed werkt bij de overige scenarios (zand op zand, zand op klei, klei op klei)
* Sheet Karsten aan repo toevoegen

## Bermen werkwijze

### LET OP 

Bij de bermen code dient een bug in de huidige DGeolib bibliotheek te worden opgelost. Dit kan door in de virtuele omgeving naar het bestand ```.venv\Lib\site-packages\geolib\models\dstability\dstability_model.py``` te gaan de volgende regel aan te passen;

Vervang in de functie ```connect_layers``` de regel

```union = linestring1.union(linestring2)```

door

```union = linestring1.union(linestring2, grid_size=1e-3)``

Er is een pull request gemaakt om deze bug op te lossen maar deze is nog niet geimplementeerd in de huidige versie van geolib.


## TODO


