from leveelogic.helpers import case_insensitive_glob
from leveelogic.deltares.dstability import DStability
from leveelogic.deltares.algorithms.algorithm_fc_phreatic_line_wsbd import (
    AlgorithmFCPhreaticLineWSBD,
)
from leveelogic.calculations.functions import sf_to_beta, get_model_factor
from pathlib import Path
import geolib as gl
import matplotlib.pyplot as plt

PATH_TO_STIXFILES = (
    "C:\\Users\\brein\\Documents\\Klanten\\WSBD\\Calamiteiten\\StixFiles"
)
PARAMETERS_FILE = "C:\\Users\\brein\\Documents\\Klanten\\WSBD\\Calamiteiten\\StixFiles\\parameters.csv"
OUTPUT_PATH = (
    "C:\\Users\\brein\\Documents\\Klanten\\WSBD\\Calamiteiten\\Output\\FragilityCurves"
)
CALCULATIONS_PATH = "C:\\Users\\brein\\Documents\\Klanten\\WSBD\\Calamiteiten\\Output\\FragilityCurves\\calculations"


# get the params from the csv file
param_lines = [
    l.strip() for l in open(PARAMETERS_FILE, "r").readlines() if l.strip() != ""
][1:]

flog = open(Path(OUTPUT_PATH) / "fc_plline.log", "w")
flog.write("Starting fragility curves calculations.\n")
flog.close()

# handle all files
for param_line in param_lines:
    try:
        filename, min_level, max_level, step_size = [
            p.strip() for p in param_line.split(",")
        ]
        min_level = float(min_level)
        max_level = float(max_level)
        step_size = float(step_size)

        dtcode, s = filename.split("_")
        start_chainage = float(s.split("-")[0])
        end_chainage = float(s.split("-")[1].replace(".stix", ""))

        flog = open(Path(OUTPUT_PATH) / "fc_plline.log", "a+")
        flog.write(
            f"Handling dijkcode {dtcode} from {start_chainage:.2f} to {end_chainage:.2f} with minlevel {min_level:.2f} and maxlevel {max_level:.2f}, stepsize {step_size:.2f}.\n"
        )
        flog.close()
    except Exception as e:
        flog = open(Path(OUTPUT_PATH) / "fc_plline.log", "a+")
        flog.write(
            "Invalid parameter line '{param_line}' or invalid filename '{filename}' (should be <dijkcode>_<van>-<tot>.stix), got error '{e}'\n"
        )
        flog.close()

    if step_size <= 0.0:
        flog = open(Path(OUTPUT_PATH) / "fc_plline.log", "a+")
        flog.write(f"Skipping '{filename}' because no step size is given.\n")
        flog.close()
        continue

    subdir = filename.split("_")[0]
    try:
        ds = DStability.from_stix(Path(PATH_TO_STIXFILES) / subdir / filename)

        alg = AlgorithmFCPhreaticLineWSBD(
            ds=ds, max_level=max_level, min_level=min_level, step=step_size
        )

        dss = alg.execute_multiple_results()
    except Exception as e:
        flog = open(Path(OUTPUT_PATH) / "fc_plline.log", "a+")
        flog.write(
            f"Skipping '{filename}' due to an error while running the algorithm, '{e}'.\n"
        )
        flog.close()
        continue

    fig, ax = plt.subplots()
    fig.set_size_inches(10, 5)

    waterlevels = []
    sfs = []
    betas = []

    bm = gl.BaseModelList(models=[ds.model for ds in dss])
    newbm = bm.execute(Path(CALCULATIONS_PATH), nprocesses=len(dss))
    for i, model in enumerate(newbm.models):
        outfilename = f"{Path(model.filename).stem}_{i}.stix"
        model.serialize(Path(OUTPUT_PATH) / "calculations" / outfilename)
        ds = DStability.from_stix(Path(OUTPUT_PATH) / "calculations" / outfilename)

        sf = model.output[0].FactorOfSafety
        model_factor = get_model_factor(
            model.datastructure.calculationsettings[0].AnalysisType
        )
        waterlevels.append(ds.phreatic_line.Points[0].Z)
        sfs.append(sf)
        betas.append(sf_to_beta(sf, model_factor))

    # # SINGLE THREADED CODE
    # for i, ds in enumerate(dss):
    #     ds.model.serialize(Path(CALCULATIONS_PATH) / f"{ds.name}_{i}.stix")
    #     ds.model.execute()
    #     sf = ds.model.output[0].FactorOfSafety
    #     waterlevels.append(ds.phreatic_line.Points[0].Z)
    #     sfs.append(sf)
    #     model_factor = get_model_factor(
    #         ds.model.datastructure.calculationsettings[0].AnalysisType
    #     )
    #     betas.append(sf_to_beta(sf, model_factor))

    plt.plot(waterlevels, betas, "o-")
    plt.xlabel("Water level [m]")
    plt.ylabel("Reliability index")
    plt.title(
        f"Fragility curve dijktraject {dtcode} van {start_chainage:.2f}km tot {end_chainage:.2f}km"
    )
    plt.grid()

    figname = f"{dtcode}_{start_chainage:.2f}{end_chainage:.2f}.png"
    fig.savefig(Path(OUTPUT_PATH) / figname)
