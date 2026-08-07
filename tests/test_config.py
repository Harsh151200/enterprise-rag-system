import os
import urllib.parse
from core.config import get_settings, DevelopmentConfig, ProductionConfig

def test_development_config_defaults():
    os.environ["APP_ENV"] = "DEVELOPMENT"
    settings = get_settings()
    
    assert isinstance(settings, DevelopmentConfig)
    assert settings.DB_PORT == 5432
    assert settings.DB_NAME == "enterprise_rag_db"

def test_password_url_encoding():
    # Simulate a password with special characters
    os.environ["DB_PASSWORD"] = "myP@ssw#rd!"
    os.environ["APP_ENV"] = "DEVELOPMENT"
    
    settings = get_settings()
    
    # Ensure the '@' and '#' are safely encoded in the SQLAlchemy URI
    encoded_password = urllib.parse.quote_plus("myP@ssw#rd!")
    assert encoded_password in settings.SQLALCHEMY_DATABASE_URI
    assert "@" not in encoded_password # The raw '@' shouldn't be in the password section