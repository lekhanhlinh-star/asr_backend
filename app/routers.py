
import json
import logging
import os
import uuid
from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi import Depends
from fastapi.responses import JSONResponse
from tasks.process_audio import process_audio
from database import get_db,Session
import requests
from models import Task, TaskSegment
router = APIRouter()
# from asr import ASRModel
# import httpx
# model_dir = os.path.abspath(
#             os.path.join(os.path.dirname(__file__), '.', 'weights', 'whisper-large-v2-lora-zh-ct2')
#         )
# model = ASRModel(model_dir,device="cuda") 
SUMMARIZER_API_URL = "http://140.115.59.61:8000/v1/summarize"
@router.post("/api/prepare")
async def prepare(
    file_len: str = Form(...),
    file_name: str = Form(...),
    total_segments: int = Form(...),
    speaker_number: str = Form("2"),
    has_separate: str = Form("false"),
    language: str = Form("default"),
    pd: str = Form(None),
    hotWord: str = Form(None),
    db: Session = Depends(get_db)
):
    task_id = uuid.uuid4().hex
    task = Task(
        id=task_id,
        status=0,
        file_len=file_len,
        file_name=file_name,
        total_segments=total_segments,
        speaker_number=speaker_number,
        has_separate=has_separate.lower() == "true",
        language=language,
        pd=pd,
        hotWord=hotWord,
        file_path=None,
        result=None,
        error=None,
    )
    db.add(task)
    db.commit()
    logging.info("Created new task %s for file %s", task_id, file_name)
    return JSONResponse(content={"ok": 0, "err_no": 0, "failed": None, "data": task_id})

@router.post("/api/upload")
async def upload(
    task_id: str = Form(...),
    segment_id: int = Form(...),
    segment_len: str = Form(...),
    content: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logging.error("Upload failed: Task %s does not exist", task_id)
        return JSONResponse(
            content={"ok": -1, "err_no": 26000, "failed": "Task ID does not exist", "data": None},
            status_code=400,
        )

    if task.status != 0:
        logging.error("Upload failed: Invalid task state %s for task %s", task.status, task_id)
        return JSONResponse(
            content={"ok": -1, "err_no": 26000, "failed": "Invalid task state", "data": None},
            status_code=400,
        )

    # Validate segment_id range
    if segment_id < 1 or segment_id > task.total_segments:
        logging.error("Upload failed: Invalid segment_id %d for task %s (expected 1-%d)", 
                     segment_id, task_id, task.total_segments)
        return JSONResponse(
            content={"ok": -1, "err_no": 26001, "failed": f"Invalid segment_id {segment_id}. Must be between 1 and {task.total_segments}", "data": None},
            status_code=400,
        )

    # Check if segment already exists
    existing_segment = db.query(TaskSegment).filter(
        TaskSegment.task_id == task_id,
        TaskSegment.segment_id == segment_id
    ).first()
    
    if existing_segment:
        logging.error("Upload failed: Segment %d already exists for task %s", segment_id, task_id)
        return JSONResponse(
            content={"ok": -1, "err_no": 26002, "failed": f"Segment {segment_id} already uploaded", "data": None},
            status_code=400,
        )

    # Validate sequential upload - MUST upload in order (1, 2, 3, ...)
    uploaded_segments = db.query(TaskSegment).filter(TaskSegment.task_id == task_id).count()
    expected_segment_id = uploaded_segments + 1
    
    logging.info("Upload validation for task %s: uploaded_segments=%d, expected=%d, received=%d", 
                task_id, uploaded_segments, expected_segment_id, segment_id)
    
    if segment_id != expected_segment_id:
        if segment_id < expected_segment_id:
            error_msg = f"Segment {segment_id} already uploaded. Expected segment {expected_segment_id}."
        else:
            error_msg = f"Must upload segment {expected_segment_id} before segment {segment_id}. Upload segments in order (1→2→3...)."
        
        logging.error("Upload failed: %s (task %s)", error_msg, task_id)
        return JSONResponse(
            content={"ok": -1, "err_no": 26003, "failed": error_msg, "data": None},
            status_code=400,
        )

    # Save uploaded segment
    segment_file_path = f"uploads/{task_id}_segment_{segment_id}_{content.filename}"
    os.makedirs(os.path.dirname(segment_file_path), exist_ok=True)
    with open(segment_file_path, "wb") as f:
        file_content = await content.read()
        f.write(file_content)

    # Save segment info to database
    task_segment = TaskSegment(
        task_id=task_id,
        segment_id=segment_id,
        segment_len=segment_len,
        file_path=segment_file_path,
        status=0
    )
    db.add(task_segment)

    # Check if this is the last segment to trigger processing
    uploaded_count = uploaded_segments + 1  # +1 because we're adding current segment
    
    if segment_id == 1:
        # First segment - set file_path but don't start processing yet
        task.file_path = segment_file_path
        task.status = 1  # Upload in progress
        logging.info("✅ First segment uploaded for task %s at %s", task_id, segment_file_path)
    elif uploaded_count == task.total_segments:
        # Last segment - start processing
        task.status = 1  # Upload completed
        db.commit()
        logging.info("✅ All %d segments uploaded for task %s. Starting processing...", task.total_segments, task_id)
        
        # Start processing only when all segments are uploaded
        process_audio.delay(task_id)
        logging.info("🚀 Enqueued Celery task for processing audio, task_id=%s", task_id)
        return {"ok": 0, "err_no": 0, "failed": None, "data": f"All segments uploaded. Processing started."}
    else:
        # Middle segments
        logging.info("✅ Segment %d/%d uploaded for task %s at %s", segment_id, task.total_segments, task_id, segment_file_path)
    
    db.commit()
    return {"ok": 0, "err_no": 0, "failed": None, "data": f"Segment {segment_id}/{task.total_segments} uploaded successfully."}

@router.post("/api/getProgress")
async def get_progress(task_id: str = Form(...), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logging.error("Progress check failed: Task %s does not exist", task_id)
        return JSONResponse(
            content={"ok": -1, "err_no": 26000, "failed": "Task ID does not exist", "data": None},
            status_code=404,
        )
    
    # Get segment statuses
    segments_data = {}
    task_segments = db.query(TaskSegment).filter(TaskSegment.task_id == task_id).all()
    
    # Helper function to get status description
    def get_status_desc(status):
        status_map = {
            0: "Task created successfully",
            1: "Audio upload completed", 
            2: "Audio recognition in progress",
            9: "Recognition completed"
        }
        return status_map.get(status, "Unknown status")
    
    for segment in task_segments:
        segments_data[str(segment.segment_id)] = {
            "status": segment.status,
            "desc": get_status_desc(segment.status)
        }
    
    progress_data = {
        "task_status": task.status,
        "desc": get_status_desc(task.status),
        "segments": segments_data
    }
    
    logging.info("Progress for task %s requested: status %s", task_id, task.status)
    return JSONResponse(content={"ok": 0, "err_no": 0, "failed": None, "data": progress_data})




@router.post("/api/getResult")
async def get_result(task_id: str = Form(...), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logging.error("Result request failed: Task %s does not exist", task_id)
        return JSONResponse(
            content={"ok": -1, "err_no": 26000, "failed": "Task ID does not exist", "data": None},
            status_code=404,
        )
    
    # Check if all segments have been uploaded
    uploaded_segments = db.query(TaskSegment).filter(TaskSegment.task_id == task_id).count()
    if uploaded_segments < task.total_segments:
        logging.warning("Result requested for incomplete upload task %s: %d/%d segments uploaded", 
                       task_id, uploaded_segments, task.total_segments)
        return JSONResponse(
            content={"ok": -1, "err_no": 26004, "failed": f"Incomplete upload: {uploaded_segments}/{task.total_segments} segments uploaded. Upload all segments before requesting result.", "data": None},
            status_code=400,
        )
    
    if task.status != 9:
        logging.warning("Result requested for incomplete task %s: current status %s", task_id, task.status)
        return JSONResponse(
            content={"ok": -1, "err_no": 26000, "failed": "Task not completed", "data": None},
            status_code=400,
        )
    
    # Convert result to JSON string as required by spec
    result_data = task.result
    if isinstance(result_data, list):
        result_json_string = json.dumps(result_data, ensure_ascii=False)
    else:
        result_json_string = result_data
    
    logging.info("Result returned for task %s", task_id)
    return JSONResponse(
        content={"ok": 0, "err_no": 0, "failed": None, "data": result_json_string},
        status_code=200,
    )





# @router.post("/v1/api/summarize")
# async def summarize_from_task(
#     task_id: str = Form(...),
#     language: str = Form(...),
#     db: Session = Depends(get_db)
# ):
#     # Lấy dữ liệu từ DB
#     task = db.query(Task).filter(Task.id == task_id).first()
#     if not task:
#         logging.error("Task ID %s not found", task_id)
#         return JSONResponse(
#             content={"ok": -1, "err_no": 26000, "failed": "Task ID does not exist", "data": None},
#             status_code=404,
#         )

#     if task.status != 9:
#         logging.warning("Task %s is not completed", task_id)
#         return JSONResponse(
#             content={"ok": -1, "err_no": 26001, "failed": "Task not completed", "data": None},
#             status_code=400,
#         )

#     transcript = " ".join(item["onebest"] for item in task.result if "onebest" in item).strip()
#     if not transcript:
#         return JSONResponse(
#             content={"ok": -1, "err_no": 26002, "failed": "Transcript is empty", "data": None},
#             status_code=400,
#         )

#     # Gửi request tới backend khác
#     try:
#         async with httpx.AsyncClient() as client:
#             response = await client.post(
#                 SUMMARIZER_API_URL,
#                 data={"transcript": transcript, "language": language},
#                 timeout=720
#             )
        
#         if response.status_code != 200:
#             return JSONResponse(
#                 content={"ok": -1, "err_no": 26003, "failed": "Summarizer backend error", "data": response.text},
#                 status_code=response.status_code,
#             )

#         summary_result = response.json()

#         return JSONResponse(
#             content={"ok": 0, "err_no": 0, "failed": None, "data": summary_result},
#             status_code=200,
#         )

#     except httpx.RequestError as e:
#         logging.exception("HTTP request failed to summarizer backend")
#         return JSONResponse(
#             content={"ok": -1, "err_no": 26004, "failed": f"Request failed: {str(e)}", "data": None},
#             status_code=500,
#         )


# @router.post("/api/asr")
# async def asr_upload(
#     file: UploadFile = File(...),
# ):
#     try:
#         # Save the uploaded file to a temporary location
#         temp_dir = "temp_uploads"
#         os.makedirs(temp_dir, exist_ok=True)
#         file_path = os.path.join(temp_dir, file.filename)
#         with open(file_path, "wb") as f:
#             content = await file.read()
#             f.write(content)

#         # Perform transcription
#         transcript = model.transcribe(file_path, language="zh", timestamp=True, punctuation=True)

#         # Optionally, delete the temporary file after processing
#         os.remove(file_path)

#         return JSONResponse(content={"ok": 0, "err_no": 0, "failed": None, "data": transcript})
#     except Exception as e:
#         logging.exception("ASR processing failed")
#         return JSONResponse(
#             content={"ok": -1, "err_no": 26005, "failed": f"ASR processing failed: {str(e)}", "data": None},
#             status_code=500,
#         )
