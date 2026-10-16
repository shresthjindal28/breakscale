from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["Users"])
@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
