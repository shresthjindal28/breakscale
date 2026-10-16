import os
import sys

from rq import SpawnWorker


class TLSSpawnWorker(SpawnWorker):
    """Rebuild Redis from settings in a child, preserving TLS and hiding credentials.

    RQ's default spawn path reconstructs Redis from pool kwargs without retaining
    the SSL connection class. It also puts those kwargs in the command line.
    """

    def fork_work_horse(self, job, queue):
        assert self.execution is not None
        child_env = dict(os.environ)
        child_env.update({
            "RQ_WORKER_KEY": self.key,
            "RQ_EXECUTION_ID": self.execution.id,
            "RQ_JOB_ID": job.id,
            "RQ_QUEUE_NAME": queue.name,
        })
        self._horse_pid = os.spawnve(
            os.P_NOWAIT, sys.executable,
            [sys.executable, "-m", "scripts.worker_horse"], child_env,
        )
