import simpy

from app.simulation.state import ComponentConfig


class SimulatedComponent:
    def __init__(
        self,
        env: simpy.Environment,
        node_id: str,
        config: ComponentConfig,
    ):
        self.env = env
        self.node_id = node_id
        self.config = config

        self.resource = simpy.Resource(
            env,
            capacity=config.concurrency,
        )

        self.processed = 0
        self.rejected = 0
        self.total_wait_seconds = 0.0

    def process(self):
        # Queue limit counts waiting requests,
        # excluding currently active requests.
        if len(self.resource.queue) >= self.config.queue_limit:
            self.rejected += 1
            return False

        queued_at = self.env.now

        with self.resource.request() as resource_request:
            yield resource_request

            self.total_wait_seconds += (
                self.env.now - queued_at
            )

            processing_seconds = max(
                self.config.latency_ms / 1000.0,
                self.config.concurrency
                / self.config.capacity_rps,
            )

            yield self.env.timeout(processing_seconds)

            self.processed += 1

        return True