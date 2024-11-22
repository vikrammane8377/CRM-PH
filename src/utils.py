# src/utils.py

import logging

def setup_logging():
    logging.basicConfig(filename='logs/app.log', level=logging.INFO,
                        format='%(asctime)s:%(levelname)s:%(message)s')

def log_message(message):
    logging.info(message)

def log_error(error):
    logging.error(error)
