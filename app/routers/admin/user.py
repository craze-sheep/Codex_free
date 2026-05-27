"""Admin: User CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.admin_auth import verify_admin_key
from app.models.schemas import UserCreate, UserUpdate, UserResponse
from app.store.user import create_user, get_user_by_id, list_users, update_user, delete_user

router = APIRouter(prefix="/admin/users")


@router.post("")
async def create(data: UserCreate, _admin: bool = Depends(verify_admin_key)):
    user = await create_user(email=data.email, password=data.password, role=data.role, balance=data.balance)
    return user


@router.get("")
async def list_all(limit: int = 100, offset: int = 0, _admin: bool = Depends(verify_admin_key)):
    users = await list_users(limit=limit, offset=offset)
    return {"data": users}


@router.get("/{user_id}")
async def get_one(user_id: int, _admin: bool = Depends(verify_admin_key)):
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}")
async def update(user_id: int, data: UserUpdate, _admin: bool = Depends(verify_admin_key)):
    fields = data.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = await update_user(user_id, **fields)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@router.delete("/{user_id}")
async def delete(user_id: int, _admin: bool = Depends(verify_admin_key)):
    ok = await delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}
