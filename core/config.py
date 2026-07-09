import os
from typing import Literal
from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# =========================================================================
# GLOBAL BASE SETTINGS (Shared across all environment profiles)
# =========================================================================
class BaseConfig(BaseSettings):
    APP_NAME: str = "Enterprise-RAG-Engine"
    # Unified code-level SemVer tracker for release tracking
    APP_VERSION: str = "3.0.0-alpha.1"
    
    # Environment execution routing selector
    APP_ENV: Literal["DEVELOPMENT", "STAGING", "PRODUCTION"] = "DEVELOPMENT"
    
    # Embedding Configuration (Both models strictly emit 1536 dimensions)
    EMBEDDING_MODE: Literal["LOCAL", "CLOUD"] = "LOCAL"
    EMBEDDING_DIMENSION: int = 1536
    
    # Infrastructure Core Secrets
    DB_USER: str = Field(default="postgres", alias="DB_USER")
    DB_PASSWORD: str = Field(..., alias="DB_PASSWORD")
    DB_HOST: str = Field(default="127.0.0.1", alias="DB_HOST")
    DB_PORT: int = Field(default=5433, alias="DB_PORT")
    DB_NAME: str = Field(default="vector_db", alias="DB_NAME")
    
    # External API Secret Token Access
    GITHUB_TOKEN: str | None = Field(default=None, alias="GITHUB_TOKEN")
    OPENAI_API_KEY: str | None = Field(default=None, alias="OPENAI_API_KEY")

    # Automated Dynamic Construction of the full connection URI string
    SQLALCHEMY_DATABASE_URI: str | None = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None, info: ValidationInfo) -> str:
        if v:
            return v
        return f"postgresql://{info.data['DB_USER']}:{info.data['DB_PASSWORD']}@{info.data['DB_HOST']}:{info.data['DB_PORT']}/{info.data['DB_NAME']}"

# =========================================================================
# PROFILE-SPECIFIC CONFIGURATIONS
# =========================================================================
class DevelopmentConfig(BaseConfig):
    APP_ENV: Literal["DEVELOPMENT"] = "DEVELOPMENT"
    EMBEDDING_MODE: Literal["LOCAL"] = "LOCAL" # Local HF model runs for rapid dev testing
    
    # Direct Pydantic to read environment fields from the local dev sheet
    model_config = SettingsConfigDict(env_file=".env.development", env_file_encoding="utf-8", extra="ignore")

class StagingConfig(BaseConfig):
    APP_ENV: Literal["STAGING"] = "STAGING"
    EMBEDDING_MODE: Literal["CLOUD"] = "CLOUD" # Uses live APIs to mimic production limits
    
    model_config = SettingsConfigDict(env_file=".env.production", env_file_encoding="utf-8", extra="ignore")

class ProductionConfig(BaseConfig):
    APP_ENV: Literal["PRODUCTION"] = "PRODUCTION"
    EMBEDDING_MODE: Literal["CLOUD"] = "CLOUD" # Standardized Cloud deployment mapping
    
    # Production blocks plain-text .env reading; configurations are injected securely via runtime env variables
    model_config = SettingsConfigDict(extra="ignore")

# =========================================================================
# ENGINE CONTEXT CONFIGURATION FACTORY
# =========================================================================
def get_settings() -> BaseConfig:
    """
    Evaluates the ambient system environment to instantiate the 
    correct immutable settings profile safely.
    """
    ambient_env = os.getenv("APP_ENV", "DEVELOPMENT").upper()
    
    if ambient_env == "PRODUCTION":
        return ProductionConfig()
    elif ambient_env == "STAGING":
        return StagingConfig()
    return DevelopmentConfig()

# Global execution instance variable available for clean import across components
settings = get_settings()