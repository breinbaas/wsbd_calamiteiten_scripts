import shapefile

from get_reflines import get_reflines
from get_stixes import get_stixes

PATH_SHAPE_STIXFILES = r"D:\Documents\WSBD\calamiteiten\GIS\stixfiles\stixfiles"


if __name__ == "__main__":
    stix_files = get_stixes()
    referencelines = get_reflines()

    w = shapefile.Writer(PATH_SHAPE_STIXFILES)
    w.field("dijk", "C", "255")
    # w.field("metrering", "C", "10")
    w.field("stix", "C", "255")
    for stix_file in stix_files:
        if stix_file.leveecode in referencelines.keys():
            x, y = referencelines[stix_file.leveecode].xy_from_l(
                (stix_file.start + stix_file.end) / 2.0
            )
            w.point(x, y)
            w.record(stix_file.name, stix_file.filename)

    w.close()
