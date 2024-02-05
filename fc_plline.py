from leveelogic.helpers import case_insensitive_glob
from leveelogic.deltares.dstability import DStability
from leveelogic.deltares.algorithms.algorithm_fc_phreatic_line_wsbd import (
    AlgorithmFCPhreaticLineWSBD,
)
from leveelogic.calculations.functions import sf_to_beta, get_model_factor, beta_to_pf
from pathlib import Path
import geolib as gl
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from math import log10

from settings import SF_REQUIRED, P_EIS_OND_DSN, P_EIS_SIG, P_EIS_OND, P_EIS_SIG_DSN

PATH_TO_STIXFILES = "E:\\Documents\\Klanten\\WSBD\\Calamiteiten\\StixFiles"
PARAMETERS_FILE = (
    "E:\\Documents\\Klanten\\WSBD\\Calamiteiten\\StixFiles\\parameters.csv"
)
OUTPUT_PATH = "E:\\Documents\\Klanten\\WSBD\\Calamiteiten\\Output\\FragilityCurves"
CALCULATIONS_PATH = (
    "E:\\Documents\\Klanten\\WSBD\\Calamiteiten\\Output\\FragilityCurves\\calculations"
)


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
    pfs = []

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
        beta = sf_to_beta(sf, model_factor)
        betas.append(beta)
        pfs.append(beta_to_pf(beta))

    xmin = min(waterlevels)
    xmax = max(waterlevels)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))
    ax1.plot([xmin, xmax], [SF_REQUIRED[dtcode], SF_REQUIRED[dtcode]], "r--")
    ax1.text(
        xmin,
        SF_REQUIRED[dtcode],
        f"minimale veiligheidsfactor ({SF_REQUIRED[dtcode]:.3f})",
    )
    ax1.plot(waterlevels, sfs, "o-")
    ax1.set_xlabel("Water level [m tov NAP]")
    ax1.set_ylabel("Safety Factor")
    ax2.set_yscale("log")

    p_eis_sig = P_EIS_SIG[dtcode]
    p_eis_sig_dsn = P_EIS_SIG_DSN[dtcode]
    p_eis_ond = P_EIS_OND[dtcode]
    p_eis_ond_dsn = P_EIS_OND_DSN[dtcode]

    aIv = (
        0,
        1 / 30 * P_EIS_SIG_DSN[dtcode],
        "Iv voldoet ruim aan signaleringswaarde",
        "#00ff00",
    )
    aIIv = (
        1 / 30 * P_EIS_SIG_DSN[dtcode],
        P_EIS_SIG_DSN[dtcode],
        "IIv voldoet aan signaleringswaarde",
        "#76933c",
    )
    aIIIv = (
        P_EIS_SIG_DSN[dtcode],
        P_EIS_OND_DSN[dtcode],
        "IIIv voldoet aan de ondergrens en mogelijk de signaleringswaarde",
        "#ffff00",
    )
    aIVv = (
        P_EIS_OND_DSN[dtcode],
        P_EIS_OND[dtcode],
        "IVv voldoet mogelijk aan de ondergrens of aan de signaleringwaarde",
        "#ccc0da",
    )
    aVv = (
        P_EIS_OND[dtcode],
        30 * P_EIS_OND[dtcode],
        "Vv voldoet niet aan de ondergrens",
        "#ff9900",
    )
    aVIv = (
        30 * P_EIS_OND[dtcode],
        1,
        "VIv voldoet ruim niet aan de ondergrens",
        "#ff0000",
    )

    for top, bottom, label, color in [aIv, aIIv, aIIIv, aIVv, aVv, aVIv]:
        ax2.add_patch(
            Rectangle(
                (xmin, bottom),
                (xmax - xmin),
                (top - bottom),
                facecolor=color,
                fill=True,
            )
        )
        ax2.plot([xmin, xmax], [bottom, bottom], "k--")
        ax2.text(xmin, (top + bottom) / 2.0, label)

    ax2.plot(waterlevels, pfs, "o-")
    ax2.set_ylim(1e-8, 1.0)
    ax2.set_xlabel("Water level [m tov NAP]")
    ax2.set_ylabel("Faalkans")
    ax1.grid()
    ax2.grid()

    fig.suptitle(
        f"Fragility curve dijktraject {dtcode} van {start_chainage:.2f}km tot {end_chainage:.2f}km"
    )
    figname = f"{dtcode}_{start_chainage:.2f}{end_chainage:.2f}.png"
    fig.savefig(Path(OUTPUT_PATH) / figname)
    break
