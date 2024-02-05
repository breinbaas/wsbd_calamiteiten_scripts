from pathlib import Path
import geolib as gl
import matplotlib.pyplot as plt
from math import tan, radians
from leveelogic.deltares.dstability import DStability
from leveelogic.helpers import case_insensitive_glob
import numpy as np
from leveelogic.deltares.algorithms.algorithm_berm_wsbd import AlgorithmBermWSBD
import logging

PATH_TO_STIXFILES = "E:\\Documents\\Klanten\\WSBD\\Calamiteiten\\StixFiles"
OUTPUT_PATH = "E:\\Documents\\Klanten\\WSBD\\Calamiteiten\\Output\\Bermen"
CALCULATIONS_PATH = (
    "E:\\Documents\\Klanten\\WSBD\\Calamiteiten\\Output\\Bermen\\calculations"
)
LOG_FILE = "E:\\Documents\\Klanten\\WSBD\\Calamiteiten\\Output\\Bermen\\bermen.log"


SF_REQUIRED = 1.20
MIN_BERM_HEIGHT = 0.5
MIN_BERM_WIDTH = 2.0
SLOPE_TOP = 10
SLOPE_BOTTOM = 2
WIDTH_STEP = 1.0
HEIGHT_STEP = 0.25
MAX_WIDTH = 10.0
MAX_HEIGHT = 2.0
BERM_MATERIAAL = "Dijksmateriaal (klei)_K4_Su"
SLOOT_MATERIAAL = "Dijksmateriaal (klei)_K4_Su"

logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    format="%(asctime)s,%(msecs)d %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)

files = case_insensitive_glob(PATH_TO_STIXFILES, ".stix")


for file in files:
    logging.info(f"Handling file '{file}'")
    filename = Path(file).stem
    dtcode, s = filename.split("_")
    start_chainage = float(s.split("-")[0])
    end_chainage = float(s.split("-")[1].replace(".stix", ""))

    # models = []

    # in a batch calculate
    # the current SF (no berm)
    # the SF with the smallest berm
    # the SF with the largest berm
    # the SF with a filled ditch (if a ditch is present)

    ## INITIAL MODEL
    ds_initial = DStability.from_stix(file)
    ds_initial.model.filename = "ini.stix"

    ## MINIMAL BERM
    ds_min_berm = DStability.from_stix(file)
    w = MIN_BERM_WIDTH
    h = MIN_BERM_HEIGHT
    alg = AlgorithmBermWSBD(
        ds=ds_min_berm,
        soilcode=BERM_MATERIAAL,
        height=h,
        width=w,
        slope_bottom=SLOPE_BOTTOM,
        slope_top=SLOPE_TOP,
    )
    try:
        ds_min_berm = alg.execute()
    except Exception as e:
        logging.info(f"Error creating berm with width={w:.2f} and height={h:.2f}.")
        continue

    ds_min_berm.model.filename = "min.stix"

    ## MAXIMUM BERM
    ds_max_berm = DStability.from_stix(file)
    w = MAX_WIDTH
    h = MAX_HEIGHT
    alg = AlgorithmBermWSBD(
        ds=ds_max_berm,
        soilcode=BERM_MATERIAAL,
        height=h,
        width=w,
        slope_bottom=SLOPE_BOTTOM,
        slope_top=SLOPE_TOP,
    )
    try:
        ds_max_berm = alg.execute()
    except Exception as e:
        logging.info(f"Error creating berm with width={w:.2f} and height={h:.2f}.")
        continue
    ds_max_berm.model.filename = "max.stix"

    models = [ds_initial.model, ds_min_berm.model, ds_max_berm.model]

    ## FILLED DITCH
    if ds_initial.has_ditch:
        ds_ditch = DStability.from_stix(file)

        alg = AlgorithmBermWSBD(
            ds=ds_ditch,
            fill_ditch=True,
            ditch_soilcode=SLOOT_MATERIAAL,
        )
        try:
            ds_ditch = alg.execute()
        except Exception as e:
            logging.info(f"Error filling ditch, '{e}'.")
            continue
        ds_ditch.model.filename = "ditch.stix"
        models.append(ds_ditch.model)

    bm = gl.BaseModelList(models=models)

    newbm = bm.execute(Path(CALCULATIONS_PATH), nprocesses=20)
    try:
        result = {m.filename.stem: m.output[0].FactorOfSafety for m in newbm.models}
    except Exception as e:
        logging.info(f"Error getting the results of the calculations; '{e}'.")
        continue

    # check if the intial SF is already high enough
    if result["ini"] > SF_REQUIRED:
        logging.info(
            f"The initial safety factor ({result['ini']:.3f}) is already higher than the required safety factor ({SF_REQUIRED:.3f})"
        )
        ds_initial.serialize(
            Path(CALCULATIONS_PATH) / f"solution_{filename}_0.00_0.00.stix"
        )
        continue
    # check if the filled ditch leads to a solution (if there is a ditch to be filled!)
    elif ds_initial.has_ditch and result["ditch"] > SF_REQUIRED:
        logging.info(
            f"The safety factor with a filled ditch ({result['ditch']:.3f}) is higher than the required safety factor ({SF_REQUIRED:.3f})"
        )
        ds_initial.serialize(
            Path(CALCULATIONS_PATH) / f"solution_{filename}_filled_ditch.stix"
        )
        continue
    # check if the smallest berm leads to a solution
    elif result["min"] > SF_REQUIRED:
        logging.info(
            f"The safety factor with the minimum berm ({result['min']:.3f}) is higher than the required safety factor ({SF_REQUIRED:.3f})"
        )
        ds_min_berm.serialize(
            Path(CALCULATIONS_PATH)
            / f"solution_{filename}_{MIN_BERM_WIDTH:.2f}_{MIN_BERM_HEIGHT:.2f}.stix"
        )
        continue
    # check if we need to adjust the berm size because the max berm is still not good enough
    elif result["max"] < SF_REQUIRED:
        logging.info(
            f"The safety factor with the maximum berm ({result['max']:.3f}) is lower than the required safety factor ({SF_REQUIRED:.3f}). No solution with these parameters."
        )
        ds_max_berm.serialize(
            Path(CALCULATIONS_PATH)
            / f"NO_solution_{filename}_{MAX_WIDTH:.2f}_{MAX_HEIGHT:.2f}.stix"
        )
        continue  # should be continue

    # Iterate over solutions

    # # calculate the initial safety factor
    # ds = DStability.from_stix(file)
    # sf = -1
    # try:
    #     ds.execute()
    #     sf = ds.model.output[0].FactorOfSafety
    # except Exception as e:
    #     flog.write(f"Error calculating the initial safetyfactor; '{e}'\n")
    #     continue

    # if sf >= SF_REQUIRED:
    #     ds.serialize(Path(CALCULATIONS_PATH) / f"solution_{filename}_w0.00_h0.00.stix")
    #     continue

    # # calculate the safety factor with the minimal berm
    # w = INITIAL_BERM_WIDTH
    # h = INITIAL_BERM_HEIGHT

    # ds = DStability.from_stix(file)

    # w_step = WIDTH_STEP
    # h_step = HEIGHT_STEP
    # w_max = MAX_WIDTH

    # while sf < SF_REQUIRED:
    #     print(w, h, sf, SF_REQUIRED)
    #     w += w_step
    #     if w > w_max:
    #         w = INITIAL_BERM_WIDTH
    #         h += h_step

    #     ds = DStability.from_stix(file)
    #     alg = AlgorithmBermWSBD(
    #         ds=ds,
    #         soilcode=BERM_MATERIAAL,
    #         height=h,
    #         width=w,
    #         slope_bottom=SLOPE_BOTTOM,
    #         slope_top=SLOPE_TOP,
    #     )
    #     try:
    #         ds = alg.execute()
    #         ds.model.filename = f"{filename}_{w:.2f}_{h:.2f}.stix"
    #         ds.execute()
    #         sf = ds.model.output[0].FactorOfSafety

    #     except Exception as e:
    #         flog.write(f"Error creating berm or calculating safety factor; '{e}'\n")
    #         continue

    #     if len(alg.log) > 0:
    #         flog.write("\n".join(alg.log))

    #     if sf >= SF_REQUIRED:
    #         ds.serialize(
    #             Path(CALCULATIONS_PATH) / f"solution_{filename}_{w:.2f}_{h:.2f}.stix"
    #         )

    # bm = gl.BaseModelList(models=models)
    # newbm = bm.execute(Path(CALCULATIONS_PATH), nprocesses=len(models))
    # labels = []
    # sfs = []
    # for i, model in enumerate(newbm.models):
    #     model.serialize(Path(CALCULATIONS_PATH) / model.filename)
    #     args = str(model.filename).replace(".stix", "").split("_")[-2:]
    #     w = float(args[0])
    #     h = float(args[1])
    #     labels.append(f"w={w:.2f}, h={h:.2f}")
    #     try:
    #         sfs.append(model.output[0].FactorOfSafety)
    #     except Exception as e:
    #         sfs.append(0.0)

    # flog.close()

    # fig, ax = plt.subplots()
    # fig.set_size_inches(20, 5)
    # plt.plot(labels, sfs, "o-")
    # plt.xlabel("Berm afmetingen [m]")
    # plt.ylabel("Veiligheidsfactor")
    # plt.title(
    #     f"Bermgrootte voor {dtcode} van {start_chainage:.2f}km tot {end_chainage:.2f}km"
    # )
    # plt.grid()
    # figname = f"{dtcode}_{start_chainage:.2f}-{end_chainage:.2f}.png"
    # fig.savefig(Path(OUTPUT_PATH) / figname)
