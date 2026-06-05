from pydantic import BaseModel
from typing import Optional

class DepartmentCreateRequest(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    manager_id: Optional[str] = None

class DepartmentUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[str] = None
    status: Optional[str] = None

class DepartmentResponse(BaseModel):
    id: str
    name: str
    code: str
    description: Optional[str] = None
    manager_id: Optional[str] = None
    status: str
    
    class Config:
        from_attributes = True
