from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "client"

class UserCreate(UserBase):
    password: str
    assigned_plants: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    assigned_plants: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    assigned_plants: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
