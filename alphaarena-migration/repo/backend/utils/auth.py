"""
API Key Authentication Middleware for FastAPI
Protects sensitive endpoints from unauthorized access.
"""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
import os
from dotenv import load_dotenv
import secrets

load_dotenv()

# API Key configuration
API_KEY_NAME = "X-API-Key"
API_KEY = os.getenv("API_KEY")

# Security scheme
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Dependency to validate API key from request headers.
    
    Args:
        api_key: API key from X-API-Key header
        
    Returns:
        str: The validated API key
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not API_KEY:
        # If no API key is configured, allow access (development mode)
        # You can change this to raise an error in production
        return None
    
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )
    
    return api_key


def generate_api_key() -> str:
    """
    Generate a secure random API key.
    
    Returns:
        str: A cryptographically secure random API key
    """
    return secrets.token_urlsafe(32)


if __name__ == "__main__":
    # Run this script to generate a new API key
    print("Generated API Key:")
    print(generate_api_key())
    print("\nAdd this to your .env file as:")
    print("API_KEY=<generated_key>")
