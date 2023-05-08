import logging
import threading

import minipti


def main():
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(asctime)s: %(message)s',
                        filename="pti.log", filemode="a")
    app = minipti.gui.controller.MainApplication(argv=[])
    logging.info("Started Program")
    app.exec_()
    logging.info("Program closed")


if __name__ == "__main__":
    main()
