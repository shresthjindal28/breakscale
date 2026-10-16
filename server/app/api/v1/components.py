
from fastapi import APIRouter

from app.schemas.component import ArchitectureGraph
from app.simulation.validator import GraphValidator

router = APIRouter(
    prefix="/components",
    tags=["Components"],
)


@router.post("/validate")
async def validate_architecture(
    architecture: ArchitectureGraph,
):
    validator = GraphValidator(architecture)
    return validator.validate()
