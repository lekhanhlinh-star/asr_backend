import streamlit as st
import requests
import time
import io

# Base URL of your FastAPI backend
BASE_URL = "http://140.115.59.61:8003"

def handle_request(url, method="POST", data=None, files=None):
    """Helper function to handle requests and check for errors"""
    try:
        if method == "POST":
            if files:
                response = requests.post(url, data=data, files=files)
            else:
                response = requests.post(url, data=data)
        
        # Log response details for debugging
        print(f"Request to {url}")
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response text: {response.text}")
            
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"Error: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(f"Response: {e.response.text}")
        return None

def start_processing(uploaded_file, file_len, total_segments, speaker_number, has_separate, language, pd, hotWord):
    """Function to manage the entire process"""
    # Step 1: Prepare Task
    prepare_data = {
        "file_len": str(file_len),
        "file_name": uploaded_file.name,
        "total_segments": str(total_segments),
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

def upload_file_segments(task_id, uploaded_file, total_segments):
    """Function to upload the file as segments"""
    file_content = uploaded_file.read()
    file_size = len(file_content)
    segment_size = file_size // total_segments
    
    st.info(f"Uploading {total_segments} segments...")
    upload_progress = st.progress(0)
    
    for segment_id in range(1, total_segments + 1):
        start_pos = (segment_id - 1) * segment_size
        if segment_id == total_segments:
            # Last segment gets remaining bytes
            end_pos = file_size
        else:
            end_pos = start_pos + segment_size
            
        segment_data = file_content[start_pos:end_pos]
        segment_len = str(len(segment_data))
        
        # Create a file-like object for the segment
        segment_file = io.BytesIO(segment_data)
        segment_filename = f"{uploaded_file.name}_segment_{segment_id}"
        
        # Debug information
        st.write(f"Uploading segment {segment_id}: size={segment_len} bytes")
        
        files = {"content": (segment_filename, segment_file, uploaded_file.type)}
        upload_data = {
            "task_id": task_id,
            "segment_id": segment_id,  # Send as int, not string
            "segment_len": segment_len
        }
        
        # Debug the request data
        st.write(f"Upload data: {upload_data}")
        
        res = handle_request(f"{BASE_URL}/api/upload", data=upload_data, files=files)
        if res and res.status_code == 200:
            response_data = res.json()
            st.write(f"Response: {response_data}")
            if response_data.get("ok") == 0:
                upload_progress.progress(segment_id / total_segments)
                st.success(f"✅ Uploaded segment {segment_id}/{total_segments}")
            else:
                st.error(f"❌ API returned error for segment {segment_id}: {response_data}")
                return False
        else:
            st.error(f"❌ Failed to upload segment {segment_id}")
            if res:
                st.error(f"Status: {res.status_code}, Response: {res.text}")
            return False
    
    st.success(f"All {total_segments} segments uploaded successfully!")
    return True

def check_progress_detailed(task_id, progress_placeholder, segments_placeholder):
    """Function to check the task progress with detailed segment info"""
    res = handle_request(f"{BASE_URL}/api/getProgress", data={"task_id": task_id})
    if not res:
        st.error("Failed to fetch progress.")
        return None
    
    data = res.json().get("data")
    if not data:
        return None
        
    task_status = data.get("task_status", 0)
    task_desc = data.get("desc", "Unknown")
    segments = data.get("segments", {})
    
    # Update main progress
    progress_pct = int((task_status / 9) * 100)
    progress_placeholder.info(f"Task Status: {task_status} - {task_desc} ({progress_pct}%)")
    
    # Update segments info
    if segments:
        segment_info = "**Segments Progress:**\n"
        for seg_id, seg_data in segments.items():
            status = seg_data.get("status", 0)
            desc = seg_data.get("desc", "Unknown")
            segment_info += f"- Segment {seg_id}: Status {status} - {desc}\n"
        segments_placeholder.markdown(segment_info)
    
    return task_status

def get_result(task_id):
    """Function to get the final result"""
    res = handle_request(f"{BASE_URL}/api/getResult", data={"task_id": task_id})
    if res and res.status_code == 200 and res.json().get("ok") == 0:
        result_data = res.json().get("data")
        st.success("Task completed!")
        
        # Parse the JSON string result
        try:
            import json
            if isinstance(result_data, str):
                parsed_result = json.loads(result_data)
            else:
                parsed_result = result_data
                
            # Display formatted result
            st.subheader("Recognition Results:")
            for i, segment in enumerate(parsed_result):
                bg = segment.get("bg", "0")
                ed = segment.get("ed", "0") 
                text = segment.get("onebest", "")
                speaker = segment.get("speaker", "0")
                
                st.write(f"**Segment {i+1}:** [{bg}ms - {ed}ms] Speaker {speaker}")
                st.write(f"Text: {text}")
                st.write("---")
                
            # Also show raw result
            with st.expander("Raw JSON Result"):
                st.text_area("Raw Result", result_data, height=200)
                
        except Exception as e:
            st.error(f"Error parsing result: {e}")
            st.text_area("Raw Result", result_data, height=200)
    else:
        st.error("Failed to fetch result.")

# Streamlit UI
st.title("Audio Processing Frontend")

st.sidebar.header("Task Configuration")
file_len = st.sidebar.text_input("File Length (bytes)", "")
total_segments = st.sidebar.number_input("Total Segments", min_value=1, max_value=10, value=1)
speaker_number = st.sidebar.number_input("Number of Speakers", min_value=1, max_value=10, value=2)
has_separate = st.sidebar.checkbox("Separate Speakers", value=False)
language = st.sidebar.selectbox("Language", ["default", "en", "zh", "vi"])
pd = st.sidebar.selectbox("Domain", ["", "edu", "medical", "finance", "tech", "sports", "gov", "game", "ecom", "car"])
hotWord = st.sidebar.text_input("Hot Words (separated by |)", "")

st.header("Upload Audio File and Start Task")
uploaded_file = st.file_uploader("Choose an audio file", type=["wav", "mp3", "ogg"])

if st.button("Start Processing"):
    if not uploaded_file or not file_len:
        st.error("Please upload an audio file and enter file length.")
    else:
        # Prepare task
        task_id = start_processing(uploaded_file, file_len, total_segments, speaker_number, has_separate, language, pd, hotWord)
        if not task_id:
            st.stop()

        # Upload file segments
        st.subheader("File Upload")
        st.write(f"Task ID: {task_id}")
        st.write(f"File: {uploaded_file.name}")
        st.write(f"Total segments: {total_segments}")
        
        if not upload_file_segments(task_id, uploaded_file, total_segments):
            st.stop()

        # Create placeholders for progress tracking
        st.subheader("Processing Progress")
        progress_placeholder = st.empty()
        segments_placeholder = st.empty()
        main_progress_bar = st.progress(0)

        # Poll progress with detailed segment info
        status = 0
        while status < 9:
            time.sleep(3)  # Check every 3 seconds
            status = check_progress_detailed(task_id, progress_placeholder, segments_placeholder)
            if status is None:
                st.error("Failed to fetch progress.")
                break
                
            # Update main progress bar
            pct = int((status / 9) * 100)
            main_progress_bar.progress(pct)

        # Fetch result when done
        if status == 9:
            progress_placeholder.success("Processing complete! Fetching result…")
            get_result(task_id)
