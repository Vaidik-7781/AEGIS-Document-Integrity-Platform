from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os

class Settings(BaseSettings):
    # App
    APP_NAME: str = "AEGIS"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    SECRET_KEY: str = "aegis-secret-key-change-in-production"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "*"]

    # Database
    DB_PATH: str = os.path.join(os.path.dirname(__file__), "aegis.db")

    # AI
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Blockchain
    ETH_RPC_URL: str = "https://ethereum-sepolia-rpc.publicnode.com"
    ETH_NETWORK: str = "sepolia"

    # Analysis
    MAX_FILES_PER_SUBMISSION: int = 10
    MAX_FILE_SIZE_MB: int = 50
    ELA_QUALITY: int = 75
    ELA_AMPLIFY: int = 15
    ELA_THRESHOLD: float = 25.0
    FONT_ZSCORE_THRESHOLD: float = 2.8
    INCOME_MISMATCH_THRESHOLD: float = 0.25

    # Risk score thresholds
    APPROVE_THRESHOLD: int = 20
    REVIEW_THRESHOLD: int = 55

    # Layer weights (must sum to 100)
    WEIGHT_ELA: int = 20
    WEIGHT_BLOCKCHAIN: int = 25
    WEIGHT_CONTRADICTION: int = 30
    WEIGHT_FONT: int = 15
    WEIGHT_VERSION: int = 10

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
