import os

# Define the base directory of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Database configuration
DATABASE_NAME = 'site.db'
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, DATABASE_NAME)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# API Key generation (for agents)
API_KEY_LENGTH = 32 # Length of the generated API key (e.g., 32 characters for a UUID-like string)
