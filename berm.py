from pathlib import Path
import geolib as gl
from leveelogic.deltares.dstability import DStability

from leveelogic.deltares.algorithms.algorithm_berm_wsbd import AlgorithmBermWSBD
import logging
from copy import deepcopy
from settings import SF_REQUIRED
import threading
import subprocess

PATH_TO_STIXFILES = "D:\\WSBD\\Calamiteiten\\StixFiles"
PARAMETERS_FILE = "D:\\WSBD\\Calamiteiten\\StixFiles\\parameters_berm.csv"
OUTPUT_PATH = "D:\\WSBD\\Calamiteiten\\Output\\Bermen"
CALCULATIONS_PATH = "D:\\WSBD\\Calamiteiten\\Output\\Bermen\\calculations"
LOG_FILE = "D:\\WSBD\\Calamiteiten\\Output\\Bermen\\bermen.log"
DSTABILITY_EXE = (
    "Y:\\Apps\\Deltares\\Consoles\\DStabilityConsole\\D-Stability Console.exe"
)


SLOPE_TOP = 10
SLOPE_BOTTOM = 2
WIDTH_STEP = 1.0
HEIGHT_STEP = 0.25
BERM_MATERIAAL = "Dijksmateriaal (klei)_K4_Su"
SLOOT_MATERIAAL = "Dijksmateriaal (klei)_K4_Su"
BERM_SECTIONS = 10  # de hoeveelheid bermen die we tussen min en max willen berekenen, hoe meer hoe langzamer maar ook nauwkeuriger

# get the params from the csv file
param_lines = [
    l.strip() for l in open(PARAMETERS_FILE, "r").readlines() if l.strip() != ""
][1:]

logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)


def calculate_sf(filename, result):
    subprocess.call([DSTABILITY_EXE, filename])
    ds = DStability.from_stix(filename)
    fname = Path(filename).stem

    try:
        msg = f"{filename}: {ds.model.output[0].FactorOfSafety}"
        result[fname] = ds.model.output[0].FactorOfSafety
    except Exception as e:
        msg = f"{filename}: Got error '{e}'"
        result[fname] = 0.0

    logging.info(msg)


# handle all files
for param_line in param_lines:
    try:
        filename, xmin, zmin, xmax, zmax = [p.strip() for p in param_line.split(",")]
        xmin = float(xmin)
        zmin = float(zmin)
        xmax = float(xmax)
        zmax = float(zmax)
        dtcode = filename.split("_")[0]
    except Exception as e:
        logging.error(
            f"Invalid parameter line '{param_line}' or invalid filename '{filename}' (should be <dijkcode>_<van>-<tot>.stix), got error '{e}'"
        )

    logging.info(f"Automatische bermbepaling voor bestand {filename}")
    logging.info(
        f"Opgegeven parameters xmin={xmin}, zmin={zmin}, xmax={xmax}, zmax={zmax}"
    )
    logging.info(f"Benodigde veiligheidsfactor: {SF_REQUIRED[dtcode]}")

    ds = DStability.from_stix(Path(PATH_TO_STIXFILES) / dtcode / filename)

    ds_initial = deepcopy(ds)
    ds_initial.model.filename = "ini.stix"

    ds_min_berm = deepcopy(ds)
    ds_min_berm.model.filename = "min.stix"
    alg_min = AlgorithmBermWSBD(
        ds=ds_min_berm,
        soilcode=BERM_MATERIAAL,
        fixed_x=xmin,
        fixed_z=zmin,
        slope_bottom=SLOPE_BOTTOM,
        slope_top=SLOPE_TOP,
    )
    try:
        ds_min_berm = alg_min.execute()
    except Exception as e:
        logging.info(f"Error creating berm with x={xmin:.2f} and z={zmin:.2f}, '{e}'.")
        continue

    ds_min_berm.serialize("min.stix")

    ds_max_berm = deepcopy(ds)
    ds_max_berm.model.filename = "max.stix"
    alg_max = AlgorithmBermWSBD(
        ds=ds_max_berm,
        soilcode=BERM_MATERIAAL,
        fixed_x=xmax,
        fixed_z=zmax,
        slope_bottom=SLOPE_BOTTOM,
        slope_top=SLOPE_TOP,
    )
    try:
        ds_max_berm = alg_max.execute()
    except Exception as e:
        logging.info(f"Error creating berm with x={xmax:.2f} and z={zmax:.2f}, '{e}'.")
        continue

    ds_max_berm.serialize("max.stix")

    ds_filled_ditch = deepcopy(ds)
    ds_filled_ditch.model.filename = "ditch.stix"
    alg_fill_ditch = AlgorithmBermWSBD(
        ds=ds_filled_ditch,
        fill_ditch=True,
        ditch_soilcode=SLOOT_MATERIAAL,
    )
    try:
        ds_filled_ditch = alg_fill_ditch.execute()
    except Exception as e:
        logging.info(f"Error filling ditch, '{e}'.")
        continue

    ds_filled_ditch.serialize("ditch.stix")

    # calculate these 4
    bm = gl.BaseModelList(
        models=[
            ds.model for ds in [ds_initial, ds_min_berm, ds_max_berm, ds_filled_ditch]
        ]
    )

    newbm = bm.execute(Path(CALCULATIONS_PATH), nprocesses=20)
    try:
        result = {m.filename.stem: m.output[0].FactorOfSafety for m in newbm.models}
    except Exception as e:
        logging.info(f"Error getting the results of the calculations; '{e}'.")
        continue

    logging.info(f"Initiele veiligheidsfactor: {result['ini']:.3f}")
    logging.info(f"Veiligheidsfactor bij minimale berm: {result['min']:.3f}")
    logging.info(f"Veiligheidsfactor bij maximale berm: {result['max']:.3f}")
    logging.info(f"Veiligheidsfactor bij gedempte sloot: {result['ditch']:.3f}")

    if result["ini"] >= SF_REQUIRED[dtcode]:
        logging.info(
            f"De initiele veiligheidsfactor ({result['ini']:.3f}) voldoet al aan de vereiste veiligheidsfactor ({SF_REQUIRED[dtcode]})."
        )
        continue
    if result["min"] >= SF_REQUIRED[dtcode]:
        logging.info(
            f"De veiligheidsfactor bij de minimale berm ({result['min']:.3f}) voldoet aan de vereiste veiligheidsfactor ({SF_REQUIRED[dtcode]})."
        )
        continue
    if result["max"] < SF_REQUIRED[dtcode]:
        logging.info(
            f"De veiligheidsfactor bij de maximale berm ({result['min']:.3f}) voldoet niet aan de vereiste veiligheidsfactor ({SF_REQUIRED[dtcode]}). Geen oplossing voor deze berekening."
        )
        continue
    if result["ditch"] >= SF_REQUIRED[dtcode]:
        logging.info(
            f"De veiligheidsfactor bij het dempen van de sloot ({result['min']:.3f}) voldoet aan de vereiste veiligheidsfactor ({SF_REQUIRED[dtcode]})."
        )
        continue

    # apperently we have no solition yet but now we can interpolate between min and max
    x = xmin
    z = zmin
    xstep = (xmax - xmin) / (BERM_SECTIONS + 1)
    zstep = (zmax - zmin) / (BERM_SECTIONS + 1)
    threads = []
    result = {}
    for i in range(BERM_SECTIONS):
        x += xstep
        z += zstep
        xr = round(x, 2)
        zr = round(z, 2)

        ds_berm = deepcopy(ds)
        alg_berm = AlgorithmBermWSBD(
            ds=ds_berm,
            soilcode=BERM_MATERIAAL,
            fixed_x=xr,
            fixed_z=zr,
            slope_bottom=SLOPE_BOTTOM,
            slope_top=SLOPE_TOP,
        )
        try:
            ds_berm = alg_berm.execute()
            filename = str(Path(CALCULATIONS_PATH) / f"berm_{i:0d}.stix")
            print("FN", filename)
            ds_berm.serialize(filename)
            threads.append(
                threading.Thread(target=calculate_sf, args=[filename, result])
            )
        except Exception as e:
            logging.info(f"Error creating berm with x={xr:.2f} and z={zr:.2f}, '{e}'.")
            continue

    logging.info(f"Started {len(threads)} calculations...")
    for t in threads:
        t.start()

    for t in threads:
        t.join()
    logging.info(f"Finished {len(threads)} calculations...")

    result = sorted([(k, v) for k, v in result.items()], key=lambda x: x[0])
    result = [r for r in result if r[1] > SF_REQUIRED[dtcode]]
    if len(result) == 0:
        logging.error("Geen enkele berm voldoet aan de vereiste veiligheid")
    else:
        logging.info(
            f"De berekening '{result[0][0]}' met een veiligheidsfactor van {result[0][1]:.3f} voldoet aan de vereiste veiligheid"
        )

    # bm = gl.BaseModelList(models=models)

    # newbm = bm.execute(Path(CALCULATIONS_PATH), nprocesses=20)
    # try:
    #     result = {m.filename.stem: m.output[0].FactorOfSafety for m in newbm.models}
    # except Exception as e:
    #     logging.info(f"Error getting the results of the calculations; '{e}'.")
    #     continue

    # print(result)


# files = case_insensitive_glob(PATH_TO_STIXFILES, ".stix")


# for file in files:
#     logging.info(f"Handling file '{file}'")
#     filename = Path(file).stem
#     dtcode, s = filename.split("_")
#     start_chainage = float(s.split("-")[0])
#     end_chainage = float(s.split("-")[1].replace(".stix", ""))


#     # models = []

#     # in a batch calculate
#     # the current SF (no berm)
#     # the SF with the smallest berm
#     # the SF with the largest berm
#     # the SF with a filled ditch (if a ditch is present)

#     ## INITIAL MODEL
#     ds_initial = DStability.from_stix(file)
#     ds_initial.model.filename = "ini.stix"

#     ## MINIMAL BERM
#     ds_min_berm = DStability.from_stix(file)
#     w = MIN_BERM_WIDTH
#     h = MIN_BERM_HEIGHT
#     alg = AlgorithmBermWSBD(
#         ds=ds_min_berm,
#         soilcode=BERM_MATERIAAL,
#         height=h,
#         width=w,
#         slope_bottom=SLOPE_BOTTOM,
#         slope_top=SLOPE_TOP,
#     )
#     try:
#         ds_min_berm = alg.execute()
#     except Exception as e:
#         logging.info(f"Error creating berm with width={w:.2f} and height={h:.2f}.")
#         continue

#     ds_min_berm.model.filename = "min.stix"

#     ## MAXIMUM BERM
#     ds_max_berm = DStability.from_stix(file)
#     w = MAX_WIDTH
#     h = MAX_HEIGHT
#     alg = AlgorithmBermWSBD(
#         ds=ds_max_berm,
#         soilcode=BERM_MATERIAAL,
#         height=h,
#         width=w,
#         slope_bottom=SLOPE_BOTTOM,
#         slope_top=SLOPE_TOP,
#     )
#     try:
#         ds_max_berm = alg.execute()
#     except Exception as e:
#         logging.info(f"Error creating berm with width={w:.2f} and height={h:.2f}.")
#         continue
#     ds_max_berm.model.filename = "max.stix"

#     models = [ds_initial.model, ds_min_berm.model, ds_max_berm.model]

#     ## FILLED DITCH
#     if ds_initial.has_ditch:
#         ds_ditch = DStability.from_stix(file)

#         alg = AlgorithmBermWSBD(
#             ds=ds_ditch,
#             fill_ditch=True,
#             ditch_soilcode=SLOOT_MATERIAAL,
#         )
#         try:
#             ds_ditch = alg.execute()
#         except Exception as e:
#             logging.info(f"Error filling ditch, '{e}'.")
#             continue
#         ds_ditch.model.filename = "ditch.stix"
#         models.append(ds_ditch.model)

#     bm = gl.BaseModelList(models=models)

#     newbm = bm.execute(Path(CALCULATIONS_PATH), nprocesses=20)
#     try:
#         result = {m.filename.stem: m.output[0].FactorOfSafety for m in newbm.models}
#     except Exception as e:
#         logging.info(f"Error getting the results of the calculations; '{e}'.")
#         continue

#     # check if the intial SF is already high enough
#     if result["ini"] > SF_REQUIRED:
#         logging.info(
#             f"The initial safety factor ({result['ini']:.3f}) is already higher than the required safety factor ({SF_REQUIRED:.3f})"
#         )
#         ds_initial.serialize(
#             Path(CALCULATIONS_PATH) / f"solution_{filename}_0.00_0.00.stix"
#         )
#         continue
#     # check if the filled ditch leads to a solution (if there is a ditch to be filled!)
#     elif ds_initial.has_ditch and result["ditch"] > SF_REQUIRED:
#         logging.info(
#             f"The safety factor with a filled ditch ({result['ditch']:.3f}) is higher than the required safety factor ({SF_REQUIRED:.3f})"
#         )
#         ds_initial.serialize(
#             Path(CALCULATIONS_PATH) / f"solution_{filename}_filled_ditch.stix"
#         )
#         continue
#     # check if the smallest berm leads to a solution
#     elif result["min"] > SF_REQUIRED:
#         logging.info(
#             f"The safety factor with the minimum berm ({result['min']:.3f}) is higher than the required safety factor ({SF_REQUIRED:.3f})"
#         )
#         ds_min_berm.serialize(
#             Path(CALCULATIONS_PATH)
#             / f"solution_{filename}_{MIN_BERM_WIDTH:.2f}_{MIN_BERM_HEIGHT:.2f}.stix"
#         )
#         continue
#     # check if we need to adjust the berm size because the max berm is still not good enough
#     elif result["max"] < SF_REQUIRED:
#         logging.info(
#             f"The safety factor with the maximum berm ({result['max']:.3f}) is lower than the required safety factor ({SF_REQUIRED:.3f}). No solution with these parameters."
#         )
#         ds_max_berm.serialize(
#             Path(CALCULATIONS_PATH)
#             / f"NO_solution_{filename}_{MAX_WIDTH:.2f}_{MAX_HEIGHT:.2f}.stix"
#         )
#         continue  # should be continue

#     # Iterate over solutions

#     # # calculate the initial safety factor
#     # ds = DStability.from_stix(file)
#     # sf = -1
#     # try:
#     #     ds.execute()
#     #     sf = ds.model.output[0].FactorOfSafety
#     # except Exception as e:
#     #     flog.write(f"Error calculating the initial safetyfactor; '{e}'\n")
#     #     continue

#     # if sf >= SF_REQUIRED:
#     #     ds.serialize(Path(CALCULATIONS_PATH) / f"solution_{filename}_w0.00_h0.00.stix")
#     #     continue

#     # # calculate the safety factor with the minimal berm
#     # w = INITIAL_BERM_WIDTH
#     # h = INITIAL_BERM_HEIGHT

#     # ds = DStability.from_stix(file)

#     # w_step = WIDTH_STEP
#     # h_step = HEIGHT_STEP
#     # w_max = MAX_WIDTH

#     # while sf < SF_REQUIRED:
#     #     print(w, h, sf, SF_REQUIRED)
#     #     w += w_step
#     #     if w > w_max:
#     #         w = INITIAL_BERM_WIDTH
#     #         h += h_step

#     #     ds = DStability.from_stix(file)
#     #     alg = AlgorithmBermWSBD(
#     #         ds=ds,
#     #         soilcode=BERM_MATERIAAL,
#     #         height=h,
#     #         width=w,
#     #         slope_bottom=SLOPE_BOTTOM,
#     #         slope_top=SLOPE_TOP,
#     #     )
#     #     try:
#     #         ds = alg.execute()
#     #         ds.model.filename = f"{filename}_{w:.2f}_{h:.2f}.stix"
#     #         ds.execute()
#     #         sf = ds.model.output[0].FactorOfSafety

#     #     except Exception as e:
#     #         flog.write(f"Error creating berm or calculating safety factor; '{e}'\n")
#     #         continue

#     #     if len(alg.log) > 0:
#     #         flog.write("\n".join(alg.log))

#     #     if sf >= SF_REQUIRED:
#     #         ds.serialize(
#     #             Path(CALCULATIONS_PATH) / f"solution_{filename}_{w:.2f}_{h:.2f}.stix"
#     #         )

#     # bm = gl.BaseModelList(models=models)
#     # newbm = bm.execute(Path(CALCULATIONS_PATH), nprocesses=len(models))
#     # labels = []
#     # sfs = []
#     # for i, model in enumerate(newbm.models):
#     #     model.serialize(Path(CALCULATIONS_PATH) / model.filename)
#     #     args = str(model.filename).replace(".stix", "").split("_")[-2:]
#     #     w = float(args[0])
#     #     h = float(args[1])
#     #     labels.append(f"w={w:.2f}, h={h:.2f}")
#     #     try:
#     #         sfs.append(model.output[0].FactorOfSafety)
#     #     except Exception as e:
#     #         sfs.append(0.0)

#     # flog.close()

#     # fig, ax = plt.subplots()
#     # fig.set_size_inches(20, 5)
#     # plt.plot(labels, sfs, "o-")
#     # plt.xlabel("Berm afmetingen [m]")
#     # plt.ylabel("Veiligheidsfactor")
#     # plt.title(
#     #     f"Bermgrootte voor {dtcode} van {start_chainage:.2f}km tot {end_chainage:.2f}km"
#     # )
#     # plt.grid()
#     # figname = f"{dtcode}_{start_chainage:.2f}-{end_chainage:.2f}.png"
#     # fig.savefig(Path(OUTPUT_PATH) / figname)
