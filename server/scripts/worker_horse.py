"""RQ child bootstrap: load TLS connection settings without command-line secrets."""
import os

from rq import Worker
from rq.executions import Execution
from rq.job import Job
from rq.serializers import JSONSerializer

from app.infrastructure.task_queue import get_queue

if __name__ == "__main__":
    queue = get_queue()
    worker = Worker.find_by_key(os.environ["RQ_WORKER_KEY"], connection=queue.connection,
                                serializer=JSONSerializer)
    if worker is None:
        raise SystemExit(1)
    job = Job.fetch(os.environ["RQ_JOB_ID"], connection=queue.connection, serializer=JSONSerializer)
    worker.execution = Execution.fetch(os.environ["RQ_EXECUTION_ID"], job.id, connection=queue.connection)
    os.setpgrp()
    worker._is_horse = True
    worker.main_work_horse(job, queue)
