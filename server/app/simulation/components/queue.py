import simpy

from app.simulation.state import MessageStatus, QueueMessage


class MessageQueue:
    def __init__(self, env: simpy.Environment, name: str, capacity: int = 1000):
        if capacity < 1:
            raise ValueError("Queue capacity must be positive")
        self.env = env
        self.name = name
        self.capacity = capacity
        self.store = simpy.Store(env)
        self.published = 0
        self.consumed = 0
        self.rejected = 0
        self.acknowledged = 0
        self.dead_lettered = 0
        self.in_flight = 0
        self.dead_letters: list[QueueMessage] = []

    @property
    def depth(self) -> int:
        return len(self.store.items)

    def publish(self, message: QueueMessage) -> bool:
        if self.depth >= self.capacity:
            self.rejected += 1
            return False
        message.status = MessageStatus.QUEUED
        self.store.put(message)
        self.published += 1
        return True

    def consume(self):
        message = yield self.store.get()
        message.status = MessageStatus.PROCESSING
        self.consumed += 1
        self.in_flight += 1
        return message

    def acknowledge(self, message: QueueMessage) -> None:
        self.in_flight -= 1
        message.status = MessageStatus.ACKNOWLEDGED
        message.completed_at = float(self.env.now)
        message.error = None
        self.acknowledged += 1

    def dead_letter(self, message: QueueMessage) -> None:
        if message.status == MessageStatus.PROCESSING:
            self.in_flight -= 1
        message.status = MessageStatus.DEAD_LETTERED
        message.completed_at = float(self.env.now)
        self.dead_letters.append(message)
        self.dead_lettered += 1

    def release_for_retry(self, message: QueueMessage) -> None:
        self.in_flight -= 1
        message.status = MessageStatus.QUEUED
