from typing import Any, Optional
from fastapi.responses import JSONResponse

def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200
) -> JSONResponse:
    """Standard success response"""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data
        }
    )

def error_response(
    message: str = "Error",
    errors: Optional[dict] = None,
    status_code: int = 400
) -> JSONResponse:
    """Standard error response"""
    content = {
        "success": False,
        "message": message
    }
    if errors:
        content["errors"] = errors
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )

def pagination_response(
    data: list,
    page: int,
    limit: int,
    total: int,
    message: str = "Success"
) -> JSONResponse:
    """Paginated response"""
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": message,
            "data": data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }
    )
