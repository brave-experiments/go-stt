import asyncio
import collections
import json
import logging
import time

from contextlib import asynccontextmanager
from typing import List

import redis

from sampuru.runner import Runner, Job

logger = logging.getLogger(__name__)

redis_host = "localhost"
stream_key = "skey"
stream2_key = "s2key"
group1 = "grp1"

list_key = "lke"

# TODO
# - truncate stream  ( XTRIM ~ rps * 5 * 60 )
#   - delete old streams
# - truncate list
# - rename keys / groups
# - handle multiple workers


class RedisRunner(Runner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_count = 0

        self.pool = redis.asyncio.ConnectionPool.from_url("redis://localhost")
        # self.r.ping()

        self.futures = {}

        self.request_count_history = collections.deque(maxlen=30)

    async def get_observations(self) -> (List[int], List[float]):
        client = redis.asyncio.Redis(connection_pool=self.pool)
        result = await client.lrange(list_key, 0, -1)

        x = []
        y = []
        for elem in result:
            # get string value
            tmp = elem.decode("utf-8")

            _x, _y = tmp.split(":")
            x.append(int(_x))
            y.append(float(_y))
        return x, y

    async def observe(self, batch_size: int, elapsed_s: float):
        # FIXME may want to ensure not all one x value
        client = redis.asyncio.Redis(connection_pool=self.pool)
        await client.rpush(list_key, f"{batch_size}:{elapsed_s}")

    async def create_response_future(self):
        return self.loop.create_future()

    def get_current_stream_key(self):
        return self.get_stream_key(time.time())

    def get_previous_stream_key(self):
        return self.get_stream_key(time.time() - 60)

    def get_stream_key(self, timestamp: int = None):
        return f"{stream_key}:{int(timestamp / 60)}"

    async def enqueue(self, job: Job):
        client = redis.asyncio.Redis(connection_pool=self.pool)
        self.request_count += 1
        jid = await client.xadd(
            self.get_current_stream_key(),
            {"data": json.dumps(job.data).encode("utf-8"), "submitter": job.submitter},
        )
        self.futures[jid] = job.future

    @asynccontextmanager
    async def get_batch_with_timeout(self, timeout_s):
        # FIXME
        client = redis.asyncio.Redis(connection_pool=self.pool)
        streams = [self.get_previous_stream_key(), self.get_current_stream_key()]
        for stream in streams:
            try:
                await client.xgroup_create(stream, group1, mkstream=True)
            except Exception as e:
                pass
        logger.debug(
            "get_batch_with_timeout: waiting up to %fs for %d items",
            timeout_s,
            self.batch_size,
        )
        reply = await client.xreadgroup(
            groupname=group1,
            consumername=self.name,
            block=int(timeout_s * 1000),
            count=self.batch_size,
            streams={stream: ">" for stream in streams},
        )
        batch = []
        if len(reply) > 0:
            for d_stream in reply:
                for element in d_stream[1]:
                    future = await self.create_response_future()
                    job = Job(
                        data=json.loads(element[1][b"data"].decode("utf-8")),
                        future=future,
                        jid=element[0],
                        submitter=element[1][b"submitter"],
                        metadata={"stream_name": d_stream[0]},
                    )
                    batch.append(job)

        try:
            yield batch
        finally:
            for job in batch:
                await client.xadd(
                    f"{stream2_key}:{job.submitter}",
                    {
                        "orig_jid": job.jid,
                        "data": json.dumps(await job.future).encode("utf-8"),
                    },
                )
                await client.xack(job.metadata["stream_name"], group1, job.jid)

    async def handle_responses(self):
        client = redis.asyncio.Redis(connection_pool=self.pool)
        try:
            await client.xgroup_create(
                f"{stream2_key}:{self.name}", group1, mkstream=True
            )
        except Exception as e:
            pass

        while True:
            reply = await client.xreadgroup(
                groupname=group1,
                consumername=self.name,
                block=1000,
                streams={f"{stream2_key}:{self.name}": ">"},
            )
            if len(reply) > 0:
                d_stream = reply[0]
                for element in d_stream[1]:
                    jid = element[1][b"orig_jid"]
                    response = json.loads(element[1][b"data"].decode("utf-8"))
                    if jid in self.futures and not self.futures[jid].done():
                        self.futures[jid].set_result(response)
                    await client.xack(d_stream[0], group1, jid)

    async def run(self, warmup: bool = False):
        self.loop.create_task(self.tock())
        await super().run(warmup)

    async def tock(self):
        client = redis.asyncio.Redis(connection_pool=self.pool)
        last_entries_added = {}
        while True:
            try:
                stream_key = self.get_current_stream_key()
                result = await client.xinfo_stream(stream_key)
                entries_added = result["entries-added"]
                active_consumers = await client.xinfo_consumers(stream_key, group1)
                # TODO cleanup last entries and consumers
                if stream_key in last_entries_added:
                    # given request_count_history averaging, per worker rps will slowly go up/down
                    self.request_count_history.append(
                        (entries_added - last_entries_added[stream_key])
                        / len(active_consumers)
                    )
                last_entries_added[stream_key] = entries_added
            except Exception as e:
                # print("tock exception", e)
                pass
            await asyncio.sleep(1)

    async def get_rps(self):
        return sum(self.request_count_history) / len(self.request_count_history)


class RemoteRedisRunner(RedisRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, remote=True)

    async def run(self, warmup: bool = False):
        await self.handle_responses()
