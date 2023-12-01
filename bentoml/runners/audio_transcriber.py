import bentoml
import whisper
import torch
import numpy as np

class AudioTranscriber(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self):
        self.model = whisper.load_model("base")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    @bentoml.Runnable.method(batchable=False)
    def transcribe_audio(self, audio):
        data = np.frombuffer(audio, np.float32).astype(np.float32)
        data = whisper.pad_or_trim(data)
        transcription = self.model.transcribe(data)
        return transcription['text']