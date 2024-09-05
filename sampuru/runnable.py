import abc

from typing import Any, List


class Runnable(abc.ABC):
    # whether a runner should flatten the incoming data into separate jobs when batching
    #
    # considerations:
    # - if data from the same request is split into multiple jobs it may be split over
    #   multiple workers or multiple forward passes. this can increase the median
    #   latency
    # - if the length of data from different requests is highly irregular, the quality
    #   of the performance prediction can degrade
    flatten = False

    @abc.abstractmethod
    def forward(self, data: List[Any]) -> List[Any]:
        """
        perform a forward pass over the data, producing one output for each input
        """
        raise NotImplementedError
