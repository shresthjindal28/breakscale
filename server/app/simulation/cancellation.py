class SimulationCancelled(Exception):
    pass

class CancellationToken:
    def __init__(self):
        self._cancelled = False
    def cancel(self):
        self._cancelled = True
    def check(self):
        if self._cancelled:
            raise SimulationCancelled()
