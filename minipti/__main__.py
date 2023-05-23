import logging
from minipti import gui


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(asctime)s: %(message)s',
                        filename="pti.log", filemode="a")
    app = gui.controller.MainApplication(argv=[])
    logging.info("Started Program")
    app.exec_()
    logging.info("Program closed")


if __name__ == "__main__":
    main()
