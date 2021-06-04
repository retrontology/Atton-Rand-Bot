from atton import AttonRand
from retroBot.config import config as attonConfig
import os
import logging
import logging.handlers


def main():
    config = attonConfig('config.yaml')
    logger = setup_logger('retroBot')
    bot = AttonRand(config)
    try:
        bot.start()
    except KeyboardInterrupt as e:
        logger.info(e)
        bot._active = False
        bot.logger.info(f'Shutting down...')
        bot.webhook()
        for channel in bot.channel_handlers:
            channel.webhook_stream_changed_unsubscribe()
        bot.logger.info(f'Shut down')


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
