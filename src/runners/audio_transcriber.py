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


import numpy as np
import io
from datetime import datetime
from faster_whisper.vad import get_speech_timestamps, collect_chunks
from pydantic import BaseModel


class BatchInput(BaseModel):
    audio: bytes
    pair: str
    lang: str = "en"


class BatchOutput(BaseModel):
    text: str
    batched_count: int
    merge_audio_time: float
    transcribe_time: float
    restore_time: float


"""
class BatchableAudioTranscriber(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self):
        device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        compute_type = "float16" if ctranslate2.get_cuda_device_count() > 0 else "int8"

        print(device, " ", compute_type)

        model = "base.en"
        self.model = WhisperModel(model, device=device, compute_type=compute_type)

    def transcribe(self, audios):
        segments, info = self.model.transcribe(
            audios,
            vad_filter=False,
            vad_parameters=dict(min_silence_duration_ms=250),
            language="en",
            condition_on_previous_text=False,
            word_timestamps=True,
            no_speech_threshold=10,
        )
        return segments

    @bentoml.Runnable.method(batchable=True)
    def transcribe_audio(self, inputs: list[BatchInput]) -> list[str]:
        result = []

        # merging audio
        ts = datetime.now()

        batch_list = []
        audio_batch = np.ndarray(1, dtype=np.float32)
        for input in inputs:
            wav = decode_audio(io.BytesIO(input.audio))
            chunks = get_speech_timestamps(wav)
            if len(chunks) == 0:
                batch_list.append(
                    BatchItem(
                        start_time=len(audio_batch) / 16000.0,
                        end_time=len(audio_batch) / 16000.0,
                        chunks_count=0,
                    )
                )
            else:
                wav = collect_chunks(wav, chunks=chunks)
                wav = np.append(wav, np.zeros(16000, dtype=np.float32))
                batch_list.append(
                    BatchItem(
                        start_time=len(audio_batch) / 16000.0,
                        end_time=(len(audio_batch) + len(wav)) / 16000.0,
                        chunks_count=len(chunks),
                    )
                )
                audio_batch = np.append(audio_batch, wav)

        for item in batch_list:
            print(item)

        merge_time = (datetime.now() - ts).total_seconds()

        ts = datetime.now()
        segments = self.transcribe(audio_batch)
        transcribe_time = (datetime.now() - ts).total_seconds()

        ts = datetime.now()
        output = [segment for segment in segments]

        for segment in output:
            for word in segment.words:
                for item in batch_list:
                    item.add(word)

        restore_time = (datetime.now() - ts).total_seconds()

        for item in batch_list:
            result.append(
                BatchOutput(
                    text=item.transcription,
                    batched_count=len(inputs),
                    merge_audio_time=merge_time,
                    transcribe_time=transcribe_time,
                    restore_time=restore_time,
                )
            )

        return result

"""


from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
import torch
from itertools import groupby


class BatchableAudioTranscriber(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self):
        pass
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = Wav2Vec2Processor.from_pretrained(
            # "facebook/wav2vec2-base-960h"
            "facebook/wav2vec2-large-960h-lv60-self"
        )
        self.model = Wav2Vec2ForCTC.from_pretrained(
            # "facebook/wav2vec2-base-960h"
            "facebook/wav2vec2-large-960h-lv60-self"
        ).cuda()

    def transcribe(self, audios):
        input_values = self.processor(
            audios, return_tensors="pt", sampling_rate=16000, padding=True
        ).input_values.cuda()

        with torch.no_grad():
            logits = self.model(input_values).logits
        predicted_ids = torch.argmax(logits, dim=-1)
        transcriptions = self.processor.batch_decode(predicted_ids)

        return transcriptions

    @bentoml.Runnable.method(batchable=True)
    def transcribe_audio(self, inputs: list[BatchInput]) -> list[str]:
        # merging audio
        audio_batch = []
        for input in inputs:
            audio_batch.append(np.frombuffer(input.audio, dtype=np.float32))

        ts = datetime.now()
        segments = self.transcribe(audio_batch)
        transcribe_time = (datetime.now() - ts).total_seconds()

        return [
            BatchOutput(
                text=text,
                batched_count=len(inputs),
                merge_audio_time=0,
                transcribe_time=transcribe_time,
                restore_time=0,
            )
            for text in segments
        ]


"""
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import torch


class BatchableAudioTranscriber(bentoml.Runnable):
    SUPPORTED_RESOURCES = ("nvidia.com/gpu", "cpu")
    SUPPORTS_CPU_MULTI_THREADING = True

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = WhisperProcessor.from_pretrained("openai/whisper-base.en")
        self.model = WhisperForConditionalGeneration.from_pretrained(
            "openai/whisper-base.en", attn_implementation="sdpa"
        ).cuda()

        self.model.generation_config.cache_implementation = "static"
        self.model.forward = torch.compile(
            self.model.forward, mode="reduce-overhead", fullgraph=True
        )

    def transcribe(self, audios):
        input_features = self.processor(
            audios, return_tensors="pt", sampling_rate=16000, padding=True
        ).input_features.cuda()

        for _ in range(2):
            self.model.generate(input_features)

        predicted_ids = self.model.generate(input_features)
        transcriptions = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)
        print(transcriptions)

        return transcriptions

    @bentoml.Runnable.method(batchable=True)
    def transcribe_audio(self, inputs: list[BatchInput]) -> list[str]:
        result = []

        # merging audio
        ts = datetime.now()
        audio_batch = []
        for input in inputs:
            wav = decode_audio(io.BytesIO(input.audio))
            chunks = get_speech_timestamps(wav)
            if len(chunks) == 0:
                audio_batch.append(np.zeros(16000, dtype=np.float32))
            else:
                wav = collect_chunks(wav, chunks=chunks)
                audio_batch.append(wav)

        merge_time = (datetime.now() - ts).total_seconds()

        ts = datetime.now()
        segments = self.transcribe(audio_batch)
        transcribe_time = (datetime.now() - ts).total_seconds()

        return [
            BatchOutput(
                text=text,
                batched_count=len(inputs),
                merge_audio_time=merge_time,
                transcribe_time=transcribe_time,
                restore_time=0,
            )
            for text in segments
        ]
"""
