import gc 
import time

import whisperx

from postprocessing.punctuation import add_punctuation

# from .postprocessing import add_punctuation


class ASRModel:
        
    def __init__(self, model_path, device="cpu", device_index=0, num_workers=4, batch_size=16):
        self.model = whisperx.load_model(
            model_path, 
            device=device, 
            device_index=device_index, 
            compute_type="auto",
            threads=num_workers,
            vad_options={
                "vad_onset": 0.500,
                "vad_offset": 0.300
            },
             
        )
        self.diarize_model = whisperx.DiarizationPipeline(
            model_name="fatymatariq/speaker-diarization-3.1",
            use_auth_token="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", 
            device=device,
        )
        self.batch_size = batch_size


    def transcribe(self, audio, language="zh", timestamp=False, punctuation=False):
        audio = whisperx.load_audio(audio)
        asr_segments = self.model.transcribe(audio, batch_size=self.batch_size, language=language)
        diarize_segments = self.diarize_model(audio)
        segments = whisperx.assign_word_speakers(diarize_segments, asr_segments)["segments"]
        
        return segments
    
if __name__=="__main__":
    model = ASRModel("base")
    sentences=model.transcribe("/home/linh/Desktop/ASR_BACKEND/app/uploads/656dce0502524276b4ceab438f15d502_meeting_audio.wav","en",timestamp=True)
    print(sentences)