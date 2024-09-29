"""
module for defining runners
"""

import abc
import asyncio
import logging
import random
import time

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from sampuru.batch import BatchParameters
from sampuru.job import Job
from sampuru.runnable import Runnable

logger = logging.getLogger(__name__)


class Runner(abc.ABC):
    """
    a runner provides an efficient interface to perform work using a particular runnable
    """

    def __init__(
        self,
        cls,
        runnable_init_params: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        batch_params: Optional[BatchParameters] = None,
    ):
        self.name = name or f"{cls.__name__}:{random.randint(1000, 9999)}"
        self.last_observations = None

        self.batch_params = batch_params or BatchParameters()
        self.batches_processed_since_last_update = 0

        self.runnable = None
        self.runnable_cls = cls
        self.runnable_init_params = runnable_init_params or {}

        self.loop = asyncio.get_event_loop()

    @abc.abstractmethod
    async def get_observations(self) -> (List[int], List[float]):
        """
        get past records of batch processing returning a list containing the number of
        jobs processed and a list of the elapsed time to process those jobs
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def observe(self, num_jobs: int, elapsed_ms: float):
        """
        record an observed batch processing event noting the number of jobs
        processed and the elapsed time
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def create_response_future(self) -> asyncio.Future:
        """
        create a future to be be resolved when the processing for a request is
        complete
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def enqueue(self, job: Job):
        """
        enqueue a job to be processed
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_queue_length(self) -> int:
        """
        get the current length of the queue
        """
        raise NotImplementedError

    @abc.abstractmethod
    @asynccontextmanager
    async def get_batch_with_timeout(self, timeout_ms: int) -> List[Job]:
        """
        get a batch with timeout
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_jobs_per_second(self) -> float:
        """
        get the current incoming requests per second
        """
        raise NotImplementedError

    async def forward(
        self, data: List[Any], timeout_ms: Optional[int] = None
    ) -> List[Any]:
        """
        asynchronously performs a forward pass of the runnable over the data
        by job(s) submitting to the work queue. jobs in the queue will be
        processed by batching
        """
        futures = []
        try:
            if self.runnable_cls.flatten:
                # we should flatten each element of data into it's own job
                for d in data:
                    future = await self.create_response_future()
                    job = Job(
                        runnable_name=str(self.runnable_cls.__name__),
                        submitter_name=self.name,
                        data=[d],
                        future=future,
                    )
                    await self.enqueue(job)
                    futures.append(future)

                outputs = await asyncio.wait_for(
                    asyncio.gather(*futures),
                    timeout=timeout_ms / 1000 if timeout_ms else None,
                )
                return [out[0] for out in outputs]

            future = await self.create_response_future()
            futures.append(future)
            job = Job(
                runnable_name=str(self.runnable_cls.__name__),
                submitter_name=self.name,
                data=data,
                future=future,
            )
            await self.enqueue(job)
            return await asyncio.wait_for(
                future, timeout=timeout_ms / 1000 if timeout_ms else None
            )
        except asyncio.TimeoutError:
            for future in futures:
                if not future.done():
                    future.cancel("cancelling due to timeout")

    async def update_batch_size(self):
        """
        update the batch size based on current observed performance
        """
        queue_length = await self.get_queue_length()
        jobs_per_second = await self.get_jobs_per_second()
        observations = await self.get_observations()

        # need at least 3 unique observations,
        if len(set(observations[0])) > 2:
            self.last_observations = observations

        # fallback to last observations if insufficient
        previous_batch_sizes, previous_batch_times_ms = self.last_observations

        self.batch_params.update_current_size(
            queue_length, jobs_per_second, previous_batch_sizes, previous_batch_times_ms
        )
        self.batches_processed_since_last_update = 0

    async def run_warmup(self):
        """
        run in warmup mode, slowly stepping up from the minimum batch size
        to create observations for performance prediction
        """
        i = self.batch_params.min_size
        batch_warmup_increment = int(
            0.1 * (self.batch_params.max_size - self.batch_params.min_size)
        )
        while i < self.batch_params.min_size + 3 * batch_warmup_increment:
            logger.debug("run_warmup: waiting for batch size %d", i)
            self.batch_params.current_size = i
            async with self.get_batch_with_timeout(
                self.batch_params.max_latency_ms
            ) as batch:
                if not batch:
                    continue
                await self.run_batch(batch)
                if len(batch) >= self.batch_params.current_size:
                    i += batch_warmup_increment

    async def run(self, warmup: bool = False, run_forever: bool = True):
        """
        run continuously, first performing a warmup if desired
        """
        if not self.runnable:
            self.runnable = self.runnable_cls(**self.runnable_init_params)
        if warmup:
            await self.run_warmup()
            await self.update_batch_size()

        while True:
            async with self.get_batch_with_timeout(
                self.batch_params.get_timeout()
            ) as batch:
                if not batch:
                    continue
                await self.run_batch(batch)
            self.batches_processed_since_last_update += 1

            if self.batch_params.should_update(
                await self.get_jobs_per_second(),
                self.batches_processed_since_last_update,
            ):
                await self.update_batch_size()

            if not run_forever:
                break

    async def run_batch(self, jobs: List[Job]):
        """
        run a batch of jobs, flattening their data to perform a single forward pass of
        the runnable
        """

        if not self.runnable:
            self.runnable = self.runnable_cls(**self.runnable_init_params)

        # only attempt to run jobs that haven't already been completed
        # e.g. through cancellation
        jobs = [job for job in jobs if not job.future.done()]

        logger.debug("run_batch: running %d jobs", len(jobs))
        if len(jobs) > 0:
            start_time = time.time()
            try:
                outputs = await self.loop.run_in_executor(
                    None, self.runnable.forward, sum([job.data for job in jobs], [])
                )
                elapsed_ms = (time.time() - start_time) * 1000
                logger.debug("run_batch: finished execution")

                for job in jobs:
                    future = job.future
                    job_dim = len(job.data)
                    if not future.done():
                        future.set_result(outputs[:job_dim])
                    # advance the outputs
                    outputs = outputs[job_dim:]
                logger.debug("run_batch: set results")

                await self.observe(len(jobs), elapsed_ms)
                logger.debug(
                    "run_batch: recorded observation, ran %d jobs in %fms",
                    len(jobs),
                    elapsed_ms,
                )
            except Exception as e:
                logger.exception("run_batch: execution failed")
                for job in jobs:
                    if not job.future.done():
                        job.future.set_exception(e)
