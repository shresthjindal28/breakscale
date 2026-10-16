
import networkx as nx

from app.schemas.component import ArchitectureGraph


class GraphBuilder:
    def __init__(self, architecture: ArchitectureGraph):
        self.architecture = architecture

    def build(self) -> nx.DiGraph:
        graph = nx.DiGraph()

        for node in self.architecture.nodes:
            graph.add_node(
                node.id,
                component_type=node.type,
                config=node.data,
            )

        for edge in self.architecture.edges:
            if edge.source not in graph:
                raise ValueError(
                    f"Unknown source node: {edge.source}"
                )

            if edge.target not in graph:
                raise ValueError(
                    f"Unknown target node: {edge.target}"
                )

            if graph.has_edge(edge.source, edge.target):
                raise ValueError(
                    f"Duplicate connection: {edge.source} -> {edge.target}"
                )

            graph.add_edge(edge.source, edge.target)

        return graph
