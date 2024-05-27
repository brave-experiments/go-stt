import json
import io

import bentoml
from  runners.audio_transcriber import AudioTranscriber

from fastapi import FastAPI, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.encoders import jsonable_encoder

import utils.google_streaming.google_streaming_api_pb2 as speech
from utils.npipe import AsyncChannelWriter, AsyncChannelReader
from utils.service_key.brave_service_key import check_stt_request


runner_audio_transcriber = bentoml.Runner(
    AudioTranscriber,
    name="audio_transcriber",
)

class RecongitionEvent:
    def __init__(self):
        self._event = speech.SpeechRecognitionEvent()

    def add_text(self, text: str):
        r = speech.SpeechRecognitionResult()
        r.stability = 1.0
        r.final = False
        r.alternative.append(speech.SpeechRecognitionAlternative(transcript=text))
        self._event.result.append(r)

    def to_bytes(self):
        message = self._event.SerializeToString()
        return len(message).to_bytes(4, signed=False) + message

app = FastAPI()

@app.post("/up")
async def handleUpstream(
    pair: str,
    request: Request,
    is_valid_brave_key = Depends(check_stt_request)
):
    if not is_valid_brave_key:
        return JSONResponse(content = jsonable_encoder({ "status" : "Invalid Brave Service Key" }))

    try:
        mic_data = bytes()
        async with await AsyncChannelWriter.open(pair) as pipe:
                async for chunk in request.stream():
                    if len(chunk) == 0:
                        break
                    mic_data += chunk
                    text = await runner_audio_transcriber.async_run(io.BytesIO(mic_data))
                    await pipe.write(text["text"] + '\n')

    except Exception as e:
        return JSONResponse(content = jsonable_encoder({ "status" : "exception", "exception" : str(e) }) )

    return JSONResponse(content = jsonable_encoder({ "status" : "ok" }))

@app.get("/down")
async def handleDownstream(
    pair: str,
    output: str = "pb",
    is_valid_brave_key = Depends(check_stt_request)
):
    if not is_valid_brave_key:
        return JSONResponse(content = jsonable_encoder({ "status" : "Invalid Brave Service Key" }))

    async def handleStream(pair):
        try:
            async with await AsyncChannelReader.open(pair) as pipe:
                while True:
                    text = await pipe.readline()
                    if not text:
                        break
                    text = text.strip('\n')
                    if output == "pb":
                        event = RecongitionEvent()
                        event.add_text(text)

                        yield event.to_bytes()
                    else:
                        yield json.dumps({ "text" : text })
        except Exception as e:
            yield json.dumps({ "exception" : str(e)})

    return StreamingResponse(handleStream(pair))
