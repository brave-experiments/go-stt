from ast import List
import bentoml
from bentoml.io import JSON
import torch
from faster_whisper import WhisperModel
import numpy as np

class AudioTranscriber(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if torch.cuda.is_available() else "int8"
        model = "base.en"
        self.model = WhisperModel(model, device=device, compute_type=compute_type)

    @bentoml.Runnable.method(batchable=True)
    def transcribe_audio(self, data: List[np.ndarray]) -> List[JSON]:
        result = []
        for audio in data:
            segments = self.model.transcribe(audio, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
            text = ""
            for s in segments:
                text = text + " "  + s.text
            result += JSON({ text: text })

        return result
