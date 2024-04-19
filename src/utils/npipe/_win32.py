import asyncio
import win32pipe
import win32file
import pywintypes
import win32event

class AsyncNamedPipe:
    def __init__(self):
        self._pipe = None
        self._overlapped = pywintypes.OVERLAPPED()
    
    async def create(self, path):
        self._pipe = win32pipe.CreateNamedPipe(
            rf"\\.\pipe\{path}",
            win32pipe.PIPE_ACCESS_DUPLEX | win32file.FILE_FLAG_OVERLAPPED,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536,
            0,
            None)
        self._overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)
        win32pipe.ConnectNamedPipe(self._pipe, self._overlapped)
        await self._wait_for_overlapped(self._overlapped)

    async def open(self, path):
        self._overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)
        self._pipe = win32file.CreateFile(
            rf"\\.\pipe\{path}",
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            win32file.FILE_FLAG_OVERLAPPED,
            None)
        await self._wait_for_overlapped(self._overlapped)

    async def write(self, data):
        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)
        win32file.WriteFile(self._pipe, data, overlapped)
        await self._wait_for_overlapped(overlapped)

    async def read(self, timeout=1000):
        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)
        buffer = win32file.AllocateReadBuffer(65536)
        win32file.ReadFile(self._pipe, buffer, overlapped)
        await self._wait_for_overlapped(overlapped, timeout)
        n_bytes  = win32file.GetOverlappedResult(self._pipe, overlapped, True)
        return bytes(buffer[:n_bytes])

    async def close(self):
        win32file.CloseHandle(self._pipe)
        self._pipe = None

    async def _wait_for_overlapped(self, overlapped, timeout=1000):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._wait_for_overlapped_blocking, overlapped, timeout)

    def _wait_for_overlapped_blocking(self, overlapped, timeout):
        result = win32event.WaitForSingleObject(overlapped.hEvent, timeout)
        if result == win32event.WAIT_OBJECT_0:
            _ = win32file.GetOverlappedResult(self._pipe, overlapped, True)
            return True
        return False