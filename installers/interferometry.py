import os
import pathlib
import json
from collections import defaultdict


if __name__ == "__main__":
    print("Installing programm...")
    parent = pathlib.Path(__file__).parent.parent
    install_cmd = ["pip", "install", "minipti"]
    #subprocess.run(["python", "-m", "venv", f"{parent}/.venv"])
    #if platform["system"]() == "Windows":
    #    subprocess.run([fr"{parent}/.venv/Scripts/activate.bat", "&&"] + install_cmd)
    #else:
    #    subprocess.run([r"source <venv>/bin/activate", "&&"] + install_cmd)
    print("Configuring...")
    config_path = f"{parent}/minipti/gui/configs/interferometry.json"
    def factory(): return defaultdict(factory)
    config = defaultdict(factory)
    config["use"] = True
    config["GUI"]["home"]["use"] = True
    config["GUI"]["home"]["plots"]["dc_signals"] = True
    config["GUI"]["home"]["plots"]["interferometric_phase"] = True
    config["GUI"]["home"]["plots"]["pti_signal"] = False
    config["GUI"]["logging"]["console"] = False
    config["GUI"]["logging"]["file"] = True
    config["GUI"]["home"]["on_run"]["DAQ"] = True
    config["GUI"]["home"]["use_utilities"] = True
    config["GUI"]["plots"]["dc_signals"]["use"] = False
    config["GUI"]["plots"]["output_phases"]["use"] = False
    config["GUI"]["plots"]["amplitudes"]["use"] = False
    config["GUI"]["plots"]["sensitivity"]["use"] = False
    config["GUI"]["plots"]["pti_signal"]["use"] = False
    config["GUI"]["plots"]["interferometric_phase"]["use"] = False
    config["GUI"]["probe_laser"]["use"] = False
    config["GUI"]["pump_laser"]["use"] = False
    config["GUI"]["battery"]["use"] = False
    config["GUI"]["settings"]["valve"] = False
    config["GUI"]["settings"]["system"]["settings"]["interferometric"] = True
    config["GUI"]["settings"]["system"]["settings"]["response_phases"] = False
    config["GUI"]["utilities"]["plot"] = True
    config["GUI"]["utilities"]["devices"]["tec_driveres"] = False
    config["GUI"]["utilities"]["devices"]["laser_driver"] = False
    config["GUI"]["utilities"]["devices"]["daq"] = True
    with open(config_path, "w") as file:
        json.dump(config, file, indent=4)
        file.write("\n")
    username = os.getlogin()
    os.symlink("../minipti.pyw", fr"C:\Users\{username}\Desktop\MiniPTI")
    print("Finished")
