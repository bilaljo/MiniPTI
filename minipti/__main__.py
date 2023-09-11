import logging
import platform
if platform.system() == "Windows":
    import ctypes

import minipti


def main():
    if platform.system() == "Windows":
        appid = u"FHNW.MiniPTI.1.9.5"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
    logging.basicConfig(level=logging.DEBUG, format="[%(threadName)s] %(levelname)s %(asctime)s: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S", filename="pti.log", filemode="a")
    logging.captureWarnings(True)
    logging.info("Started Program")
    app = minipti.gui.controller.api.MainApplication(argv=[])
    logging.info("Started Program")
    app.exec_()
    logging.info("Program closed")


if __name__ == "__main__":
    main()
