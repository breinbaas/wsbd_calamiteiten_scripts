import shapefile
from helpers import case_insensitive_glob
from math import hypot

REFLINES_PATH = r"D:\Documents\WSBD\calamiteiten\GIS\referentielijnen"


class ReferenceLine:
    def __init__(self):
        self.name = ""
        self.points = []

    @classmethod
    def from_shape(self, filename):
        rl = ReferenceLine()
        rl.name = filename.stem
        shape = shapefile.Reader(filename)
        feature = shape.shapeRecords()[0]
        first = feature.shape.__geo_interface__
        if not first["type"] == "LineString":
            raise NotImplementedError(
                f"ReferenceLine.from_shape only handles LineString geometries but got a '{first['type']}' geometry."
            )
        rl.points = [[p[0], p[1], 0.0] for p in first["coordinates"]]

        for i in range(1, len(rl.points)):
            rl.points[i][-1] = round(
                rl.points[i - 1][-1]
                + hypot(
                    rl.points[i][0] - rl.points[i - 1][0],
                    rl.points[i][1] - rl.points[i - 1][1],
                )
            )

        return rl

    @property
    def length(self):
        return self.points[-1][-1]

    def xy_from_l(self, l):
        for i in range(1, len(self.points)):
            x1, y1, l1 = self.points[i - 1]
            x2, y2, l2 = self.points[i]

            if l1 <= l and l <= l2:
                x = x1 + (l - l1) / (l2 - l1) * (x2 - x1)
                y = y1 + (l - l1) / (l2 - l1) * (y2 - y1)
                return x, y

        raise ValueError(f"Invalid chainage {l}, min=0.0, max={self.length:.1f}")

    def coords_between(self, start, end):
        points = [self.xy_from_l(start)]
        points += [p for p in self.points if p[-1] > start and p[-1] < end]
        points += [self.xy_from_l(end)]
        return points


def get_reflines():
    refline_files = case_insensitive_glob(REFLINES_PATH, ".shp")
    reflines = [
        ReferenceLine.from_shape(refline_file) for refline_file in refline_files
    ]
    return {rl.name: rl for rl in reflines}


if __name__ == "__main__":
    reflines = get_reflines()
    print(reflines)
