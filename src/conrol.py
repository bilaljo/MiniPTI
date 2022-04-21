from cProfile import run
import configparser
import multiprocessing as mp
import sched, time
import platform
import subprocess


def execute(task):
    if platform.system() == "Windows":
        subprocess.run(task + ".exe")
    else:
        subprocess.run(task)

def run_task(processes, process_name, task):
    processes[process_name] = mp.Process(target=execute, kwargs={"task": task})
    processes[process_name].start()

def main():
    pti_config = configparser.ConfigParser()
    pti_config.read("pti.conf")
    print(pti_config.sections())
    process = {}
    if platform.system() != "Windows":
        mp.set_start_method("fork")
    schedueler = sched.scheduler(time.time)
    schedueler.enter(float(pti_config["timing"]["phase_scan"]), 0, run_task, kwargs={"processes": process, "process_name": "phase_scan", "task": "Phase_Scan"})
    schedueler.enter(float(pti_config["timing"]["decimation"]), 0, run_task, kwargs={"processes": process, "process_name": "decimation", "task": "Decimation"})
    schedueler.enter(float(pti_config["timing"]["pti_inversion"]), float(pti_config["timing"]["decimation"]), run_task, kwargs={"processes": process, "process_name": "pti_inversion", "task": "PTI_Inversion"})
    while (True):
        schedueler.run()


if __name__ == "__main__":
    main()
