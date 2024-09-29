import torch

from faster_whisper import decode_audio

from silero_vad import (get_speech_timestamps, load_silero_vad, collect_chunks)

import numpy as np
import io


def len2secs(x, sample_rate=16000):
    return x / sample_rate


def buf2secs(buf, sample_rate=16000):
    return len2secs(len(buf), sample_rate)


def secs2len(secs, sample_rate=16000):
    return round(secs * 16000)


def split_speech_timestamps(speech_timestamps, buffered, split_time):
    max_offset = secs2len(split_time)
    buffered = secs2len(buffered)

    timestamps = []
    while speech_timestamps:
        timestamps.append([])
        while speech_timestamps and speech_timestamps[0][
                "end"] < max_offset - buffered:
            timestamps[-1].append(speech_timestamps.pop(0))

        max_offset += secs2len(split_time)
        buffered = 0

    return timestamps


class StreamTranscriber:

    def __init__(self, loop, pool):

        self._raw_stream_data = bytes()
        self._raw_stream_data_duration = 0

        self._vad_detected_offset = 0
        self._speech_audio_buffers = []
        self._speech_timestamps = []
        self._last_chunk_received = False

        self._vad_model = load_silero_vad()

        self._min_speech_duration_ms = 125
        self._min_silence_duration_ms = 125
        self._speech_pad_ms = 125

        self.loop = loop
        self.pool = pool

    async def consume(self, stream_data: bytes):
        self._last_chunk_received = len(stream_data) == 0

        self._raw_stream_data += stream_data
        try:
            raw_audio_buffer = decode_audio(io.BytesIO(self._raw_stream_data))
            raw_audio_buffer = raw_audio_buffer[self._vad_detected_offset:]
        except Exception as e:
            return

        self._raw_stream_data_duration = buf2secs(raw_audio_buffer)

        speech_timestamps = get_speech_timestamps(
            raw_audio_buffer,
            self._vad_model,
            min_speech_duration_ms=self._min_speech_duration_ms,
            min_silence_duration_ms=self._min_silence_duration_ms,
            speech_pad_ms=self._speech_pad_ms)

        if not speech_timestamps:
            return

        if not self._last_chunk_received:
            # remove the speech chunks which probably are not ended
            while (speech_timestamps
                   and speech_timestamps[-1]["end"] > len(raw_audio_buffer) -
                   self._min_silence_duration_ms * 16):
                del speech_timestamps[-1]

            if not speech_timestamps:
                return

        self._vad_detected_offset += speech_timestamps[-1]["end"]

        buffered = 0
        if self._speech_audio_buffers:
            buffered = buf2secs(self._speech_audio_buffers[-1])

        speech_timestamps = split_speech_timestamps(
            speech_timestamps,
            buffered,
            5,
        )

        for chunks in speech_timestamps:
            speech = collect_chunks(
                chunks, torch.tensor(raw_audio_buffer,
                                     dtype=torch.float32)).numpy()
            if (not self._speech_audio_buffers
                    or buf2secs(self._speech_audio_buffers[-1]) > 5):
                self._speech_audio_buffers.append(speech)
            else:
                self._speech_audio_buffers[-1] = np.append(
                    self._speech_audio_buffers[-1], speech)

    def should_transcribe(self):
        if not self._speech_audio_buffers:
            return False
        if buf2secs(self._speech_audio_buffers[0]) > 1:
            return True
        if self._raw_stream_data_duration > 3:
            return True
        return self._last_chunk_received

    def get_speech_audio(self) -> bytes:
        assert self.should_transcribe()

        return self._speech_audio_buffers.pop(0).tobytes()
