from pathlib import Path
import geolib as gl
from leveelogic.deltares.dstability import DStability
from leveelogic.deltares.algorithms.algorithm_berm_wsbd import AlgorithmBermWSBD
import logging
from copy import deepcopy
from settings import SF_REQUIRED
import threading
import subprocess

PATH_TO_STIXFILES = "Y:\\Documents\\Klanten\\OneDrive\\WSBD\\calamiteiten\\StixFiles"
PARAMETERS_FILE = "Y:\\Documents\\Klanten\\OneDrive\\WSBD\\calamiteiten\\StixFiles\\parameters_berm.csv"
OUTPUT_PATH = "Y:\\Documents\\Klanten\\Output\\WSBD\\Bermen"
CALCULATIONS_PATH = "Y:\\Documents\\Klanten\\Output\\WSBD\\Bermen\\calculations"
LOG_FILE = "Y:\\Documents\\Klanten\\Output\\WSBD\\Bermen\\bermen.log"
DSTABILITY_EXE = (
    "Y:\\Apps\\Deltares\\Consoles\\DStabilityConsole\\D-Stability Console.exe"
)


SLOPE_TOP = 10
SLOPE_BOTTOM = 2
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

    ds_initial = ds.copy(deep=True)
    ds_initial.model.filename = "ini.stix"

    ds_min_berm = ds.copy(deep=True)
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

    ds_min_berm.serialize(Path(CALCULATIONS_PATH) / "min.stix")
    # extra serialization for debugging purposes
    ds_min_berm.serialize(str(Path(CALCULATIONS_PATH) / f"{dtcode}_min.stix"))

    ds_max_berm = ds.copy(deep=True)
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

    ds_max_berm.serialize(Path(CALCULATIONS_PATH) / "max.stix")
    # extra serialization for debugging purposes
    ds_max_berm.serialize(str(Path(CALCULATIONS_PATH) / f"{dtcode}_max.stix"))

    ds_filled_ditch = ds.copy(deep=True)
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

    ds_filled_ditch.serialize(Path(CALCULATIONS_PATH) / "ditch.stix")
    # extra serialization for debugging purposes
    ds_filled_ditch.serialize(str(Path(CALCULATIONS_PATH) / f"{dtcode}_ditch.stix"))

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

    # apperently we have no solution yet but now we can interpolate between min and max
    # note that we use our own multithreading code because the current geolib solution is not that nice...
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

        ds_berm = ds.copy(deep=True)
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
            # extra serialization for debugging purposes
            ds_berm.serialize(
                str(Path(CALCULATIONS_PATH) / f"{dtcode}_berm_{i:0d}.stix")
            )
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
