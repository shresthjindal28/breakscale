import random
from collections.abc import Callable

import simpy

from app.simulation.algorithms.retries import exponential_backoff
from app.simulation.components.queue import MessageQueue
from app.simulation.state import QueueMessage


class BackgroundWorker:
    def __init__(
        self, env: simpy.Environment, name: str, queue: MessageQueue,
        processing_ms: float = 100, failure_rate: float = 0.0,
        max_attempts: int = 3, seed: int = 42,
        downstream: Callable | None = None,
    ):
        if processing_ms < 0:
            raise ValueError("processing_ms cannot be negative")
        if not 0 <= failure_rate <= 1:
            raise ValueError("failure_rate must be between 0 and 1")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.env = env
        self.name = name
        self.queue = queue
        self.processing_seconds = processing_ms / 1000
        self.failure_rate = failure_rate
        self.max_attempts = max_attempts
        self.random = random.Random(seed)
        self.processed = 0
        self.failed_attempts = 0
        self.downstream = downstream

    def _retry(self, message: QueueMessage):
        # A separate process lets this worker consume other jobs during backoff.
        yield self.env.timeout(exponential_backoff(message.attempts))
        if not self.queue.publish(message):
            message.error = f"Retry queue full: {self.queue.name}"
            self.queue.dead_letter(message)

    def run(self):
        while True:
            message = yield self.env.process(self.queue.consume())
            message.attempts += 1
            message.error = None
            yield self.env.timeout(self.processing_seconds)
            success = self.random.random() >= self.failure_rate
            if not success:
                message.error = f"Worker processing failed: {self.name}"
            elif self.downstream is not None:
                success = yield self.env.process(self.downstream(self.name, message))
            if not success:
                if message.error is None:
                    message.error = f"Background processing failed: {self.name}"
                self.failed_attempts += 1
                if message.attempts >= self.max_attempts:
                    self.queue.dead_letter(message)
                else:
                    self.queue.release_for_retry(message)
                    self.env.process(self._retry(message))
            else:
                self.processed += 1
                self.queue.acknowledge(message)
