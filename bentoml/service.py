import io
import asyncio
import bentoml
from bentoml.io import JSON, File
from runners.audio_transcriber import AudioTranscriber
import tempfile

runner_audio_transcriber = bentoml.Runner(
    AudioTranscriber,
    name="audio_transcriber",
)

svc = bentoml.Service(
    "stt",
    runners=[ runner_audio_transcriber ],
)

@svc.api(input=File(), output=JSON())
async def process_audio(input_file: io.BytesIO):
    path = tempfile.NamedTemporaryFile().name
    with open(path, "wb") as f:
        f.write(input_file.read())

    transcript = await runner_audio_transcriber.transcribe_audio.async_run(path)
    return transcript