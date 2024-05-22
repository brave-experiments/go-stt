import os
import tempfile
import asyncio
import aiofiles
import aiofiles.os
from pathlib import Path


class AsyncChannelWriter:
    def __init__(self, fd, dir: Path):
        self._fd = fd
        self._dir = dir

    async def open(pair: str, timeout: int = 10000):
        loop = asyncio.get_running_loop()

        try:
            dir = await loop.run_in_executor(None, tempfile.mkdtemp, None, pair + "-", Path.home() / "tmp" / "channels")
            dir = Path(dir)
            await loop.run_in_executor(None, os.mkfifo, dir / "pipe")
            async with asyncio.timeout(timeout / 1000.0):
                fd = await aiofiles.open(dir / "pipe", "w")
                return AsyncChannelWriter(fd, dir)

        except asyncio.TimeoutError:
            await aiofiles.os.unlink(dir / "pipe")
            await aiofiles.os.rmdir(dir)
            raise Exception("No consumer")

    async def close(self):
        await self._fd.close()
        await aiofiles.os.unlink(self._dir / "pipe")
        await aiofiles.os.rmdir(self._dir)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    def __bool__(self):
        return self._fd is not None
 
    async def write(self, data):
        await self._fd.write(data)
        await self._fd.flush()

    async def writeline(self, data):
        await self._fd.writelines([data])
        await self._fd.flush()


class AsyncChannelReader:
    def __init__(self, fd):
        self._fd = fd

    async def open(pair: str, timeout: int = 10000):
        fd = None
        try:
            async with asyncio.timeout(timeout / 1000.0):
                channels = Path.home() / "tmp" / "channels"
                dirs = None
                while not dirs:
                    dirs = list(filter(lambda d: d.startswith(f"{pair}-"),  await aiofiles.os.listdir(channels)))
                    if not dir:
                        await asyncio.sleep(0.1)

                path = channels / dirs[0] / "pipe"
                while not await aiofiles.ospath.exists(path):
                    await asyncio.sleep(0.1)

                fd = await aiofiles.open(path, "r")
        except asyncio.TimeoutError:
            raise Exception("No producer")

        return AsyncChannelReader(fd)

    async def close(self):
        await self._fd.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def read(self, size = -1):
        return await self._fd.read(size)

    async def readline(self):
        return await self._fd.readline()

