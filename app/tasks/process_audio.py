import logging
import os
from asr import ASRModel
import torch
from database import SessionLocal
from celery_app import celery
from models import Task, TaskSegment
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
        
        # Update all segments to processing status
        task_segments = db.query(TaskSegment).filter(TaskSegment.task_id == task_id).all()
        for segment in task_segments:
            segment.status = 2  # Processing
        
        db.commit()

        # Use shared model instance
        model = get_asr_model()
        if task.language=="default":
            language= "zh"
        language= task.language
        
        # Get all segments for this task, ordered by segment_id
        task_segments = db.query(TaskSegment).filter(TaskSegment.task_id == task_id).order_by(TaskSegment.segment_id).all()
        
        all_segments = []
        total_duration_offset = 0
        
        if task_segments:
            # Process multiple segments
            logging.info("Processing %d segments for task %s", len(task_segments), task_id)
            
            for segment in task_segments:
                logging.info("Transcribing segment %d: %s", segment.segment_id, segment.file_path)
                segment_transcription = model.transcribe(
                    segment.file_path,
                    int(task.speaker_number),
                    language="zh",
                    timestamp=True,
                    punctuation=True
                )
                
                # Process this segment's results
                has_separate = task.has_separate if hasattr(task, 'has_separate') else False
                
                for line in segment_transcription:
                    if 'speaker' in line and 'text' in line:
                        # Handle speaker numbering according to spec
                        if not has_separate:
                            speaker_val = "0"
                        else:
                            try:
                                speaker_num = int(line['speaker'])
                                if speaker_num < 1:
                                    speaker_val = "1"
                                else:
                                    speaker_val = str(speaker_num)
                            except (ValueError, TypeError):
                                speaker_val = "1"
                        
                        # Adjust timestamps by adding offset from previous segments
                        adjusted_start = int(line['start']) + total_duration_offset
                        adjusted_end = int(line['end']) + total_duration_offset
                        
                        all_segments.append({
                            "bg": str(adjusted_start),
                            "ed": str(adjusted_end),
                            "onebest": line['text'].strip(),
                            "speaker": speaker_val
                        })
                
                # Update segment status to completed
                segment.status = 9
                
                # Calculate duration of this segment for timestamp adjustment
                if segment_transcription:
                    last_timestamp = max([int(line.get('end', 0)) for line in segment_transcription if 'end' in line], default=0)
                    total_duration_offset += last_timestamp
                    
                logging.info("Completed processing segment %d", segment.segment_id)
        else:
            # Fallback: process single file (backward compatibility)
            logging.info("No segments found, processing single file: %s", task.file_path)
            transcription = model.transcribe(
                task.file_path,
                int(task.speaker_number),
                language="zh",
                timestamp=True,
                punctuation=True
            )
            
            # Format result for single file
            has_separate = task.has_separate if hasattr(task, 'has_separate') else False
            
            for line in transcription:
                if 'speaker' in line and 'text' in line:
                    if not has_separate:
                        speaker_val = "0"
                    else:
                        try:
                            speaker_num = int(line['speaker'])
                            if speaker_num < 1:
                                speaker_val = "1"
                            else:
                                speaker_val = str(speaker_num)
                        except (ValueError, TypeError):
                            speaker_val = "1"
                    
                    all_segments.append({
                        "bg": str(line['start']),
                        "ed": str(line['end']),
                        "onebest": line['text'].strip(),
                        "speaker": speaker_val
                    })

        task.result = all_segments
        task.status = 9  # Completed
        
        # Update all segments to completed status
        task_segments = db.query(TaskSegment).filter(TaskSegment.task_id == task_id).all()
        for segment in task_segments:
            segment.status = 9  # Completed
        
        db.commit()
        logging.info("Task %s completed successfully with %d segments", task_id, len(all_segments))

    except Exception as e:
        logging.exception("Error processing task %s", task_id)
        if task:
            task.error = str(e)
            task.status = -1  # Failed
            db.commit()
    finally:
        db.close()

