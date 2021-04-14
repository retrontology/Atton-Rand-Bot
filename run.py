from atton_config import atton_config
from atton import AttonRand
import threading
import os
import logging
import logging.handlers


def main():
    config = atton_config('config.yaml.bak')
    logger = setup_logger('AttonRand')
    bot = AttonRand(config)
    try:
        bot.start()
    except:
        bot.connection.close()


def setup_logger(logname, logpath=""):
    if not logpath or logpath == "":
        logpath = os.path.join(os.path.dirname(__file__), 'logs')
    else:
        logpath = os.path.abspath(logpath)
    if not os.path.exists(logpath):
        os.mkdir(logpath)
    logger = logging.getLogger(logname)
    logger.setLevel(logging.DEBUG)
    file_handler = logging.handlers.TimedRotatingFileHandler(os.path.join(logpath, logname), when='midnight')
    stream_handler = logging.StreamHandler()
    form = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler.setFormatter(form)
    stream_handler.setFormatter(form)
    file_handler.setLevel(logging.INFO)
    stream_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger

if __name__ == "__main__":
    main()