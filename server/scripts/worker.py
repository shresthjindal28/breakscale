"""Start an RQ spawn worker; no inherited async database connections."""
from rq.serializers import JSONSerializer

from app.infrastructure.spawn_worker import TLSSpawnWorker
from app.infrastructure.task_queue import get_queue

if __name__ == "__main__":
    queue = get_queue()
    TLSSpawnWorker([queue],connection=queue.connection,serializer=JSONSerializer).work()
