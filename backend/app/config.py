"""Application configuration loaded from environment variables."""
import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    db_name: str = "ledgerline"
    
    # JWT
    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    
    # CORS
    cors_origins: str = "http://localhost:5173"
    
    # Rate limiting
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    
    # Transaction limits
    max_transaction_amount: int = 100_000_000_00  # 100 crore paise = 1 crore INR
    
    # Idempotency key TTL (hours)
    idempotency_ttl_hours: int = 48
    
    # Anthropic (optional, for anomaly AI summaries)
    anthropic_api_key: str = ""
    
    # External account ID (system account for deposits/withdrawals)
    external_account_id: str = "EXTERNAL"
    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
