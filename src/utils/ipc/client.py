import asyncio

if __name__=='__main__':
    import messages
else:
    from . import messages

HOST, PORT = "localhost", 3015

class Publisher:
    def __init__(self, pair):
        self._pair: str = pair
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
        async def op() :
            self._reader, self._writer = await asyncio.open_connection(HOST, PORT)
            await messages.send_request(self._writer, messages.Publish(pair))
            ready = await messages.receive_request(self._reader)
            if not isinstance(ready, messages.Ready):
                raise asyncio.InvalidStateError()

        await asyncio.wait_for(op(), timeout)


class Subscriber:
    def __init__(self, pair: str):
        self._pair: str = pair
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
        async def op() :            
            self._reader, self._writer = await asyncio.open_connection(HOST, PORT)
            await messages.send_request(self._writer, messages.Subscribe(pair))
            ready = await messages.receive_request(self._reader)
            if not isinstance(ready, messages.Ready):
                raise asyncio.InvalidStateError()

        await asyncio.wait_for(op(), timeout)

if __name__ == '__main__':
    async def publisher(pair):
        try:
            async def op():
                async with Publisher(pair) as pub:
                    for i in range(0, 30):
                        await pub.push(messages.Text(f"{pair} -> {i}", False))
                        await asyncio.sleep(1)
            await asyncio.wait_for(op(), 3)
        except Exception as e:
            print(e)
            pass

    async def subscriber(pair):
    
        try:
            async with Subscriber(pair) as sub:
                while True:
                    r = await sub.pull()
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

    async def main():
        tasks = []
        for i in range(20):
            tasks.append(asyncio.create_task(batch(str(i))))

        for t in tasks:
            await t

    asyncio.run(main())
