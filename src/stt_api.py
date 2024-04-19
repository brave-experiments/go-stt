from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import google_streaming_api_pb2 as speech
from runners.random_generator import RandomGenerator
import bentoml
from utils.npipe import AsyncNamedPipe
import asyncio

runner_random_generator = bentoml.Runner(
    RandomGenerator,
    name="random_generator",
)

class FlacDecoder:
    def __init__(self):
        self.decoder = pyflac.StreamDecoder(self.callback)
        self.samples = asyncio.Queue()

    def callback(self, data, sample_rate, num_channerls, num_samples):
        self.samples.put(data)

    def feed(self, data):
        self.decoder.process(data)


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

clients = {}

@app.post("/up")
async def handleUpstream(pair: str, request: Request):
    pipe = AsyncNamedPipe()
    await pipe.create(pair)

    async for chunk in request.stream():
        await pipe.write(chunk)

    await pipe.close()
    return ""

@app.get("/down")
async def handleDownstream(pair:str):
    await asyncio.sleep(0.1)

    async def handleStream(pair):
        event = RecongitionEvent()
        pipe = AsyncNamedPipe()

        await pipe.open(pair)

        while True:
            chunk = await pipe.read()
            if chunk is None:
                break

            text = await runner_random_generator.async_run(chunk)
            event.add_text(str(text))

            yield event.to_bytes()

        await pipe.close()

    return StreamingResponse(handleStream(pair))


