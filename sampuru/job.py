"""
job definition
"""

from asyncio import Future
from typing import Any, List, Optional
from dataclasses import dataclass


@dataclass
class Job:
    """
    a single unit of work to be sent to a remote runner
    """

    runnable_name: str
    submitter_name: str
    data: List[Any]
    future: Future
    job_id: Optional[str] = None
    metadata: Optional[dict] = None
