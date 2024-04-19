import bentoml
import ctranslate2
from faster_whisper import WhisperModel
import io
import numpy as np

class AudioTranscriber(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self):
        device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        compute_type = "int8_float16" if ctranslate2.get_cuda_device_count() > 0 else "int8"

        model = "base.en"
        self.model = WhisperModel(model, device=device, compute_type=compute_type)

    @bentoml.Runnable.method(batchable=False)
    def transcribe_audio(self, audio):
        segments, info = self.model.transcribe(audio, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))

        text = ""
        for segment in segments:
            print(segment)
            text += segment.text

        return { "text" : text }

"""
    @bentoml.Runnable.method(batchable=False)
    def transcribe_audio_data(self, audio):
        data = np.frombuffer(audio, np.float32).astype(np.float32)
        segments, info = self.model.transcribe(data, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))

        text = ""
        for segment in segments:
            text += segment.text

        return { "text" : text }
"""