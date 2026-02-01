from typing import Annotated, Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/access-token") # URL is just a placeholder here

async def get_current_user_id(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    # A simple implementation that just extracts user ID from token
    # In a real app, this would also fetch the user from DB to verify existence/active status
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception

# Dep for full user object if needed, but for now ID is enough for the requested task.
# The user asked for "Depends(get_current_user)" - I'll mock that to return a dict or ID wrapper
# assuming typical auth flow. For now, let's return a simple object or dict with 'id'.

class UserStruct:
    def __init__(self, id):
        self.id = id

async def get_current_user(
    user_id: Annotated[str, Depends(get_current_user_id)]
) -> UserStruct:
    return UserStruct(id=user_id)
