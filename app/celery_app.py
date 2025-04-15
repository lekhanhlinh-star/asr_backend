import os
from celery import Celery
import sys
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()
# Add the parent directory of this file to PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Đọc URL từ .env
BROKER_URL = os.getenv("BROKER_URL")
BACKEND_URL = os.getenv("BACKEND_URL")
celery = Celery(
    "asr",
    broker=BROKER_URL,
    backend=BACKEND_URL ,
)

# If your tasks live in tasks.py in the same folder:
celery.conf.imports = ("tasks.process_audio",)
