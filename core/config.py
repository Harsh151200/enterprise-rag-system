import os
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class BaseConfig(BaseSettings):
    APP_NAME: str = "Enterprise-RAG-Engine"
    APP_VERSION: str = "3.0.0"
    APP_ENV: Literal["DEVELOPMENT", "STAGING", "PRODUCTION"] = "DEVELOPMENT"
    
    EMBEDDING_MODE: Literal["LOCAL", "CLOUD"] = "LOCAL"
    EMBEDDING_DIMENSION: int = 1536
    
    # Infrastructure Core Secrets (Defaults fall back to local development parameters)
    DB_USER: str = Field(default="postgres", alias="DB_USER")
    DB_PASSWORD: str = Field(..., alias="DB_PASSWORD")
    DB_HOST: str = Field(default="127.0.0.1", alias="DB_HOST")
    DB_PORT: int = Field(default=5433, alias="DB_PORT")
    DB_NAME: str = Field(default="vector_db", alias="DB_NAME")
    
    GITHUB_TOKEN: str | None = Field(default=None, alias="GITHUB_TOKEN")
    OPENAI_API_KEY: str | None = Field(default=None, alias="OPENAI_API_KEY")
    HF_TOKEN: str | None = Field(default=None, alias="HF_TOKEN")

    # This property is dynamically assembled after field initialization
    SQLALCHEMY_DATABASE_URI: str | None = None

    @model_validator(mode="after")
    def assemble_db_connection(self) -> "BaseConfig":
        """
        Runs after fields are validated. If an explicit global URI string is 
        provided by the container environment, we use it directly. Otherwise, 
        we compile it cleanly using the individual parameters.
        """
        if not self.SQLALCHEMY_DATABASE_URI:
            self.SQLALCHEMY_DATABASE_URI = (
                f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        return self

# --- Profile Configurations ---

class DevelopmentConfig(BaseConfig):
    APP_ENV: Literal["DEVELOPMENT"] = "DEVELOPMENT"
    EMBEDDING_MODE: Literal["LOCAL"] = "LOCAL"
    model_config = SettingsConfigDict(env_file=".env.development", env_file_encoding="utf-8", extra="ignore")

class StagingConfig(BaseConfig):
    APP_ENV: Literal["STAGING"] = "STAGING"
    EMBEDDING_MODE: Literal["CLOUD"] = "CLOUD"
    # FIXED: Now looks explicitly for a staging configurations vault file
    model_config = SettingsConfigDict(env_file=".env.staging", env_file_encoding="utf-8", extra="ignore")

class ProductionConfig(BaseConfig):
    APP_ENV: Literal["PRODUCTION"] = "PRODUCTION"
    EMBEDDING_MODE: Literal["CLOUD"] = "CLOUD"
    # Production relies entirely on secure container infrastructure/Secret Manager variable injection
    model_config = SettingsConfigDict(extra="ignore")

def get_settings() -> BaseConfig:
    # Captures environment flags from the operating system host
    ambient_env = os.getenv("APP_ENV", "DEVELOPMENT").upper()
    if ambient_env == "PRODUCTION":
        return ProductionConfig()
    elif ambient_env == "STAGING":
        return StagingConfig()
    return DevelopmentConfig()

settings = get_settings()