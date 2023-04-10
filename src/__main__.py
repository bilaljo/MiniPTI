import logging

import gui
from PyQt5.QtGui import QIcon


def main():
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(asctime)s: %(message)s', filename="pti.log",
                        filemode="a")
    app = gui.controller.MainApplication(argv=[])
    logging.info("Started Program")
    app.setWindowIcon(QIcon("gui/images/icon.png"))
    app.exec_()
    logging.info("Program closed")


if __name__ == "__main__":
    main()
