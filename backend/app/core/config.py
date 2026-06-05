from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "HRMS API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/HRMS"
    
    # Database
    MONGODB_URL: str = "mongodb+srv://TfgHrmsUser:Hrms@163@tfghrms.jtzhyy4.mongodb.net/"
    DATABASE_NAME: str = "hrms_db"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Email Configuration
    GMAIL_USER: str = ""
    GMAIL_APP_PASSWORD: str = ""
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
