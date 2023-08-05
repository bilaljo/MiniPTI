import logging


def main():
    logging.basicConfig(level=logging.DEBUG, format="[%(threadName)s] %(levelname)s %(asctime)s: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S", filename="pti.log", filemode="a")
    logging.captureWarnings(True)
    app = minipti.gui.controller.controller.MainApplication(argv=[])
    logging.info("Started Program")
    app.exec_()
    logging.info("Program closed")


if __name__ == "__main__":
    main()
