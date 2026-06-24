from fastapi import APIRouter, Depends, UploadFile, File, Query, status, HTTPException
from typing import Optional
from app.core.dependencies import get_current_user
from app.utils.cloudinary_upload import upload_file_to_cloudinary, FOLDER_MAP

router = APIRouter()

VALID_CATEGORIES = list(FOLDER_MAP.keys())


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Upload File to Cloudinary",
    description="""
**Purpose:** Upload a document or image to Cloudinary and get back a secure URL.
Use the returned `url` in onboarding section payloads (government_ids, education, experience, documents).

**Access:** Any authenticated user (all roles).

**Content-Type:** `multipart/form-data`

**Form Fields:**
| Field | Required | Description |
|---|---|---|
| file | ✅ | The file to upload |
| category | ❌ | Document category for organised storage. Default: `other` |
| employee_id | ❌ | Employee ID for file naming (e.g. EMP001) |

**Category values and their Cloudinary folder:**
| Category | Folder | Use for |
|---|---|---|
| `pan` | hrms/government_ids/pan | PAN card |
| `aadhaar` | hrms/government_ids/aadhaar | Aadhaar card |
| `passport` | hrms/government_ids/passport | Passport |
| `education` | hrms/education | Degree certificates, marksheets |
| `experience` | hrms/experience | Relieving letters, experience certificates |
| `document` | hrms/documents | Offer letter, other documents |
| `profile_photo` | hrms/profile_photos | Employee photo |
| `other` | hrms/other | Anything else |

**Allowed file types:** JPEG, PNG, WEBP, PDF, DOC, DOCX

**Max file size:** 10 MB

**Response 201:**
```json
{
  "url": "https://res.cloudinary.com/dxbjp7jno/image/upload/v1234567890/hrms/government_ids/pan/EMP001_pan.pdf",
  "public_id": "hrms/government_ids/pan/EMP001_pan",
  "file_name": "pan_card.pdf",
  "file_size": 204800,
  "format": "pdf"
}
```

**How to use the URL in onboarding:**

After uploading, use the `url` in your onboarding section submission:
```json
PUT /hrms/employees/me/onboarding/government_ids
{
  "data": {
    "pan": {
      "number": "ABCDE1234F",
      "document_url": "https://res.cloudinary.com/dxbjp7jno/..."
    }
  }
}
```

**Errors:**
- `400` — File type not allowed, file too large, or empty file
- `401` — Not authenticated
- `500` — Cloudinary upload failed
""",
)
async def upload_file(
    file: UploadFile = File(..., description="File to upload (PDF, JPEG, PNG, WEBP, DOC, DOCX — max 10MB)"),
    category: str = Query("other", description="Document category — pan | aadhaar | passport | education | experience | document | profile_photo | other"),
    employee_id: Optional[str] = Query(None, description="Employee ID for file naming (e.g. EMP001)"),
    current_user: dict = Depends(get_current_user)
):
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Valid: {VALID_CATEGORIES}"
        )

    result = await upload_file_to_cloudinary(
        file=file,
        category=category,
        employee_id=employee_id
    )
    return result


@router.post(
    "/multiple",
    status_code=status.HTTP_201_CREATED,
    summary="Upload Multiple Files",
    description="""
**Purpose:** Upload up to 5 files at once to Cloudinary. All files go to the same category.
Returns a list of upload results.

**Access:** Any authenticated user (all roles).

**Content-Type:** `multipart/form-data`

**Form Fields:**
| Field | Required | Description |
|---|---|---|
| files | ✅ | 1–5 files to upload |
| category | ❌ | Same category applied to all files. Default: `document` |
| employee_id | ❌ | Employee ID for file naming |

**Response 201:**
```json
{
  "uploaded": 3,
  "failed": 0,
  "results": [
    {
      "url": "https://res.cloudinary.com/dxbjp7jno/...",
      "file_name": "degree.pdf",
      "file_size": 512000,
      "format": "pdf"
    },
    ...
  ],
  "errors": []
}
```

**Errors:**
- `400` — More than 5 files, unsupported type, or file too large
- `401` — Not authenticated
""",
)
async def upload_multiple_files(
    files: list[UploadFile] = File(..., description="Up to 5 files"),
    category: str = Query("document", description="Category for all files"),
    employee_id: Optional[str] = Query(None, description="Employee ID for file naming"),
    current_user: dict = Depends(get_current_user)
):
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files allowed per request")

    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Valid: {VALID_CATEGORIES}"
        )

    results = []
    errors = []

    for f in files:
        try:
            result = await upload_file_to_cloudinary(
                file=f,
                category=category,
                employee_id=employee_id
            )
            results.append(result)
        except HTTPException as e:
            errors.append({"file_name": f.filename, "error": e.detail})
        except Exception as e:
            errors.append({"file_name": f.filename, "error": str(e)})

    return {
        "uploaded": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }
