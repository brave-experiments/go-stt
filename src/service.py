import asyncio
import logging
import os

from threading import Thread

from .stt_api import app, runner_audio_transcriber
from .ipc import run_ipc_server

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    level=logging.DEBUG,
    datefmt="%Y-%m-%d %H:%M:%S",
)


def start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def multiprocessing_startup():
    loop = asyncio.new_event_loop()
    loop.create_task(run_ipc_server("localhost", 3015))
    t = Thread(target=start_background_loop, args=(loop,), daemon=True)
    t.start()


@app.on_event("startup")
async def app_startup():
    loop = asyncio.get_event_loop()
    loop.create_task(runner_audio_transcriber.run(loop=loop, warmup=True))

    logger = logging.getLogger("uvicorn.access")
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s")
    )
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)


multiprocessing_startup()
