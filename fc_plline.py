# from leveelogic.deltares.dstability import DStability
# from leveelogic.deltares.algorithms.algorithm_fc_phreatic_line_wsbd import (
#    AlgorithmFCPhreaticLineWSBD,
# )
import shutil, os
from helpers import sf_to_beta, get_model_factor, beta_to_pf, case_insensitive_glob
from pathlib import Path
from geolib.models import DStabilityModel
from geolib import BaseModelList
import matplotlib.pyplot as plt
import logging
from matplotlib.patches import Rectangle
import numpy as np

from settings import SF_REQUIRED, P_EIS_OND_DSN, P_EIS_SIG, P_EIS_OND, P_EIS_SIG_DSN

PATH_TO_STIXFILES = "Z:\\Documents\\Klanten\\OneDrive\\WSBD\\calamiteiten\\StixFiles"
PARAMETERS_FILE = "Z:\\Documents\\Klanten\\OneDrive\\WSBD\\calamiteiten\\StixFiles\\parameters_fc_plline.csv"
OUTPUT_PATH = "Z:\\Documents\\Klanten\\Output\\WSBD\\FragilityCurves"
CALCULATIONS_PATH = (
    "Z:\\Documents\\Klanten\\Output\\WSBD\\FragilityCurves\\Calculations"
)
TEMP_CALCULATIONS_PATH = (
    "Z:\\Documents\\Klanten\\Output\\WSBD\\FragilityCurves\\Calculations\\Temp"
)
LOG_FILE = "Z:\\Documents\\Klanten\\Output\\WSBD\\FragilityCurves\\fc_plline.log"
MAX_THREADS = 8  # increase if you need more threads

ADJUST_FOR_UPLIFT = True

logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)

# logging.warning("Note that adjustment for uplift is not yet implemented!")


# get the params from the csv file
param_lines = [
    l.strip() for l in open(PARAMETERS_FILE, "r").readlines() if l.strip() != ""
][1:]


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

        logging.info(
            f"Handling dijkcode {dtcode} from {start_chainage:.2f} to {end_chainage:.2f} with minlevel {min_level:.2f} and maxlevel {max_level:.2f}, stepsize {step_size:.2f}."
        )
    except Exception as e:
        logging.error(
            "Invalid parameter line '{param_line}' or invalid filename '{filename}' (should be <dijkcode>_<van>-<tot>.stix), got error '{e}'"
        )

    if step_size <= 0.0:
        logging.info(f"Skipping '{filename}' because no step size is given.")
        continue

    subdir = filename.split("_")[0]

    #############################################################
    # EXTRA CODE                                                #
    #                                                           #
    # Check the difference between the current calculation      #
    # and the one generated using the waternet creator code     #
    #############################################################
    ds_org = DStabilityModel()
    try:
        filepath = Path(PATH_TO_STIXFILES) / subdir / filename
        ds_org.parse(filepath)
        ds_org.execute()
        sf = ds_org.output[-1].FactorOfSafety
        riverlevel = ds_org.phreatic_line.Points[0].Z
        logging.info(f"Original safety factor at river level {riverlevel} = {sf:.3f}")
    except Exception as e:
        logging.error(
            f"Cannot determine the safety factor of the original calculation; {e}"
        )

    try:
        filepath = Path(PATH_TO_STIXFILES) / subdir / f"{filename}.compare.stix"
        ds_org.serialize(filepath)
        ds_compare = DStabilityModel()
        ds_compare.parse(filepath)
        ds_compare.generate_waternet(
            river_level_mhw=riverlevel, adjust_for_uplift=ADJUST_FOR_UPLIFT
        )
        ds_compare.serialize(filepath)
        ds_compare.execute()
        sf = ds_compare.output[-1].FactorOfSafety
        riverlevel = ds_compare.phreatic_line.Points[0].Z
        logging.info(f"Generated safety factor at river level {riverlevel} = {sf:.3f}")
    except Exception as e:
        logging.error(
            f"Error creating a calculation with the same riverlevel using the waternet code; {e}"
        )

    try:
        models_to_calculate = []
        for river_level in np.arange(min_level, max_level + 0.5 * step_size, step_size):
            logging.info(f"Handling river level {river_level}")
            # copy the file
            filepath = str(Path(PATH_TO_STIXFILES) / subdir / filename)
            new_filepath = str(
                Path(CALCULATIONS_PATH) / f"{filename}_{river_level}.stix"
            )
            shutil.copyfile(filepath, new_filepath)

            ds = DStabilityModel()
            ds.parse(new_filepath)
            ds.set_scenario_and_stage_by_label("Norm", "Norm")
            # TODO > uplift implementeren
            ds.generate_waternet(
                river_level_mhw=river_level, adjust_for_uplift=ADJUST_FOR_UPLIFT
            )
            ds.serialize(new_filepath)
            models_to_calculate.append(ds)
    except Exception as e:
        logging.error(
            f"Skipping '{filename}' due to an error while running the algorithm, '{e}'."
        )

    if len(models_to_calculate) == 0:
        logging.info(f"Skipping '{filename}, got 0 calculations")
        continue

    logging.info(f"Starting {len(models_to_calculate)} calculation(s)")
    bm = BaseModelList(models=models_to_calculate)
    newbm = bm.execute(Path(TEMP_CALCULATIONS_PATH), nprocesses=MAX_THREADS)
    logging.info("Calculations ready")

    plt.clf()
    fig, ax = plt.subplots()
    fig.set_size_inches(10, 5)

    waterlevels = []
    sfs = []
    betas = []
    pfs = []

    for i, model in enumerate(newbm.models):
        ds = DStabilityModel()

        try:
            river_level = float(model.filename.name.split("_")[-1].replace(".stix", ""))
            waterlevels.append(river_level)
            sf = model.output[-1].FactorOfSafety
            logging.info(f"Safety factor for river level {river_level} = {sf:.3f}")
            sfs.append(sf)
            model_factor = get_model_factor(
                model.datastructure.calculationsettings[-1].AnalysisType
            )
            beta = sf_to_beta(sf, model_factor)
            betas.append(beta)
            pfs.append(beta_to_pf(beta))

        except Exception as e:
            logging.error(
                f"Error getting safety factor from '{model.filename.name}'; '{e}'"
            )

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
    figname = f"{dtcode}_{start_chainage:.2f}_{end_chainage:.2f}.png"
    fig.savefig(Path(OUTPUT_PATH) / figname)

    # map met berekeningen leegmaken
    files = case_insensitive_glob(TEMP_CALCULATIONS_PATH, ".stix")
    for f in files:
        os.remove(f)
