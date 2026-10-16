import math

from app.schemas.component import ArchitectureGraph
from app.simulation.validator import GraphValidator


# Bound CPU/memory before accepting either REST or streaming work.
def validate_workload(graph_data: dict) -> ArchitectureGraph:
    graph = ArchitectureGraph.model_validate(graph_data)
    validation = GraphValidator(graph).validate()
    if not validation["valid"] or validation["warnings"] and any("cycles" in warning for warning in validation["warnings"]):
        raise ValueError("Invalid architecture: " + str(validation["errors"] or validation["warnings"]))
    for node in graph.nodes:
        for key,value in node.data.items():
            if isinstance(value,(float,int)) and not isinstance(value,bool) and (not math.isfinite(value) or abs(value)>1_000_000):
                raise ValueError(f"Invalid or excessive numeric value for {key}")
        if node.type == "client" and not 0 <= float(node.data.get("rps",100)) <= 1000:
            raise ValueError("Client RPS must be between 0 and 1000")
        for key in ("capacity_rps","capacity","concurrency","pool_size","cache_capacity","queue_capacity"):
            if key in node.data and float(node.data[key]) <= 0:
                raise ValueError(f"{key} must be positive")
        if int(node.data.get("max_attempts",3)) not in range(1,11):
            raise ValueError("Worker max_attempts must be between 1 and 10")
    return graph
