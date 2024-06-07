import asyncio
from . import messages


class Publisher:
    def __init__(self, pair, host="localhost", port=3015):
        self._pair: str = pair
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader = None
        self._writer: asyncio.StreamReader = None

    def __del__(self):
        if self._writer:
            self._writer.close()

    async def __aenter__(self):
        await self._open(self._pair)
        return self

    async def __aexit__(self, *_):
        if self._writer:
            self._writer.close()

    async def push(self, r: messages.Text):
        await messages.send_request(self._writer, r)

    async def _open(self, pair: str, timeout: float = 10.0):
        async def op():
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
            await messages.send_request(self._writer, messages.Publish(pair))
            ready = await messages.receive_request(self._reader)
            if not isinstance(ready, messages.Ready):
                raise asyncio.InvalidStateError()

        await asyncio.wait_for(op(), timeout)


class Subscriber:
    def __init__(self, pair: str, host="localhost", port=3015):
        self._pair: str = pair
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader = None
        self._writer: asyncio.StreamReader = None

    def __del__(self):
        if self._writer:
            self._writer.close()

    async def __aenter__(self):
        await self._open(self._pair)
        return self

    async def __aexit__(self, *_):
        if self._writer:
            self._writer.close()

    async def pull(self) -> messages.Text:
        try:
            r = await messages.receive_request(self._reader)
        except asyncio.IncompleteReadError:
            return None

        if not isinstance(r, messages.Text):
            raise asyncio.InvalidStateError()
        return r

    async def _open(self, pair: str, timeout: float = 10.0):
        async def op():
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
            await messages.send_request(self._writer, messages.Subscribe(pair))
            ready = await messages.receive_request(self._reader)
            if not isinstance(ready, messages.Ready):
                raise asyncio.InvalidStateError()

        await asyncio.wait_for(op(), timeout)