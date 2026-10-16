import simpy

from app.simulation.clock import SimulationClock


class SimulationScheduler:
    def __init__(self):
        self.env = simpy.Environment()
        self.clock = SimulationClock(self.env)

    def start_process(self, generator):
        return self.env.process(generator)

    def run(self, until: float):
        self.env.run(until=until)