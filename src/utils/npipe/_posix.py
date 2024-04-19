import os
import asyncio
import aiofile

class AsyncNamedPipe:
    def __init__(self):
        self._pipe = None
    
    async def create(self, path):
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, os.mkfifo(f"/tmp/{path}"))
        except:
            pass

        self._pipe = await aiofile.async_open(f"/tmp/{path}")

    async def open(self, path):
        self._pipe = await aiofile.async_open(f"/tmp/{path}")

    async def write(self, data):
        return self._pipe.write(data)

    async def read(self, timeout=1000):
        return self._pipe.read()

    async def close(self):
        return self._pipe.close()
