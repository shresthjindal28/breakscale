from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer

from app.core.config import get_settings


def get_queue() -> Queue:
    url = get_settings().REDIS_URL
    if not url:
        raise RuntimeError("REDIS_URL is required")
    return Queue("simulations", connection=Redis.from_url(url,socket_connect_timeout=5,socket_timeout=5),
                 default_timeout=600,serializer=JSONSerializer)

def enqueue_simulation(simulation_id: str):
    return get_queue().enqueue("app.simulation.worker_runner.run_simulation_job",simulation_id,
        job_id=simulation_id,job_timeout=600,ttl=900,result_ttl=3600,failure_ttl=86400)
