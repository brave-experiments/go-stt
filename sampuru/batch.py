"""
module for defining the parameters for forming batches
"""

import logging
import time

from dataclasses import dataclass
from typing import List, Optional

from scipy import stats


logger = logging.getLogger(__name__)


@dataclass
class BatchParameters:
    """
    configuration for batching of requests
    """

    current_size: int = 1
    max_latency_ms: int = 1000
    max_observations: int = 50
    max_size: int = 10
    min_size: int = 1
    predicted_time_ms: int = 0
    update_interval_s: int = 10
    last_updated_at: float = 0

    def update_current_size(
        self,
        queue_length: int,
        jobs_per_second: float,
        previous_batch_sizes: List[int],
        previous_batch_times_ms: List[float],
    ):
        """
        calculate the optimal batch size given the configuration, current
        observed incoming jobs per second and observed runtime of past batches
        """

        logger.info(
            "update_current_size: before update - queue length %d, "
            + "incoming jobs per second: %f, batch size %d, predicted batch time %f ms",
            queue_length,
            jobs_per_second,
            self.current_size,
            self.predicted_time_ms,
        )
        batch_size = self.min_size
        slope, intercept = self.regress_observations(
            previous_batch_sizes, previous_batch_times_ms
        )
        while batch_size < self.max_size:
            predicted_batch_time_ms = self.predict(slope, intercept, batch_size)
            predicted_throughput = (batch_size / predicted_batch_time_ms) * 1000
            if jobs_per_second < predicted_throughput:
                self.current_size = batch_size
                break
            batch_size += 1
        else:
            self.current_size = self.max_size
        self.predicted_time_ms = self.predict(slope, intercept, self.current_size)
        logger.info(
            "update_current_size: after update - batch size %d, "
            "predicted batch time %f ms",
            self.current_size,
            self.predicted_time_ms,
        )
        self.last_updated_at = time.time()

    def get_timeout(self):
        """
        timeout for getting a batch, based on max latency and predicted batch time
        """
        return max(self.max_latency_ms - self.predicted_time_ms, 0.01)

    @staticmethod
    def regress_observations(
        previous_batch_sizes: List[int], previous_batch_times_ms: List[float]
    ) -> (float, float):
        """
        perform a linear regression of on observed worker performance
        """
        res = stats.theilslopes(previous_batch_times_ms, previous_batch_sizes)
        return res.slope, res.intercept

    @staticmethod
    def predict(slope: float, intercept: float, size: int) -> float:
        """
        based on the slope and intercept determined by a previous regression,
        predict the time needed to process a batch of size
        """
        return slope * size + intercept

    def should_update(self, jobs_per_second: float, batches_processed: int):
        """
        should we attempt to update the batch size based on the number of batches we
        have processed since the last update
        """
        if jobs_per_second > 0:
            elapsed = time.time() - self.last_updated_at
            logger.debug(
                "should_update: batches processed %d, time since last update %fs",
                batches_processed,
                elapsed,
            )
            return self.last_updated_at == 0 or (elapsed >= self.update_interval_s)
        return False
