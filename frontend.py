import streamlit as st
import requests
import time
import io

# Base URL of your FastAPI backend
BASE_URL = "http://0.0.0.0:8001"

def handle_request(url, method="POST", data=None, files=None):
    """Helper function to handle requests and check for errors"""
    try:
        if method == "POST":
            if files:
                response = requests.post(url, data=data, files=files)
            else:
                response = requests.post(url, data=data)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"Error: {str(e)}")
        return None

def start_processing(uploaded_file, file_len, speaker_number, has_separate, language, pd, hotWord):
    """Function to manage the entire process"""
    # Step 1: Prepare Task
    prepare_data = {
        "file_len": str(file_len),
        "file_name": uploaded_file.name,
        "speaker_number": str(speaker_number),
        "has_separate": str(has_separate).lower(),
        "language": language,
        "pd": pd,
        "hotWord": hotWord
    }
    res = handle_request(f"{BASE_URL}/api/prepare", data=prepare_data)
    if res and res.status_code == 200 and res.json().get("ok") == 0:
        task_id = res.json()["data"]
        st.success(f"Task prepared: {task_id}")
        return task_id
    else:
        st.error(f"Prepare failed: {res.text if res else 'Unknown error'}")
        return None

def upload_file(task_id, uploaded_file):
    """Function to upload the file"""
    files = {"file": (uploaded_file.name, uploaded_file.read())}
    upload_data = {"task_id": task_id}
    res = handle_request(f"{BASE_URL}/api/upload", data=upload_data, files=files)
    if res and res.status_code == 200 and res.json().get("ok") == 1:
        st.success("File uploaded successfully.")
        return True
    else:
        st.error(f"Upload failed: {res.text if res else 'Unknown error'}")
        return False

def check_progress(task_id, progress_bar):
    """Function to check the task progress"""
    status = 0
    while status != 9:
        time.sleep(2)
        res3 = handle_request(f"{BASE_URL}/api/getProgress", data={"task_id": task_id})
        if res3:
            data = res3.json().get("data")
            prog = int(eval(data)["status"])
            status = prog
            progress_bar.progress(min(prog * 10, 100))
            st.write(f"Current status: {prog}")
        else:
            st.error("Failed to fetch progress.")
            break
    return status

def get_result(task_id):
    """Function to get the final result"""
    res4 = handle_request(f"{BASE_URL}/api/getResult", data={"task_id": task_id})
    if res4 and res4.status_code == 200 and res4.json().get("ok") == 0:
        result = res4.json().get("data")
        st.success("Task completed!")
        st.text_area("Result", result, height=200)
    else:
        st.error("Failed to fetch result.")

# Streamlit UI
st.title("Audio Processing Frontend")

st.sidebar.header("Task Configuration")
file_len = st.sidebar.text_input("File Length (e.g., duration in seconds)", "")
speaker_number = st.sidebar.number_input("Number of Speakers", min_value=1, max_value=10, value=2)
has_separate = st.sidebar.checkbox("Separate Speakers", value=False)
language = st.sidebar.selectbox("Language", ["default", "en", "zh", "vi"])
pd = st.sidebar.text_input("Pd", "")
hotWord = st.sidebar.text_input("Hotword", "")

st.header("Upload Audio File and Start Task")
uploaded_file = st.file_uploader("Choose an audio file", type=["wav", "mp3", "ogg"])

if st.button("Start Processing"):
    if not uploaded_file or not file_len:
        st.error("Please upload an audio file and enter file length.")
    else:
        # Prepare, upload, etc. …
        task_id = start_processing(uploaded_file, file_len, speaker_number, has_separate, language, pd, hotWord)
        if not task_id:
            st.stop()

        if not upload_file(task_id, uploaded_file):
            st.stop()

        # Create a single placeholder for status text
        status_placeholder = st.empty()
        progress_bar = st.progress(0)

        # Poll progress
        status = 0
        while status < 9:
            time.sleep(2)
            res3 = handle_request(f"{BASE_URL}/api/getProgress", data={"task_id": task_id})
            if not res3:
                st.error("Failed to fetch progress.")
                break

            # Parse status from returned JSON string
            status = int(eval(res3.json()["data"])["status"])
            pct = int((status / 9) * 100)

            # Update progress bar and placeholder in place
            progress_bar.progress(pct)
            status_placeholder.info(f"Current status: {status}  —  {pct}% complete")

        # Fetch result when done
        if status == 9:
            status_placeholder.success("Processing complete! Fetching result…")
            get_result(task_id)
