"""
runner tests
"""

import asyncio
import logging
import time

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import pytest

from sampuru.batch import BatchParameters
from sampuru.job import Job
from sampuru.runnable import Runnable
from sampuru.runner import Runner

logger = logging.getLogger(__name__)


class MockRunner(Runner):
    def __init__(
        self,
        cls,
        runnable_init_params: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        batch_params: Optional[BatchParameters] = None,
    ):
        super().__init__(cls, runnable_init_params, name, batch_params)
        self.observations = []
        self.queue = asyncio.Queue()

    async def get_observations(self) -> (List[int], List[float]):
        jobs_processed = [obs[0] for obs in self.observations]
        elapsed_times = [obs[1] for obs in self.observations]
        return jobs_processed, elapsed_times

    async def observe(self, num_jobs: int, elapsed_ms: float):
        self.observations.append((num_jobs, elapsed_ms))

    async def create_response_future(self) -> asyncio.Future:
        return asyncio.Future()

    async def enqueue(self, job: Job):
        await self.queue.put(job)

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
                    if len(batch) >= self.batch_params.current_size:
                        break
        except asyncio.TimeoutError:
            pass
        if batch:
            yield batch
            for job in batch:
                self.queue.task_done()

    async def get_jobs_per_second(self) -> float:
        return 100.0


class MockRunnable(Runnable):
    flatten = False

    def __init__(self, *args, **kwargs):
        pass

    def forward(self, data):
        return data


class FlatMockRunnable(MockRunnable):
    flatten = True


class ExceptionMockRunnable(MockRunnable):
    def forward(self, data):
        raise Exception("error in forward")


@pytest.mark.asyncio
async def test_runner_init():
    runner = MockRunner(MockRunnable, name="test_runner")
    assert runner.name == "test_runner"
    assert isinstance(runner.batch_params, BatchParameters)
    assert runner.runnable is None
    assert runner.runnable_cls == MockRunnable
    assert runner.runnable_init_params == {}


@pytest.mark.asyncio
async def test_runner_forward():
    runner = MockRunner(MockRunnable)
    data = [1, 2, 3]
    out = asyncio.create_task(runner.forward(data))
    # forward should enqueue a single job given flatten = False
    job = await asyncio.wait_for(runner.queue.get(), timeout=0.1)
    # the job data should be as expected
    assert job.data == data
    # if we resolve the future we should get the expected output from forward
    job.future.set_result(data)
    assert await out == data

    runner = MockRunner(FlatMockRunnable)
    out = asyncio.create_task(runner.forward(data))
    # forward should enqueue a three jobs given flatten = False
    job1 = await asyncio.wait_for(runner.queue.get(), timeout=0.1)
    job2 = await asyncio.wait_for(runner.queue.get(), timeout=0.1)
    job3 = await asyncio.wait_for(runner.queue.get(), timeout=0.1)
    # if we resolve the future we should get the combined output from forward
    job1.future.set_result([data[0]])
    job2.future.set_result([data[1]])
    job3.future.set_result([data[2]])
    assert await out == data


@pytest.mark.asyncio
async def test_runner_run_batch():
    runner = MockRunner(MockRunnable, batch_params=BatchParameters(current_size=2))
    jobs = [
        Job(
            runnable_name="MockRunnable",
            submitter_name="test_runner",
            data=[1, 2],
            future=asyncio.Future(),
        ),
        Job(
            runnable_name="MockRunnable",
            submitter_name="test_runner",
            data=[3, 4],
            future=asyncio.Future(),
        ),
        Job(
            runnable_name="MockRunnable",
            submitter_name="test_runner",
            data=[5],
            future=asyncio.Future(),
        ),
    ]
    for job in jobs:
        await runner.enqueue(job)

    async with runner.get_batch_with_timeout(timeout_ms=1000) as batch:
        await runner.run_batch(batch)

    assert len(runner.observations) == 1
    assert runner.observations[0][0] == 2  # Number of jobs processed
    assert runner.observations[0][1] > 0  # Elapsed time

    for job in jobs[:2]:
        assert job.future.done()
        assert job.future.result() == job.data

    assert not jobs[2].future.done()
    assert not jobs[2].future.set_result([])

    runner = MockRunner(ExceptionMockRunnable)
    jobs[0].future = asyncio.Future()
    await runner.enqueue(jobs[0])
    async with runner.get_batch_with_timeout(timeout_ms=1000) as batch:
        await runner.run_batch(batch)
    # an exception within the runnable should be propogated to the job future
    with pytest.raises(Exception):
        await jobs[0].future


@pytest.mark.asyncio
async def test_runner_run():
    runner = MockRunner(MockRunnable, batch_params=BatchParameters(current_size=1))
    data = [1, 2, 3]
    asyncio.create_task(runner.run(run_forever=False))
    result = await runner.forward(data)
    assert result == data
