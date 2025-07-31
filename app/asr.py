import os
import time
import logging
from dotenv import load_dotenv
import whisperx

from postprocessing.punctuation import add_punctuation
from diarization_pipeline import DiarizationPipeline  # import class bạn đã viết

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class ASRModel:
    def __init__(
        self,
        model_path: str = "base",
        finetuned_ckpt_path: str = "epoch=19.ckpt",
        device: str = "cuda",
        device_index: int = 0,
        num_workers: int = 4,
        batch_size: int = 16,
        hf_token: str = None
    ):
        logger.info("Loading WhisperX ASR model...")
        self.model = whisperx.load_model(
            model_path,
            device=device,
            device_index=device_index,
            compute_type="auto",
            threads=num_workers,
            vad_options={"vad_onset": 0.500, "vad_offset": 0.300}
        )

        self.batch_size = batch_size

        hf_token = hf_token or os.getenv("HF_TOKEN")
        if not hf_token:
            raise ValueError("HF_TOKEN not set in .env or as parameter.")

        logger.info("Loading DiarizationPipeline (fine-tuned)...")
        self.diarizer = DiarizationPipeline(
            finetuned_ckpt_path=finetuned_ckpt_path,
            use_cuda=(device == "cuda"),
            auth_token=hf_token
        )

    def transcribe(self, audio_path, num_speakers, language="zh", timestamp=False, punctuation=False):

        logger.info(f"Transcribing: {audio_path}")
        start_total = time.time()

        # Step 1: load audioz
        audio = whisperx.load_audio(audio_path)

        # Step 2: transcribe
        start_asr = time.time()
        asr_result = self.model.transcribe(audio, batch_size=self.batch_size, language=language)
        end_asr = time.time()

        # Step 3: diarization with fine-tuned checkpoint
        diarization_segments = self.diarizer.run(audio_path,num_speakers)

        # Step 4: combine speaker info with ASR
    

        result = whisperx.assign_word_speakers(diarization_segments , asr_result)
        segments = result["segments"]

        # if punctuation:
        #     logger.info("Applying punctuation...")
        #     segments = add_punctuation(segments,language)

        logger.info(f"ASR time: {end_asr - start_asr:.2f}s")
        logger.info(f"Total processing time: {time.time() - start_total:.2f}s")

        return segments
