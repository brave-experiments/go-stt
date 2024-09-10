import asyncio
import json
from datetime import datetime

from concurrent.futures import ProcessPoolExecutor

import numpy as np

from fastapi import FastAPI, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.encoders import jsonable_encoder

from sampuru import LocalRunner, BatchParameters

from .utils.google_streaming import google_streaming_api_pb2 as speech
from .utils.service_key.brave_service_key import check_stt_request

from .ipc import (
    client as ipc_client,
    messages as ipc_messages,
)
from .stream_transcriber import StreamTranscriber

from .runners.audio_transcriber import (
    WhisperHFRunnable,
)

runner_audio_transcriber = LocalRunner(
    WhisperHFRunnable,
    name="audio_transcriber",
    runnable_init_params={
        "model_id": "distil-whisper/distil-large-v3",
    },
    batch_params=BatchParameters(max_size=32),
)
vad_executor_pool = ProcessPoolExecutor()


def TextToProtoMessage(text: ipc_messages.Text):
    event = speech.SpeechRecognitionEvent()
    rr = speech.SpeechRecognitionResult()
    rr.stability = 1.0
    rr.final = text.final
    rr.alternative.append(speech.SpeechRecognitionAlternative(transcript=text.text))
    event.result.append(rr)

    proto = event.SerializeToString()
    return len(proto).to_bytes(4, "big", signed=False) + proto


app = FastAPI()


@app.get("/sticky")
async def handleSticky():
    pass


@app.post("/up")
async def handleUpstream(
    pair: str,
    request: Request,
    lang: str = "en",
    # is_valid_brave_key=Depends(check_stt_request),
    is_valid_brave_key=True,
):
    if not is_valid_brave_key:
        return JSONResponse(
            content=jsonable_encoder({"status": "Invalid Brave Service Key"})
        )

    try:
        mic_data = bytes()
        text = ""
        stream = StreamTranscriber(asyncio.get_event_loop(), vad_executor_pool)
        async with ipc_client.Publisher(pair) as pipe:
            try:
                async for chunk in request.stream():
                    await stream.consume(chunk)

                    while stream.should_transcribe():
                        process_time = datetime.now()
                        transciption = await runner_audio_transcriber.forward(
                            [
                                {
                                    "raw": np.frombuffer(
                                        stream.get_speech_audio(), dtype=np.float32
                                    ),
                                    "sampling_rate": 16000,
                                }
                            ]
                        )
                        process_time = (datetime.now() - process_time).total_seconds()

                        out = transciption[0]
                        # print( pair, " : ", out.batched_count, "", out.merge_audio_time, " ", out.transcribe_time, " ", out.restore_time,)

                        if out.text:
                            print(out.text.lower())
                            text += out.text.lower() + " "
                            await pipe.push(
                                ipc_messages.Text(
                                    text,
                                    False,
                                    len(mic_data),
                                    out.merge_audio_time
                                    + out.transcribe_time
                                    + out.restore_time,
                                    process_time,
                                )
                            )

            finally:
                if text:
                    await pipe.push(ipc_messages.Text(text, True))

    except Exception as e:
        raise
        return JSONResponse(
            content=jsonable_encoder({"status": "exception", "exception": str(e)})
        )

    return JSONResponse(content=jsonable_encoder({"status": "ok"}))


@app.get("/down")
async def handleDownstream(
    pair: str,
    output: str = "pb",  # is_valid_brave_key=Depends(check_stt_request)
    is_valid_brave_key=True,
):
    if not is_valid_brave_key:
        return JSONResponse(
            content=jsonable_encoder({"status": "Invalid Brave Service Key"})
        )

    async def handleStream(pair):
        try:
            async with ipc_client.Subscriber(pair) as pipe:
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
                                "time": text.time,
                            }
                        )
        except Exception as e:
            yield json.dumps({"exception": str(e)})

    return StreamingResponse(handleStream(pair))
