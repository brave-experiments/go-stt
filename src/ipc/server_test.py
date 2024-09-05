import asyncio

import pytest

from stt.ipc.client import Publisher, Subscriber
from stt.ipc import messages
from stt.ipc.server import run_ipc_server


async def publisher(pair):
    async def op():
        async with Publisher(pair) as pipe:
            for i in range(0, 30):
                await pipe.push(messages.Text(f"{pair} -> {i}", False))
                await asyncio.sleep(1)

    try:
        await asyncio.wait_for(op(), 3)
    except Exception as e:
        print(e)
        pass


async def subscriber(pair):
    try:
        async with Subscriber(pair) as pipe:
            while True:
                r = await pipe.pull()
                if r is None:
                    break
                print(r)

    except asyncio.IncompleteReadError:
        pass
    except Exception as e:
        print(e)
        pass


async def batch(pair):
    try:
        await asyncio.gather(subscriber(pair), publisher(pair))
    except Exception as e:
        print(e)
        pass
    print("done")


@pytest.mark.asyncio
async def test_server():
    srv = asyncio.create_task(run_ipc_server("localhost", 3015))

    tasks = []
    for i in range(20):
        tasks.append(asyncio.create_task(batch(str(i))))
    for t in tasks:
        await t
    srv.cancel()
