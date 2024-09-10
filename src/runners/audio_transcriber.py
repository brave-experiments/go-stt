import time

from typing import List

import torch

from pydantic import BaseModel
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

from sampuru import Runnable


class BatchOutput(BaseModel):
    text: str
    batched_count: int
    merge_audio_time: float
    transcribe_time: float
    restore_time: float


class WhisperHFRunnable(Runnable):
    def __init__(self, model_id: str = "openai/whisper-large-v3"):
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        )
        model.to(device)

        processor = AutoProcessor.from_pretrained(model_id)

        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=torch_dtype,
            device=device,
        )

    def forward(self, data: List[bytes]) -> List[str]:
        start = time.time()
        result = self.pipe(data, batch_size=len(data))
        transcribe_time = time.time() - start
        return [
            BatchOutput(
                text=r["text"],
                batched_count=len(data),
                merge_audio_time=0,
                transcribe_time=transcribe_time,
                restore_time=0,
            )
            for r in result
        ]
