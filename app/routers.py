
import json
import logging
import os
import uuid
from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi import Depends
from fastapi.responses import JSONResponse
from tasks.process_audio import process_audio
from database import get_db,Session
from models import Task
router = APIRouter()

@router.post("/api/prepare")
async def prepare(
    file_len: str = Form(...),
    file_name: str = Form(...),
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
    file: UploadFile = File(...),
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

    # Save uploaded file
    file_path = f"uploads/{task_id}_{file.filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Update DB
    task.file_path = file_path
    task.status = 1  # Upload completed
    db.commit()
    logging.info("File uploaded and saved for task %s at %s", task_id, file_path)


    process_audio.delay(task_id)
    logging.info("Enqueued Celery task for processing audio, task_id=%s", task_id)

    return {"ok": 1, "err_no": 0, "failed": None, "data": {"task_id": task_id}}

@router.post("/api/getProgress")
async def get_progress(task_id: str = Form(...), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logging.error("Progress check failed: Task %s does not exist", task_id)
        return JSONResponse(
            content={"ok": -1, "err_no": 26000, "failed": "Task ID does not exist", "data": None},
            status_code=404,
        )
    
    progress_data = {"desc": "Task status", "status": task.status}
    logging.info("Progress for task %s requested: status %s", task_id, task.status)
    return JSONResponse(content={"ok": 0, "err_no": 0, "failed": None, "data": json.dumps(progress_data)})




@router.post("/api/getResult")
async def get_result(task_id: str = Form(...), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        logging.error("Result request failed: Task %s does not exist", task_id)
        return JSONResponse(
            content={"ok": -1, "err_no": 26000, "failed": "Task ID does not exist", "data": None},
            status_code=404,
        )
    
    if task.status != 9:
        logging.warning("Result requested for incomplete task %s: current status %s", task_id, task.status)
        return JSONResponse(
            content={"ok": -1, "err_no": 26000, "failed": "Task not completed", "data": None},
            status_code=400,
        )
    
    logging.info("Result returned for task %s", task_id)
    return JSONResponse(
    content={"ok": 0, "err_no": 0, "failed": None, "data": task.result},
    status_code=200,
)