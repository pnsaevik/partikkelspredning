"""Azure Storage Queue implementation of `JobQueue`.

Claiming uses the queue's built-in visibility timeout as a peek-lock: a
received message is hidden from other receivers for `visibility_timeout`
seconds and is only deleted once the caller has durably recorded the claim
(see `partikkelspredning.services.job_service.JobService.claim_job`). That
is what gives `try_claim` the at-most-once guarantee
`partikkelspredning.ports.queue.JobQueue` requires - no extra locking
needed here, unlike the local CSV adapter's file lock.

If the process crashes after receiving a message but before deleting it,
the message becomes visible again after the timeout and can be claimed by
another worker - a basic form of the retry behavior the root README
describes as a future improvement, provided here for free by the platform.
"""
from __future__ import annotations

from typing import Optional

from azure.core.exceptions import ResourceExistsError
from azure.storage.queue import QueueClient


class StorageQueueJobQueue:
    def __init__(
        self,
        connection_string: str,
        queue_name: str = "jobs",
        visibility_timeout: int = 300,
    ) -> None:
        self._client = QueueClient.from_connection_string(connection_string, queue_name)
        try:
            self._client.create_queue()
        except ResourceExistsError:
            pass
        self._visibility_timeout = visibility_timeout

    def enqueue(self, job_id: str) -> None:
        self._client.send_message(job_id)

    def try_claim(self) -> Optional[str]:
        messages = self._client.receive_messages(
            messages_per_page=1, visibility_timeout=self._visibility_timeout
        )
        for message in messages:
            self._client.delete_message(message)
            return message.content
        return None
