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
        
        # Validate segment completeness and order
        if task_segments:
            expected_segments = task.total_segments
            actual_segments = len(task_segments)
            
            # Check if we have the right number of segments
            if actual_segments != expected_segments:
                error_msg = f"Segment count mismatch: expected {expected_segments}, got {actual_segments}"
                logging.error(error_msg)
                task.error = error_msg
                task.status = -1
                db.commit()
                return
            
            # Check if segments are in correct order (1, 2, 3, ...)
            for i, segment in enumerate(task_segments):
                expected_id = i + 1
                if segment.segment_id != expected_id:
                    error_msg = f"Segment order error: expected segment_id {expected_id}, got {segment.segment_id}"
                    logging.error(error_msg)
                    task.error = error_msg
                    task.status = -1
                    db.commit()
                    return
            
            logging.info("✅ Segment validation passed: %d segments in correct order", actual_segments)
        
        all_segments = []
        total_duration_offset = 0
        
        if task_segments:
            # Process multiple segments
            logging.info("🚀 Processing %d segments for task %s", len(task_segments), task_id)
            
            for segment in task_segments:
                logging.info("🎵 Transcribing segment %d: %s", segment.segment_id, segment.file_path)
                segment_transcription = model.transcribe(
                    segment.file_path,
                    int(task.speaker_number),
                    language="zh",
                    timestamp=True,
                    punctuation=True
                )
                
                logging.info("📝 Segment %d returned %d lines", segment.segment_id, len(segment_transcription) if segment_transcription else 0)
                
                # Process this segment's results
                has_separate = task.has_separate if hasattr(task, 'has_separate') else False
                segment_result_count = 0
                
                for line in segment_transcription:
                    if 'speaker' in line and 'text' in line:
                        # Handle speaker numbering according to spec
                        if not has_separate:
                            speaker_val = "0"
                        else:
                            try:
                                speaker_num = int(line["speaker"].split("_")[-1])
                                if speaker_num < 1:
                                    speaker_val = "1"
                                else:
                                    speaker_val = str(speaker_num)
                            except (ValueError, TypeError):
                                speaker_val = "1"
                        
                        # Adjust timestamps by adding offset from previous segments
                        original_start = int(line['start'])
                        original_end = int(line['end'])
                        adjusted_start = original_start + total_duration_offset
                        adjusted_end = original_end + total_duration_offset
                        
                        logging.debug("⏱️ Segment %d: Original [%d-%d] -> Adjusted [%d-%d] (offset: %d)", 
                                    segment.segment_id, original_start, original_end, 
                                    adjusted_start, adjusted_end, total_duration_offset)
                        
                        all_segments.append({
                            "bg": str(adjusted_start),
                            "ed": str(adjusted_end),
                            "onebest": line['text'].strip(),
                            "speaker": speaker_val
                        })
                        segment_result_count += 1
                
                logging.info("✅ Segment %d processed: %d results added", segment.segment_id, segment_result_count)
                # Update segment status to completed and commit to DB
                segment.status = 9
                db.commit()  # Commit sau mỗi segment để track progress
                
                # Calculate duration of this segment for timestamp adjustment  
                segment_duration = 0
                if segment_transcription:
                    # Tìm timestamp lớn nhất trong segment này
                    max_end_time = 0
                    for line in segment_transcription:
                        if 'end' in line:
                            try:
                                end_time = int(line['end'])
                                if end_time > max_end_time:
                                    max_end_time = end_time
                            except (ValueError, TypeError):
                                logging.warning("⚠️ Invalid end time in segment %d: %s", segment.segment_id, line.get('end'))
                                pass
                    
                    segment_duration = max_end_time
                    # Cập nhật offset cho segment tiếp theo
                    total_duration_offset += segment_duration
                    logging.info("📊 Segment %d processed. Duration: %d ms, Total offset: %d ms", 
                               segment.segment_id, segment_duration, total_duration_offset)
                else:
                    logging.warning("⚠️ No transcription data for segment %d", segment.segment_id)
                    # If no transcription, estimate duration from segment_len
                    try:
                        estimated_duration = int(float(segment.segment_len) * 1000)  # Convert to ms
                        total_duration_offset += estimated_duration
                        logging.info("📊 Segment %d: No transcription, using estimated duration %d ms", 
                                   segment.segment_id, estimated_duration)
                    except (ValueError, TypeError):
                        logging.error("❌ Cannot estimate duration for segment %d", segment.segment_id)
                    
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

        # Validate merged timestamps are in ascending order
        if all_segments:
            prev_end = -1
            timestamp_issues = []
            
            for i, segment_result in enumerate(all_segments):
                try:
                    current_bg = int(segment_result['bg'])
                    current_ed = int(segment_result['ed'])
                    
                    # Check if current start >= previous end
                    if current_bg < prev_end:
                        issue = f"Overlap at index {i}: bg={current_bg} < prev_end={prev_end}"
                        timestamp_issues.append(issue)
                        logging.warning("⚠️ " + issue)
                    
                    # Check if bg <= ed
                    if current_bg > current_ed:
                        issue = f"Invalid at index {i}: bg={current_bg} > ed={current_ed}"
                        timestamp_issues.append(issue)
                        logging.warning("⚠️ " + issue)
                    
                    prev_end = current_ed
                    
                except (ValueError, TypeError) as e:
                    issue = f"Invalid format at index {i}: {e}"
                    timestamp_issues.append(issue)
                    logging.error("❌ " + issue)
            
            if timestamp_issues:
                logging.warning("⚠️ Found %d timestamp issues in merged result", len(timestamp_issues))
            else:
                logging.info("✅ Timestamp validation passed for %d segments", len(all_segments))

        task.result = all_segments
        task.status = 9  # Completed
        
        # Update all segments to completed status
        task_segments = db.query(TaskSegment).filter(TaskSegment.task_id == task_id).all()
        for segment in task_segments:
            segment.status = 9  # Completed
        
        db.commit()
        logging.info("🎉 Task %s completed successfully with %d transcription segments", task_id, len(all_segments))

    except Exception as e:
        logging.exception("❌ Error processing task %s", task_id)
        if task:
            task.error = str(e)
            task.status = -1  # Failed
            db.commit()
    finally:
        db.close()

