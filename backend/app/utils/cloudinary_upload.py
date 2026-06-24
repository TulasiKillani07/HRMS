"""
Cloudinary file upload utility.
Supports images and documents (PDF, DOCX, etc.)
"""
import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile
from app.core.config import settings
from app.utils.logger import logger

# Configure Cloudinary on import
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

# Allowed MIME types
ALLOWED_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Max file size: 10 MB
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Cloudinary folder per document category
FOLDER_MAP = {
    "pan":              "hrms/government_ids/pan",
    "aadhaar":          "hrms/government_ids/aadhaar",
    "passport":         "hrms/government_ids/passport",
    "education":        "hrms/education",
    "experience":       "hrms/experience",
    "document":         "hrms/documents",
    "profile_photo":    "hrms/profile_photos",
    "other":            "hrms/other",
}


async def upload_file_to_cloudinary(
    file: UploadFile,
    category: str = "other",
    employee_id: str = None
) -> dict:
    """
    Upload a file to Cloudinary and return the secure URL and metadata.

    Args:
        file:        FastAPI UploadFile object
        category:    One of: pan, aadhaar, passport, education, experience, document, profile_photo, other
        employee_id: Optional employee ID for organising files in Cloudinary

    Returns:
        {
            "url": "https://res.cloudinary.com/...",
            "public_id": "hrms/government_ids/pan/...",
            "file_name": "pan_card.pdf",
            "file_size": 204800,
            "format": "pdf"
        }
    """
    # Validate category
    folder = FOLDER_MAP.get(category, FOLDER_MAP["other"])

    # Validate content type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File type '{content_type}' is not allowed. "
                f"Allowed types: JPEG, PNG, WEBP, PDF, DOC, DOCX"
            )
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds the 10 MB limit. Your file: {len(content) / (1024*1024):.1f} MB"
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Build public_id for organised storage
    safe_filename = file.filename.replace(" ", "_").replace("/", "_") if file.filename else "file"
    public_id = f"{folder}/{employee_id + '_' if employee_id else ''}{safe_filename}"

    # Determine resource type
    resource_type = "image" if content_type.startswith("image/") else "raw"

    logger.info(f"Uploading '{file.filename}' ({len(content)} bytes) to Cloudinary folder '{folder}'")

    try:
        result = cloudinary.uploader.upload(
            content,
            public_id=public_id,
            resource_type=resource_type,
            overwrite=True,
            use_filename=True,
            unique_filename=True,
        )

        logger.info(f"Upload successful: {result['secure_url']}")

        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "file_name": file.filename,
            "file_size": result.get("bytes", len(content)),
            "format": result.get("format", ""),
        }

    except Exception as e:
        logger.error(f"Cloudinary upload failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"File upload failed: {str(e)}"
        )
