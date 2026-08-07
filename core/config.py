import os
from typing import Literal
import urllib.parse
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class BaseConfig(BaseSettings):
    APP_NAME: str = "Enterprise-RAG-Engine"
    APP_VERSION: str = "3.0.0"
    APP_ENV: Literal["DEVELOPMENT", "STAGING", "PRODUCTION"] = "DEVELOPMENT"
    
    EMBEDDING_MODE: Literal["LOCAL", "CLOUD"] = "LOCAL"
    EMBEDDING_DIMENSION: int = 1536
    
    # Infrastructure Core Secrets (Strict defaults aligned with standard Postgres)
    DB_USER: str = Field(default="postgres")
    DB_PASSWORD: str = Field(...) # Ellipsis means required, fails fast if missing
    DB_HOST: str = Field(default="127.0.0.1")
    DB_PORT: int = Field(default=5432) 
    DB_NAME: str = Field(default="enterprise_rag_db")

    # External API KEYS
    GITHUB_TOKEN: str | None = Field(default=None)
    OPENAI_API_KEY: str | None = Field(default=None)
    HF_TOKEN: str | None = Field(default=None)

    # Internal API Key for securing our endpoints
    API_KEY: str = Field(default="dev-local-secret-key-123")

    SQLALCHEMY_DATABASE_URI: str | None = None

    @model_validator(mode="after")
    def assemble_db_connection(self) -> "BaseConfig":
        """
        Runs after fields are validated. If an explicit global URI string is 
        provided by the container environment, we use it directly. Otherwise, 
        we compile it cleanly using the individual parameters.
        """
        if not self.SQLALCHEMY_DATABASE_URI:
            # Safely encode the password to handle special characters like '@', '#', or '/'
            encoded_password = urllib.parse.quote_plus(self.DB_PASSWORD)
            
            self.SQLALCHEMY_DATABASE_URI = (
                f"postgresql://{self.DB_USER}:{encoded_password}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        return self

# --- Profile Configurations ---

class DevelopmentConfig(BaseConfig):
    model_config = SettingsConfigDict(env_file=".env.development", extra="ignore")

class StagingConfig(BaseConfig):
    EMBEDDING_MODE: Literal["CLOUD"] = "CLOUD"
    model_config = SettingsConfigDict(env_file=".env.staging", extra="ignore")

class ProductionConfig(BaseConfig):
    EMBEDDING_MODE: Literal["CLOUD"] = "CLOUD"
    model_config = SettingsConfigDict(
        env_file=".env.production", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

def get_settings() -> BaseConfig:
    ambient_env = os.getenv("APP_ENV", "DEVELOPMENT").upper()
    if ambient_env == "PRODUCTION":
        return ProductionConfig()
    elif ambient_env == "STAGING":
        return StagingConfig()
    return DevelopmentConfig()

settings = get_settings()