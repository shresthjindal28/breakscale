import simpy


class SimulationClock:
    def __init__(self, env: simpy.Environment):
        self.env = env

    @property
    def now(self) -> float:
        return float(self.env.now)

    def wait(self, seconds: float):
        return self.env.timeout(seconds)