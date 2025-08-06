import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(raise_error_if_not_found=True))

TOKEN = os.getenv("TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX")
FILENAME = os.getenv("FILENAME")
APPLICATION_ID = os.getenv("APPLICATION_ID")
# Добавьте сюда другие токены, ключи и ID по мере необходимости 