import os
import secrets
from pathlib import Path

from dotenv import load_dotenv


def generate_secret_key():
    """Generate a secure random secret key"""
    return secrets.token_hex(32)

def init_environment():
    """Initialize environment configuration"""
    env_file = Path(__file__).parent.parent / '.env'
    env_example = Path(__file__).parent.parent / '.env-example'
    
    # If .env doesn't exist, create it from .env.example
    if not env_file.exists() and env_example.exists():
        with open(env_example, 'r') as example:
            with open(env_file, 'w') as env:
                for line in example:
                    if line.startswith('SECRET_KEY='):
                        # Generate new secret key
                        env.write(f'SECRET_KEY={generate_secret_key()}\n')
                    else:
                        env.write(line)
        print("Created new .env file with fresh SECRET_KEY")
    
    # Load the environment variables
    load_dotenv()
    
    # Verify SECRET_KEY exists
    if not os.getenv('SECRET_KEY'):
        raise RuntimeError(
            "SECRET_KEY not found in environment variables. "
            "Please ensure .env file exists with SECRET_KEY set."
        )

if __name__ == '__main__':
    init_environment()
