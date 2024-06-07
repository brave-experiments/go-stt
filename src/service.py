import io
import os

import bentoml
from bentoml.io import JSON, File

from stt_api import app, runner_audio_transcriber

import ipc_server

svc = bentoml.Service(
    "stt",
    runners=[runner_audio_transcriber],
)

svc.mount_asgi_app(app)


@svc.on_deployment
def on_deployment():
    if not os.fork():
        ipc_server.start_ipc_server()


@svc.api(input=File(), output=JSON())
async def process_audio(input_file: io.BytesIO):
    transcript = await runner_audio_transcriber.transcribe_audio.async_run(input_file)
    return transcript
