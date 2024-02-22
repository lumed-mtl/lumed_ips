import logging
import os

# create logger
current_directory = os.getcwd()
folder_path = os.path.join(current_directory, "logs")
# Create the folder if it doesn't exist
if not os.path.exists(folder_path):
    os.makedirs(folder_path)

LOG_FORMAT = (
    "%(asctime)s - %(levelname)s"
    "(%(filename)s:%(funcName)s)"
    "(%(filename)s:%(lineno)d) - "
    "%(message)s"
)

logging.basicConfig(
    filename=os.path.join(folder_path, "logger.log"),
    level=logging.DEBUG,
    format=str(LOG_FORMAT),
    filemode="w",
)
logger = logging.getLogger()

logging.debug("This is a debug message")
logging.info("This is an info message")
logging.warning("This is a warning message")
logging.error("This is an error message")
logging.critical("This is a critical message")
