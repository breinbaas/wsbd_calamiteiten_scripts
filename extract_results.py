import shapefile
import pandas as pd

from helpers import case_insensitive_glob

PATH_RESULTS = r"D:\Documents\WSBD\calamiteiten\GIS\toetsing"

# loop alle bestand af en schrijf de resultaten als csv bestanden weg
if __name__ == "__main__":
    # get all (unique) fields
    fieldnames = []
    for filename in case_insensitive_glob(PATH_RESULTS, ".shp"):
        shape = shapefile.Reader(filename)
        fieldnames += [shape[0] for shape in shape.fields[1:]]

    fieldnames = list(set(fieldnames))
    df = pd.DataFrame({f: [] for f in fieldnames})

    # fill the dataframe
    for filename in case_insensitive_glob(PATH_RESULTS, ".shp"):
        dtcode = filename.stem.split("-")
        dtcode = f"{dtcode[0]}-{dtcode[1]}"
        shape = shapefile.Reader(filename)
        shape_fields = [shape[0] for shape in shape.fields[1:]]
        shape_fields.append("dijkcode")
        # add empty row
        s = pd.Series([None] * len(shape_fields))
        for i in range(len(shape.records())):
            s["dijkcode"] = dtcode
            rec = shape.record(i)
            for j in range(len(rec)):
                s[shape_fields[j]] = rec[j]
            df = pd.concat([df, s.to_frame().T])

    df.to_csv("output/results.csv")
