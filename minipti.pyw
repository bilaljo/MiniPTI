import subprocess
import platform


if __name__ == "__main__":
	if platform.system() == "Windows":
		subprocess.Popen(["pythonw", "-m", "minipti"])
	else:
		subprocess.Popen(["nohup python", "-m", "minipti", "&"])
