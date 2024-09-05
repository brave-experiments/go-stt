import asyncio
import collections
import logging
import time

from contextlib import asynccontextmanager
from typing import Any, List

from sampuru.runner import Runner, Job

logger = logging.getLogger(__name__)


class LocalRunner(Runner):
    """
    a local runner which keeps jobs in a collections.deque
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = asyncio.Queue()
        self.waker = asyncio.Condition()

        self.x = collections.deque(maxlen=self.batch_params.max_observations)
        self.y = collections.deque(maxlen=self.batch_params.max_observations)

        self.request_count = 0
        self.request_count_history = collections.deque(maxlen=30)

    async def run(self, *args, loop, **kwargs):
        self.loop = loop
        self.loop.create_task(self.tock())
        await super().run(*args, **kwargs)

    async def get_observations(self) -> (List[int], List[float]):
        return list(self.x), list(self.y)

    async def observe(self, num_jobs: int, elapsed_ms: float):
        self.x.append(num_jobs)
        self.y.append(elapsed_ms)

    async def create_response_future(self) -> asyncio.Future:
        return self.loop.create_future()

    async def enqueue(self, job: Job):
        self.request_count += 1
        await self.queue.put(job)

    async def get_queue_length(self) -> int:
        return self.queue.qsize()

    async def get_from_queue(self) -> Job:
        try:
            return await self.queue.get()
        except RuntimeError as e:
            if str(e) != "Event loop is closed":
                raise e

    @asynccontextmanager
    async def get_batch_with_timeout(self, timeout_ms: int = None) -> List[Job]:
        batch = []
        start_time = time.time()
        try:
            while True:
                remaining_timeout_s = None
                if timeout_ms:
                    elapsed_time_s = time.time() - start_time
                    remaining_timeout_s = max(
                        (timeout_ms / 1000) - elapsed_time_s, 0.001
                    )
                job = await asyncio.wait_for(
                    self.get_from_queue(), timeout=remaining_timeout_s
                )
                if job:
                    batch.append(job)
                    if len(batch) >= self.batch_params.max_size:
                        break
                    if (
                        await self.get_queue_length()
                        > 2 * self.batch_params.current_size
                    ):
                        continue
                    if len(batch) >= self.batch_params.current_size:
                        break
        except asyncio.TimeoutError:
            pass
        yield batch
        for job in batch:
            self.queue.task_done()

    async def tock(self):
        while True:
            self.request_count_history.append(self.request_count)
            self.request_count = 0
            await asyncio.sleep(1)

    async def get_jobs_per_second(self):
        return sum(self.request_count_history) / len(self.request_count_history)
