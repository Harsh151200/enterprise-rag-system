import os
import urllib.parse
import pytest
from pydantic import ValidationError
from core.config import get_settings, DevelopmentConfig, StagingConfig, ProductionConfig, BaseConfig

def test_development_config_defaults():
    os.environ["APP_ENV"] = "DEVELOPMENT"
    os.environ["DB_PASSWORD"] = "dummy"
    settings = get_settings()
    
    assert isinstance(settings, DevelopmentConfig)
    assert settings.EMBEDDING_MODE == "LOCAL"

def test_staging_and_production_config_overrides():
    # Staging
    os.environ["APP_ENV"] = "STAGING"
    os.environ["DB_PASSWORD"] = "dummy"
    staging_settings = get_settings()
    assert isinstance(staging_settings, StagingConfig)
    assert staging_settings.EMBEDDING_MODE == "CLOUD"

    # Production
    os.environ["APP_ENV"] = "PRODUCTION"
    prod_settings = get_settings()
    assert isinstance(prod_settings, ProductionConfig)
    assert prod_settings.EMBEDDING_MODE == "CLOUD"

def test_missing_required_secrets_fails_fast():
    # Pydantic should raise a ValidationError if DB_PASSWORD is missing
    if "DB_PASSWORD" in os.environ:
        del os.environ["DB_PASSWORD"]
        
    with pytest.raises(ValidationError) as excinfo:
        BaseConfig()
    
    assert "DB_PASSWORD" in str(excinfo.value)
    assert "Field required" in str(excinfo.value)

def test_password_url_encoding():
    os.environ["DB_PASSWORD"] = "myP@ssw#rd!"
    os.environ["APP_ENV"] = "DEVELOPMENT"
    
    settings = get_settings()
    encoded_password = urllib.parse.quote_plus("myP@ssw#rd!")
    assert encoded_password in settings.SQLALCHEMY_DATABASE_URI
    assert "@" not in encoded_password  # The raw '@' shouldn't be in the password section