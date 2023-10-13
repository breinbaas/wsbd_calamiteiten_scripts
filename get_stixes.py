from helpers import case_insensitive_glob

STIX_PATH = r"D:\Documents\WSBD\calamiteiten\Berekeningen"

TRAJECTEN = ["34-1", "34-2", "34-3", "34-4", "34-5", "34A-1", "35-1", "35-2"]


class StixFile:
    def __init__(self, leveecode, start, end, filename):
        self.leveecode = leveecode
        self.start = start
        self.end = end
        self.filename = filename

    @property
    def name(self):
        return f"{self.leveecode}_{round(self.start)}_{round(self.end)}"


def get_stixes():
    # get all stix files
    stix_files = case_insensitive_glob(STIX_PATH, ".stix")
    stixes = []
    # per file
    for stix_file in stix_files:
        # check if we have the traject name in the filename
        args = [a.upper() for a in stix_file.stem.split("_")]
        has_traject_code = len([a for a in args if a in TRAJECTEN]) > 0

        # if not report this as unparsable
        if not has_traject_code:
            print(f"Unparsable filename '{stix_file.stem}', no traject code")
            continue

        traject_code = [a for a in args if a in TRAJECTEN][0]

        # check if we have km-km in the filename
        has_km = True
        for a in args:
            try:
                args = a.split("-")
                assert (len(args)) == 2
                assert a.upper() not in TRAJECTEN
                start = float(args[0]) * 1000
                end = float(args[1]) * 1000
                has_km = True
                break
            except:
                has_km = False

        if not has_km:
            print(f"Unparsable filename '{stix_file.stem}', no chainage")
            continue

        stixes.append(StixFile(traject_code.upper(), start, end, stix_file))

    return stixes


if __name__ == "__main__":
    stixes = get_stixes()
    print(stixes)
