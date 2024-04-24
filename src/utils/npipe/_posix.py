import os
import asyncio
import aiofiles
import aiofiles.os
from contextlib import contextmanager

class AsyncNamedPipe:
    def __init__(self, pipe, path,  creator = False):
        self._pipe = pipe
        self._path = path
        self._creator = creator

    async def create(path: str, timeout: int = 10000):
        loop = asyncio.get_running_loop()
        path = f"/tmp/{path}"
        try:
            await loop.run_in_executor(None, os.mkfifo, path)
        except:
            pass
        
        try:
            async with asyncio.timeout(timeout / 1000.0):
                fd = await aiofiles.open(path, "w")
                return AsyncNamedPipe(fd, path, True)

        except asyncio.TimeoutError:
            await aiofiles.os.unlink(path)
            raise Exception("No consumer")

    async def open(path: str, timeout: int = 1000):
        pipe = None
        path = f"/tmp/{path}"
        try:
            async with asyncio.timeout(timeout / 1000.0):
                while not await aiofiles.ospath.exists(path):
                    await asyncio.sleep(0.1)
                pipe = await aiofiles.open(path, "r")
        except asyncio.TimeoutError:
            raise Exception("No producer")

        return AsyncNamedPipe(pipe, path)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return await self.close()

    def __bool__(self):
        return self._pipe is not None
 
    async def write(self, data):
        await self._pipe.write(data)
        await self._pipe.flush()

    async def writeline(self, data):
        await self._pipe.writelines([data])
        await self._pipe.flush()

    async def read(self, size = -1):
        return await self._pipe.read(size)

    async def readline(self):
        return await self._pipe.readline()


    async def close(self):
        if self._creator:
            await aiofiles.os.unlink(self._path)

        return await self._pipe.close()
