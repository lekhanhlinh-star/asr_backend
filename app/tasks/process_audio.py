import logging
import os
from asr import ASRModel
import torch
from database import SessionLocal
from celery_app import celery
from models import Task
_model_instance=None
def get_asr_model():
    global _model_instance
    if _model_instance is None:
        model_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'weights', 'whisper-large-v2-lora-zh-ct2')
        )
        weights = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'weights', 'epoch=19.ckpt')
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print("Loading ASR model on device:", device)
        _model_instance = ASRModel(model_path=model_dir, finetuned_ckpt_path= weights,device=device)
    return _model_instance
# Optional: preload model on worker start
from celery.signals import worker_process_init
@worker_process_init.connect
def init_worker(**kwargs):
    logging.info("Preloading ASR model in Celery worker...")
    get_asr_model()
    logging.info("Load finish...")


@celery.task(name="atasks.process_audio")
def process_audio(task_id: str):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logging.error("Task %s not found", task_id)
            return

        logging.info("Processing task %s", task_id)
        task.status = 2  # Processing
        db.commit()

        # Use shared model instance
        model = get_asr_model()
        if task.language=="default":
            language= "zh"
        language= task.language
        

        logging.info("Transcribing audio: %s", task.file_path)
        transcription = model.transcribe(
            task.file_path,
            int(task.speaker_number),
            language="zh",
            timestamp=True,
            punctuation=True
        )

        # Format result
        segments = []
        for line in transcription:
            if 'speaker' in line and 'text' in line:
                segments.append({
                    "bg": line['start'],
                    "ed": line['end'],
                    "onebest": line['text'].strip(),
                    "speaker": line['speaker'].strip()
                })

        task.result = segments
        task.status = 9  # Completed
        db.commit()
        logging.info("Task %s completed successfully", task_id)

    except Exception as e:
        logging.exception("Error processing task %s", task_id)
        if task:
            task.error = str(e)
            task.status = -1  # Failed
            db.commit()
    finally:
        db.close()

