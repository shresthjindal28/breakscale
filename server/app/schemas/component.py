
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ComponentType = Literal[
    "client",
    "loadBalancer",
    "service",
    "worker",
    "database",
    "cache",
    "queue",
    "cdn",
    "storage",
]


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    type: ComponentType
    data: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)


class ArchitectureGraph(BaseModel):
    nodes: list[GraphNode] = Field(max_length=500)
    edges: list[GraphEdge] = Field(max_length=2000)

    @model_validator(mode="after")
    def validate_unique_ids(self):
        node_ids = [node.id for node in self.nodes]
        edge_ids = [edge.id for edge in self.edges]

        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Duplicate node IDs detected")

        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("Duplicate edge IDs detected")

        return self
