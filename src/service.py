import io
import bentoml
from bentoml.io import JSON, File
from runners.audio_transcriber import AudioTranscriber
from stt_api import app, runner_random_generator

runner_audio_transcriber = bentoml.Runner(
    AudioTranscriber,
    name="audio_transcriber",
)

svc = bentoml.Service(
    "stt",
    runners=[ runner_audio_transcriber, runner_random_generator ],
)

svc.mount_asgi_app(app)

@svc.api(input=File(), output=JSON())
async def process_audio(input_file: io.BytesIO):
    transcript = await runner_audio_transcriber.transcribe_audio.async_run(input_file)
    return transcript

@svc.api(input=File(), output=JSON())
async def process_audio_data(input_file: io.BytesIO):
    transcript = await runner_audio_transcriber.transcribe_audio_data.async_run(input_file.read())
    return transcript

