"""Engine-only concurrent benchmark; does not claim API/RQ production capacity."""
import json
import multiprocessing
import resource
import sys
import time
from concurrent.futures import ProcessPoolExecutor

from app.schemas.component import ArchitectureGraph
from app.simulation.engine import SimulationEngine
from app.simulation.state import SimulationConfig


def measure(kind: str):
    route = ["client", "api", "database"]
    nodes = [
        {"id": "client", "type": "client", "data": {"rps": 1000}},
        {"id": "api", "type": "service", "data": {"capacity_rps": 500, "queue_limit": 5}},
        {"id": "database", "type": "database", "data": {"pool_size": 5}},
    ]
    if kind == "queue-worker":
        route = ["client", "api", "queue", "worker", "database"]
        nodes += [{"id":"queue","type":"queue"}, {"id":"worker","type":"worker"}]
    if kind == "outage-retries":
        nodes[1]["data"].update({"failure_start_at":2,"failure_duration":3,"max_retries":2})
    graph = ArchitectureGraph.model_validate({"nodes":nodes,"edges":[
        {"id":str(i),"source":a,"target":b} for i,(a,b) in enumerate(zip(route,route[1:]))
    ]})
    start = time.perf_counter()
    engine = SimulationEngine(graph, SimulationConfig(duration_seconds=10,max_requests=5000))
    result = engine.run()
    elapsed = time.perf_counter() - start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {"scenario":kind,"wall_seconds":round(elapsed,4),"generated":result.generated,
            "completed":result.completed,"failed":result.failed,
            "peak_process_mb":round(rss/(1024**2 if sys.platform=="darwin" else 1024),2),
            "trace_events":len(engine.trace.events),"trace_dropped":engine.trace.dropped_events}


if __name__ == "__main__":
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context("spawn")) as pool:
        results = list(pool.map(measure,["linear","queue-worker","outage-retries"]))
    print(json.dumps({"processes":2,"total_wall_seconds":round(time.perf_counter()-start,4),"results":results},indent=2))
