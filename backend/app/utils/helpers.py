from datetime import datetime
from typing import Optional
from bson import ObjectId

def convert_objectid_to_str(data: dict) -> dict:
    """Convert MongoDB ObjectId to string"""
    if data and "_id" in data:
        data["_id"] = str(data["_id"])
    return data

def convert_datetime_to_str(dt: datetime) -> str:
    """Convert datetime to ISO format string"""
    return dt.isoformat() if dt else None

def is_valid_objectid(id_str: str) -> bool:
    """Check if string is a valid ObjectId"""
    try:
        ObjectId(id_str)
        return True
    except:
        return False

def get_current_timestamp() -> datetime:
    """Get current UTC timestamp"""
    return datetime.utcnow()

def paginate_query(page: int = 1, limit: int = 10):
    """Calculate skip and limit for pagination"""
    skip = (page - 1) * limit
    return skip, limit
