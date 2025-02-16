from pathlib import Path
import os
from dotenv import load_dotenv

# Get the src directory path
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables
env_file = BASE_DIR / '.env.development'
print(f"Looking for .env file at: {env_file}")
load_dotenv(env_file)

# Check the environment variable
allow_reg = os.getenv('ALLOW_REGISTRATION')
print(f"ALLOW_REGISTRATION raw value = {allow_reg}")
print(f"ALLOW_REGISTRATION bool value = {str(allow_reg).lower() == 'true'}") 