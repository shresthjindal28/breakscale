from dataclasses import dataclass

import simpy


@dataclass(frozen=True)
class FailureEvent:
    node_id: str
    start_at: float
    duration: float


class FailureInjector:
    def __init__(self, env: simpy.Environment):
        self.env = env
        self.failed_nodes: set[str] = set()
        self.events: list[FailureEvent] = []
        self.outage_counts: dict[str, int] = {}
        self._started = False

    def schedule(self, event: FailureEvent):
        if event.start_at < 0 or event.duration <= 0:
            raise ValueError("Invalid failure schedule")
        if self._started:
            raise ValueError("Schedule failures before starting the injector")
        if any(
            other.node_id == event.node_id
            and event.start_at < other.start_at + other.duration
            and other.start_at < event.start_at + event.duration
            for other in self.events
        ):
            raise ValueError("Overlapping outages on the same node are not supported")
        self.events.append(event)

    def is_available(self, node_id: str) -> bool:
        return node_id not in self.failed_nodes

    def _run_event(self, event: FailureEvent):
        if event.start_at > self.env.now:
            yield self.env.timeout(event.start_at - self.env.now)
        self.failed_nodes.add(event.node_id)
        self.outage_counts[event.node_id] = self.outage_counts.get(event.node_id, 0) + 1
        yield self.env.timeout(event.duration)
        self.failed_nodes.remove(event.node_id)

    def start(self):
        if self._started:
            return
        self._started = True
        for event in self.events:
            self.env.process(self._run_event(event))
