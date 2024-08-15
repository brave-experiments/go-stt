import bentoml
import ctranslate2
from faster_whisper import WhisperModel, decode_audio


class AudioTranscriber(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self):
        device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        compute_type = (
            "int8_float16" if ctranslate2.get_cuda_device_count() > 0 else "int8"
        )

        print(device, " ", compute_type)

        model = "medium"
        self.model = WhisperModel(model, device=device, compute_type=compute_type)

    @bentoml.Runnable.method(batchable=False)
    def transcribe_audio(self, audio, lang):
        if len(lang) < 2:
            lang = "en"
        else:
            lang = lang[0:2]

        segments, info = self.model.transcribe(
            audio,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            language=lang,
        )

        text = ""
        for segment in segments:
            text += segment.text

        return {"text": text}


from pydantic import BaseModel
import numpy as np
import io


class BatchInput(BaseModel):
    audio: bytes
    pair: str
    lang: str = "en"


"""
class BatchableAudioTranscriber(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self):
        device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        compute_type = (
            "int8_float16" if ctranslate2.get_cuda_device_count() > 0 else "int8"
        )

        print(device, " ", compute_type)

        model = "base.en"
        self.model = whisper.load_model(model_identifier=model, backend='CTranslate2')

    def transcribe(self, audio):
        segments, info = self.model.transcribe(
            audio,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False,
            language="en",
        )

        return segments

    @bentoml.Runnable.method(batchable=True)
    def transcribe_audio(self, inputs: list[BatchInput]) -> list[str]:
        if len(inputs) == 1:
            segments = self.transcribe(io.BytesIO(inputs[0].audio))

            text = ""
            for segment in segments:
                text += segment.text
            return [text]

        MAX_SILENCE = 16000 * 30

        # merging audio
        audio_batch = np.ndarray(1, dtype=np.float32)
        for input in inputs:
            wav = decode_audio(io.BytesIO(input.audio))
            wav = np.append(wav, np.zeros(MAX_SILENCE - len(wav), dtype=np.float32))
            audio_batch = np.append(audio_batch, wav)

        segments, info = self.model.g(
            audio_batch,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=250),
            condition_on_previous_text=False,
            word_timestamps=True,
            language="en",
        )

        result = []
        print("inputs ", len(inputs))
        for segment in segments:
            print(segment.start, " -> ", segment.end, " : ", segment.text)

            for word in segment.words:
                print("   ", word.start, " -> ", word.end, " : ", word)

            if segment.start >= 30 * len(result):
                result.append("")
            if segment.end < 30 * (len(result)):
                result[-1] += segment.text

        return result
"""

import whisperx as whisper


class BatchableAudioTranscriber(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self):
        self.device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        compute_type = "float16" if ctranslate2.get_cuda_device_count() > 0 else "int8"

        print(self.device, " ", compute_type)

        model = "medium"
        self.model = whisper.load_model(
            whisper_arch=model,
            device=self.device,
            compute_type=compute_type,
            download_root="/home/bentoml/models",
        )

    def transcribe(self, audios):
        result = self.model.transcribe(audios, batch_size=8, language="en")
        return result["segments"]

    @bentoml.Runnable.method(batchable=True)
    def transcribe_audio(self, inputs: list[BatchInput]) -> list[str]:
        if len(inputs) == 1:
            segments = self.transcribe(decode_audio(io.BytesIO(inputs[0].audio)))

            text = ""
            for segment in segments:
                text += segment["text"]
            return [text]

        # merging audio
        MAX_SILENCE = 16000 * 30

        # merging audio
        audio_batch = np.ndarray(1, dtype=np.float32)
        for input in inputs:
            wav = decode_audio(io.BytesIO(input.audio))
            wav = np.append(wav, np.zeros(MAX_SILENCE - len(wav), dtype=np.float32))
            audio_batch = np.append(audio_batch, wav)

        segments = self.transcribe(audio_batch)

        result = []
        for segment in segments:
            if segment["start"] + 0.1 >= 30 * len(result):
                result.append("")
            if segment["end"] < 30 * (len(result)):
                result[-1] += segment["text"]

        return result
