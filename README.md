# Speech Recognition API Backend

This project provides a backend API for asynchronous speech recognition (ASR) using FastAPI and Celery. The API allows users to upload audio files, track processing progress, and retrieve transcription results.

## Features
- Asynchronous audio transcription (not real-time)
- Supports large audio files (up to 500MB)
- Task-based workflow: prepare, upload, progress, result
- Extensible for diarization, hotwords, and domain adaptation

## API Endpoints

### 1. Preprocessing
- **Endpoint:** `/api/prepare`
- **Method:** POST
- **Content-Type:** `application/x-www-form-urlencoded`
- **Description:** Register a new audio recognition task and get a `task_id`.
- **Parameters:**
  - `file_len` (str, required): File size in bytes
  - `file_name` (str, required): File name
  - `speaker_number` (str, optional): Number of speakers (default: 2)
  - `has_separate` (str, optional): Speaker separation (`true`/`false`, default: false)
  - `language` (str, optional): Language (default: Chinese and English)
  - `pd` (str, optional): Domain (e.g., edu, medical, etc.)
  - `hotWord` (str, optional): Hot words (e.g., "word1|word2")
- **Response:** `{ "ok": 0, "err_no": 0, "failed": null, "data": "<task_id>" }`

### 2. File Upload
- **Endpoint:** `/api/upload`
- **Method:** POST
- **Content-Type:** `multipart/form-data`
- **Description:** Upload the audio file for the given `task_id`.
- **Parameters:**
  - `task_id` (str, required): Task ID from `/api/prepare`
  - `file` (file, required): Audio file (wav/flac/opus/m4a/mp3)
- **Response:** `{ "ok": 0, "err_no": 0, "failed": null, "data": { "task_id": "..." } }`

### 3. Query Processing Progress
- **Endpoint:** `/api/getProgress`
- **Method:** POST
- **Content-Type:** `application/x-www-form-urlencoded`
- **Description:** Query the current status of the recognition task.
- **Parameters:**
  - `task_id` (str, required): Task ID
- **Response:** `{ "ok": 0, "err_no": 0, "failed": null, "data": { "desc": "Task status", "status": <int> } }`

### 4. Get Result
- **Endpoint:** `/api/getResult`
- **Method:** POST
- **Content-Type:** `application/x-www-form-urlencoded`
- **Description:** Retrieve the recognition result when the task is complete (`status == 9`).
- **Parameters:**
  - `task_id` (str, required): Task ID
- **Response:** `{ "ok": 0, "err_no": 0, "failed": null, "data": <result> }`

## Task Status Codes
- `0`: Task created
- `1`: Audio upload completed
- `2`: Audio recognition in progress
- `9`: Recognition completed

## Error Codes
- `0`: Success
- `26000`: Common errors (e.g., task not found, invalid state)

## Requirements
- Python 3.8+
- FastAPI
- Celery
- SQLAlchemy
- (See `requirements.txt` for full list)

## Quick Start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```
3. Start the Celery worker:
   ```bash
   celery -A app.celery_app worker --loglevel=info
   ```

## Notes
- Audio files are processed asynchronously. Use `/api/getProgress` to poll for status.
- Only when status is `9` should you call `/api/getResult`.
- For more details, see the API PRD document.

## License
MIT