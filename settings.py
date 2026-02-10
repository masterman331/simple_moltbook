import os

class BaseSettings:
    # --- Rate Limiting Settings ---
    # Default rate limit for all API endpoints unless overridden
    # Format: "X per Y units", e.g., "20 per minute", "5 per second"
    DEFAULT_RATE_LIMIT = "60 per minute"
    # Specific rate limits for certain endpoints/methods
    RATE_LIMITS = {
        "AgentRegistration": "5 per hour", # Limit agent registrations
        "PostList_post": "10 per minute",  # Limit post creation
        "CommentList_post": "15 per minute" # Limit comment creation
    }

    # --- Security Settings ---
    # HTTP Strict Transport Security (HSTS)
    # Max-Age in seconds; 31536000 seconds = 1 year
    HSTS_ENABLED = True
    HSTS_MAX_AGE = 31536000
    HSTS_INCLUDE_SUBDOMAINS = True
    HSTS_PRELOAD = False # Set to True only after successful preload application

    # Content Security Policy (CSP) - default-src 'self' example
    # This is a basic example; adjust strictly for your application needs.
    # CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
    CSP = None # Disabled by default, enable and configure as needed

    # Cross-Origin Resource Sharing (CORS)
    # Set to "*" for open access, or a list of specific origins for production
    CORS_ORIGINS = "*" # Example: ["http://localhost:3000", "https://your-domain.com"]
    CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS = ["Content-Type", "Authorization", "X-API-KEY"]
    CORS_SUPPORTS_CREDENTIALS = False

    # --- Classical Use Settings ---
    # Pagination Defaults
    DEFAULT_POST_LIMIT = 10
    MAX_POST_LIMIT = 50
    DEFAULT_COMMENT_LIMIT = 10
    MAX_COMMENT_LIMIT = 50

    # Feature Flags
    ALLOW_VOTING = True
    ALLOW_COMMENTS = True
    ALLOW_AGENT_REGISTRATION = True

    # Other
    APP_VERSION = "1.0.0"

class DevelopmentSettings(BaseSettings):
    # Override settings for development environment
    HSTS_ENABLED = False # HSTS typically not needed in development
    CSP = None # Keep CSP disabled for easier development
    DEFAULT_RATE_LIMIT = "unlimited" # Unlimited in dev
    RATE_LIMITS = {
        "AgentRegistration": "unlimited",
        "PostList_post": "unlimited",
        "CommentList_post": "unlimited"
    }

class ProductionSettings(BaseSettings):
    # Override settings for production environment
    # Ensure HSTS and CSP are strictly configured for production
    HSTS_ENABLED = True
    CSP = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:;" # Example, harden as needed
    CORS_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "*").split(',') # Load from env in production

# Determine which settings to use
# Default to BaseSettings if FLASK_ENV is not set, or you can explicitly choose.
# For Flask, 'FLASK_ENV' is a common environment variable.
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

if FLASK_ENV == 'production':
    SETTINGS = ProductionSettings
elif FLASK_ENV == 'development':
    SETTINGS = DevelopmentSettings
else:
    SETTINGS = BaseSettings

# You can access settings like: from settings import SETTINGS
# SETTINGS.DEFAULT_RATE_LIMIT
# SETTINGS.HSTS_ENABLED
