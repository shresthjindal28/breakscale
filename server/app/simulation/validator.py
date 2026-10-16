
import networkx as nx

from app.schemas.component import ArchitectureGraph
from app.simulation.graph import GraphBuilder


class GraphValidator:
    def __init__(self, architecture: ArchitectureGraph):
        self.architecture = architecture

    def validate(self) -> dict:
        errors: list[str] = []
        warnings: list[str] = []

        try:
            graph = GraphBuilder(self.architecture).build()
        except ValueError as exc:
            return {
                "valid": False,
                "errors": [str(exc)],
                "warnings": [],
                "stats": {},
            }

        clients = [
            node_id
            for node_id, attrs in graph.nodes(data=True)
            if attrs["component_type"] == "client"
        ]

        if not clients:
            errors.append("At least one client node is required")

        if graph.number_of_nodes() == 0:
            errors.append("Architecture cannot be empty")

        for node_id in graph.nodes:
            if graph.has_edge(node_id, node_id):
                errors.append(
                    f"Self-connection detected on node {node_id}"
                )

        if not nx.is_directed_acyclic_graph(graph):
            warnings.append(
                "Architecture contains cycles; loop handling "
                "must be configured before simulation"
            )

        reachable = set(clients)

        for client_id in clients:
            reachable.update(nx.descendants(graph, client_id))

        disconnected = set(graph.nodes) - reachable

        if disconnected:
            warnings.append(
                f"{len(disconnected)} nodes are unreachable "
                "from any client"
            )

        for client_id in clients:
            if graph.out_degree(client_id) == 0:
                warnings.append(
                    f"Client {client_id} has no outgoing connection"
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "stats": {
                "total_nodes": graph.number_of_nodes(),
                "total_edges": graph.number_of_edges(),
                "total_clients": len(clients),
                "unreachable_nodes": len(disconnected),
                "has_cycles": not nx.is_directed_acyclic_graph(graph),
            },
        }
