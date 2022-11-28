import logging

import gui


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(asctime)s: %(message)s', filename="pti.log",
                        filemode="a")
    app = gui.Controller(argv=[])
    logging.info("Started Program")
    app.exec()
    logging.info("Program closed")


if __name__ == "__main__":
    main()
