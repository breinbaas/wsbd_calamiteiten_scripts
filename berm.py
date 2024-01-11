from pathlib import Path
import geolib as gl
import matplotlib.pyplot as plt

from leveelogic.deltares.dstability import DStability
from leveelogic.helpers import case_insensitive_glob

from leveelogic.deltares.algorithms.algorithm_berm_wsbd import AlgorithmBermWSBD

PATH_TO_STIXFILES = (
    "C:\\Users\\brein\\Documents\\Klanten\\WSBD\\Calamiteiten\\StixFiles"
)
OUTPUT_PATH = "C:\\Users\\brein\\Documents\\Klanten\\WSBD\\Calamiteiten\\Output\\Bermen"
CALCULATIONS_PATH = "C:\\Users\\brein\\Documents\\Klanten\\WSBD\\Calamiteiten\\Output\\Bermen\\calculations"

SF_REQUIRED = 1.0
INITIAL_BERM_HEIGHT = 1.0
INITIAL_BERM_WIDTH = 3.0
SLOPE_TOP = 10
SLOPE_BOTTOM = 2
HEIGHT_STEP = 0.2
BERM_MATERIAAL = "Dijksmateriaal (klei)_K4_Su"


files = case_insensitive_glob(PATH_TO_STIXFILES, ".stix")

for file in files:
    filename = Path(file).stem
    dtcode, s = filename.split("_")
    start_chainage = float(s.split("-")[0])
    end_chainage = float(s.split("-")[1].replace(".stix", ""))

    flog = open(Path(OUTPUT_PATH) / f"{filename}.log", "w")

    ds = DStability.from_stix(file)

    alg = AlgorithmBermWSBD(
        ds=ds,
        soilcode=BERM_MATERIAAL,
        initial_height=INITIAL_BERM_HEIGHT,
        initial_width=INITIAL_BERM_WIDTH,
        height_step=HEIGHT_STEP,
        slope_bottom=SLOPE_BOTTOM,
        slope_top=SLOPE_TOP,
    )
    dss = alg.execute_multiple_results()

    if len(alg.log) > 0:
        flog.write("\n".join(alg.log))

    bm = gl.BaseModelList(models=[ds.model for ds in dss])
    newbm = bm.execute(Path(CALCULATIONS_PATH), nprocesses=len(dss))
    labels = []
    sfs = []
    for i, model in enumerate(newbm.models):
        model.serialize(Path(CALCULATIONS_PATH) / model.filename)
        args = str(model.filename).replace(".stix", "").split("_")[-2:]
        w = float(args[0][1:])
        h = float(args[1][1:])
        labels.append(f"w={w:.2f}, h={h:.2f}")
        sfs.append(model.output[0].FactorOfSafety)

    flog.close()

    fig, ax = plt.subplots()
    fig.set_size_inches(20, 5)
    plt.plot(labels, sfs, "o-")
    plt.xlabel("Berm afmetingen [m]")
    plt.ylabel("Veiligheidsfactor")
    plt.title(
        f"Bermgrootte voor {dtcode} van {start_chainage:.2f}km tot {end_chainage:.2f}km"
    )
    plt.grid()
    figname = f"{dtcode}_{start_chainage:.2f}-{end_chainage:.2f}.png"
    fig.savefig(Path(OUTPUT_PATH) / figname)
