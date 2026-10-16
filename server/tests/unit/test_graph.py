

from app.schemas.component import ArchitectureGraph
from app.simulation.validator import GraphValidator


def test_valid_architecture():
    architecture = ArchitectureGraph.model_validate({
        "nodes": [
            {"id": "c1", "type": "client"},
            {"id": "s1", "type": "service"},
        ],
        "edges": [
            {"id": "e1", "source": "c1", "target": "s1"},
        ],
    })

    result = GraphValidator(architecture).validate()

    assert result["valid"] is True
    assert result["stats"]["total_nodes"] == 2


def test_missing_client():
    architecture = ArchitectureGraph.model_validate({
        "nodes": [
            {"id": "s1", "type": "service"},
        ],
        "edges": [],
    })

    result = GraphValidator(architecture).validate()

    assert result["valid"] is False


def test_invalid_connection():
    architecture = ArchitectureGraph.model_validate({
        "nodes": [
            {"id": "c1", "type": "client"},
        ],
        "edges": [
            {"id": "e1", "source": "c1", "target": "missing"},
        ],
    })

    result = GraphValidator(architecture).validate()

    assert result["valid"] is False
