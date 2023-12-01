import bentoml
import torch
from faster_whisper import WhisperModel
from bentoml.io import JSON

class AudioTranscriber(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if torch.cuda.is_available() else "int8"
        model = "base_en"
        self.model = WhisperModel(model, device=device, compute_type=compute_type)

    @bentoml.Runnable.method(batchable=False)
    def transcribe_audio(self, audio):        
        segments = self.model.transcribe(audio, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))

        text = ""
        for s in segments:
            text = text + " "  + s.text

        return { "text" : text }