import os
import torch
from typing import Optional, List, Tuple
from pyannote.audio import Pipeline
from pyannote.audio.pipelines import SpeakerDiarization
from pyannote.core import Segment
import pandas as pd

class DiarizationPipeline:
    def __init__(
        self,
        finetuned_ckpt_path: str,
        segmentation_threshold: float = 0.6283,
        clustering_threshold: float = 0.5954,
        min_cluster_size: int = 15,
        use_cuda: bool = True,
        auth_token: Optional[str] = None,
        model_name: str = "pyannote/speaker-diarization-3.1"
    ):
        self.device = torch.device("cuda" if use_cuda and torch.cuda.is_available() else "cpu")
        self.finetuned_ckpt_path = finetuned_ckpt_path

        # Load pretrained modules
        self.pretrained_pipeline = Pipeline.from_pretrained(
            model_name, use_auth_token=auth_token
        ).to(self.device)

        # Build full pipeline
        self.pipeline = SpeakerDiarization(
            segmentation=self.finetuned_ckpt_path,
            embedding=self.pretrained_pipeline.embedding,
            embedding_exclude_overlap=self.pretrained_pipeline.embedding_exclude_overlap,
            clustering=self.pretrained_pipeline.klustering,
        ).to(self.device)

        # Set parameters
        self.pipeline.instantiate({
            "segmentation": {
                "threshold": segmentation_threshold,
                "min_duration_off": 0.0,
            },
            "clustering": {
                "method": "centroid",
                "min_cluster_size": min_cluster_size,
                "threshold": clustering_threshold,
            },
        })

    def run(self, audio_path: str,num_speakers:int) -> List[Tuple[float, float, str]]:
        """Run diarization and return list of (start, end, speaker)"""
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        diarization_result = self.pipeline(audio_path,num_speakers=num_speakers)


        diarize_df = pd.DataFrame(diarization_result.itertracks(yield_label=True), columns=['segment', 'label', 'speaker'])
        diarize_df['start'] = diarize_df['segment'].apply(lambda x: float(x.start))
        diarize_df['end'] = diarize_df['segment'].apply(lambda x: float(x.end))
    
        # ✅ Return list of dicts
        return diarize_df
       


    def print_result(self, audio_path: str):
        """Run diarization and print formatted output"""
        segments = self.run(audio_path)
        for start, end, speaker in segments:
            print(f"{start:.2f}s - {end:.2f}s: Speaker {speaker}")

    def to_dict(self, audio_path: str):
        """Return result as a list of dictionaries"""
        segments = self.run(audio_path)
        return [
            {"start": float(start), "end": float(end), "speaker": speaker}
            for start, end, speaker in segments
        ]


# Usage example
if __name__ == "__main__":
    diarizer = DiarizationPipeline(
        finetuned_ckpt_path="epoch=19.ckpt",
        auth_token="your_hf_token_here"
    )

    audio_file = "sample_0.wav"
    diarizer.print_result(audio_file)
    # Optional: print as dict
    # print(diarizer.to_dict(audio_file))
