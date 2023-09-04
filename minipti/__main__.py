import logging
import platform
if platform.system() == "Windows":
    import ctypes

import minipti

import qdarktheme


def main():
    if platform.system() == "Windows":
        appid = u"FHNW.MiniPTI.1.9.5"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
    logging.basicConfig(level=logging.DEBUG, format="[%(threadName)s] %(levelname)s %(asctime)s: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S", filename="pti.log", filemode="a")
    logging.captureWarnings(True)
    app = minipti.gui.controller.api.MainApplication(argv=[])
    qdarktheme.setup_theme()
    app.setStyleSheet(qdarktheme.load_stylesheet())
    logging.info("Started Program")
    app.exec_()
    logging.info("Program closed")


if __name__ == "__main__":
    main()
