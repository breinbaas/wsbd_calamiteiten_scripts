from leveelogic.deltares.dstability import DStability
from leveelogic.deltares.algorithms.algorithm_phreatic_line import (
    AlgorithmPhreaticLine,
)
from leveelogic.calculations.functions import sf_to_beta, get_model_factor, beta_to_pf
from pathlib import Path
import geolib as gl
import matplotlib.pyplot as plt
import logging
from matplotlib.patches import Rectangle

from settings import SF_REQUIRED, P_EIS_OND_DSN, P_EIS_SIG, P_EIS_OND, P_EIS_SIG_DSN

PATH_TO_STIXFILES = "Y:\\Documents\\Klanten\\OneDrive\\WSBD\\calamiteiten\\StixFiles"
PARAMETERS_FILE = "Y:\\Documents\\Klanten\\OneDrive\\WSBD\\calamiteiten\\StixFiles\\parameters_fc_plline.csv"
OUTPUT_PATH = "Y:\\Documents\\Klanten\\Output\\WSBD\\FragilityCurves"
CALCULATIONS_PATH = (
    "Y:\\Documents\\Klanten\\Output\\WSBD\\FragilityCurves\\Calculations"
)
LOG_FILE = "Y:\\Documents\\Klanten\\Output\\WSBD\\FragilityCurves\\fc_plline.log"


logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
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

        logging.debug(
            f"Handling dijkcode {dtcode} from {start_chainage:.2f} to {end_chainage:.2f} with minlevel {min_level:.2f} and maxlevel {max_level:.2f}, stepsize {step_size:.2f}.\n"
        )
    except Exception as e:
        logging.error(
            "Invalid parameter line '{param_line}' or invalid filename '{filename}' (should be <dijkcode>_<van>-<tot>.stix), got error '{e}'\n"
        )

    if step_size <= 0.0:
        logging.info(f"Skipping '{filename}' because no step size is given.\n")
        continue

    subdir = filename.split("_")[0]
    try:
        ds = DStability.from_stix(Path(PATH_TO_STIXFILES) / subdir / filename)

        # get the right scenario (named Norm) and stage (named Norm)
        scenario_index = ds.get_scenario_index_by_label("Norm")
        if scenario_index == -1:
            logging.error("Could not find a scenario named 'Norm'")
            continue

        stage_index = ds.get_stage_index_by_label(scenario_index, "Norm")
        if stage_index == -1:
            logging.error("Could not find a stage named 'Norm'")
            continue

        ds.set_scenario_and_stage(scenario_index, stage_index)

        # get the information from the waternet
        wns = ds.waternet_settings

        river_level = min_level
        while river_level <= max_level:
            alg = AlgorithmPhreaticLine(
                ds=ds,
                add_as_new_stage=False,
                new_stage_name=f"Riverlevel={river_level:.2f}",
                river_level_mhw=3.04,  # river_level,
                river_level_ghw=wns["river_level_ghw"],
                polder_level=wns["polder_level"],
                B_offset=wns["B_offset"],
                C_offset=wns["C_offset"],
                E_offset=wns["D_offset"],
                D_offset=wns["E_offset"],
                surface_offset=0.01,
                phreatic_level_embankment_top_waterside=wns[
                    "phreatic_level_embankment_top_waterside"
                ],
                phreatic_level_embankment_top_landside=wns[
                    "phreatic_level_embankment_top_landside"
                ],
                aquifer_id=wns["aquifer_id"],
                aquifer_inside_aquitard_id=wns["aquifer_inside_aquitard_id"],
                intrusion_length=wns["intrusion_length"],
                hydraulic_head_pl2_inward=wns["hydraulic_head_pl2_inward"],
                hydraulic_head_pl2_outward=wns["hydraulic_head_pl2_outward"],
                inward_leakage_length_pl3=wns["inward_leakage_length_pl3"],
                outward_leakage_length_pl3=wns["outward_leakage_length_pl3"],
                inward_leakage_length_pl4=wns["inward_leakage_length_pl4"],
                outward_leakage_length_pl4=wns["outward_leakage_length_pl4"],
            )
            ds = alg.execute()
            ds.serialize(Path(OUTPUT_PATH) / f"{filename}_{river_level:.2f}.stix")
            river_level += step_size

        # dss = alg.execute_multiple_results()
    except Exception as e:
        logging.error(
            f"Skipping '{filename}' due to an error while running the algorithm, '{e}'.\n"
        )
        continue
    break

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
