import shapefile

from get_reflines import get_reflines


# LET OP De metrering van 34-2 moet omgedraaid omdat de
# uitkomsten shape de andere kant oploopt dan de
# referentielijn

lines = open("output/results_cleared.csv", "r").readlines()

fields = lines[0].split(";")
fields = fields[3:]


PATH_SHAPE_RESULTS = (
    r"D:\Documents\WSBD\calamiteiten\GIS\toetsing_cleared\resultaten.shp"
)

reflines = get_reflines()

w = shapefile.Writer(PATH_SHAPE_RESULTS)
for field in fields:
    w.field(field.strip(), "C", "255")


for line in [l.strip() for l in lines[1:]]:
    args = line.split(";")
    dijkcode = args[0].upper()
    van = int(float(args[1].replace(",", ".")))
    tot = int(float(args[2].replace(",", ".")))
    args = [a.strip() for a in args[3:]]
    refline = reflines[dijkcode]
    try:
        coords = refline.coords_between(van, tot)

    except Exception as e:
        print(f"Error handling line '{line}': '{e}'")
        continue

    w.line([coords])
    w.record(*args)

w.close()
