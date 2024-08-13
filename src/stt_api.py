import json
import io
from datetime import datetime

import bentoml
from runners.audio_transcriber import (
    AudioTranscriber,
    BatchableAudioTranscriber,
    BatchInput,
)

from fastapi import FastAPI, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.encoders import jsonable_encoder

import utils.google_streaming.google_streaming_api_pb2 as speech
from utils.service_key.brave_service_key import check_stt_request

import utils.ipc as ipc

runner_audio_transcriber = bentoml.Runner(
    BatchableAudioTranscriber,
    name="audio_transcriber",
    max_batch_size=10,
)


def TextToProtoMessage(text: ipc.messages.Text):
    event = speech.SpeechRecognitionEvent()
    rr = speech.SpeechRecognitionResult()
    rr.stability = 1.0
    rr.final = text.final
    rr.alternative.append(speech.SpeechRecognitionAlternative(transcript=text.text))
    event.result.append(rr)

    proto = event.SerializeToString()
    return len(proto).to_bytes(4, signed=False) + proto


app = FastAPI()


@app.get("/sticky")
async def handleSticky():
    pass


@app.post("/up")
async def handleUpstream(
    pair: str,
    request: Request,
    lang: str = "en",
    is_valid_brave_key=Depends(check_stt_request),
):
    if not is_valid_brave_key:
        return JSONResponse(
            content=jsonable_encoder({"status": "Invalid Brave Service Key"})
        )

    try:
        mic_data = bytes()
        text = ""
        async with ipc.client.Publisher(pair) as pipe:
            try:
                async for chunk in request.stream():
                    if len(chunk) == 0:
                        break
                    mic_data += chunk
                    process_time = datetime.now()
                    transciption = await runner_audio_transcriber.async_run(
                        [BatchInput(audio=mic_data, lang=lang, pair=pair)]
                    )
                    process_time = datetime.now() - process_time

                    text = transciption[0]
                    if text:
                        await pipe.push(
                            ipc.messages.Text(
                                text, False, len(mic_data), process_time.total_seconds()
                            )
                        )
            finally:
                if text:
                    await pipe.push(ipc.messages.Text(text, True))

    except Exception as e:
        return JSONResponse(
            content=jsonable_encoder({"status": "exception", "exception": str(e)})
        )

    return JSONResponse(content=jsonable_encoder({"status": "ok"}))


@app.get("/down")
async def handleDownstream(
    pair: str, output: str = "pb", is_valid_brave_key=Depends(check_stt_request)
):
    if not is_valid_brave_key:
        return JSONResponse(
            content=jsonable_encoder({"status": "Invalid Brave Service Key"})
        )

    async def handleStream(pair):
        try:
            async with ipc.client.Subscriber(pair) as pipe:
                while True:
                    text = await pipe.pull()
                    if not text:
                        break
                    if output == "pb":
                        yield TextToProtoMessage(text)
                    else:
                        yield json.dumps(
                            {
                                "text": text.text,
                                "final": text.final,
                                "buffer": text.buffer_len,
                                "process_time": text.process_time,
                            }
                        )
        except Exception as e:
            yield json.dumps({"exception": str(e)})

    return StreamingResponse(handleStream(pair))
