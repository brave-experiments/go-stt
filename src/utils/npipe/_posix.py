import os
import asyncio
import aiofiles
import aiofiles.os

class AsyncNamedPipe:
    def __init__(self, pipe):
        self._pipe = pipe

    async def create(path: str, timeout: int = 10000):
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, os.mkfifo,f"/tmp/{path}")
        except:
            pass
        
        try:
            async with asyncio.timeout(timeout / 1000.0):
                fd = await aiofiles.open(f"/tmp/{path}", "w")
                return AsyncNamedPipe(fd)
        except asyncio.TimeoutError:
            await aiofiles.os.unlink(f"/tmp/{path}")
            raise Exception("No consumer")

    async def open(path: str, timeout: int = 1000):
        pipe = None

        try:
            async with asyncio.timeout(timeout / 1000.0):
                pipe = await aiofiles.open(f"/tmp/{path}", "r")
        except asyncio.TimeoutError:
            raise Exception("No producer")

        return AsyncNamedPipe(pipe)

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
        return await self._pipe.close()
