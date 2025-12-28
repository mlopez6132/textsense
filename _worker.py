"""
Cloudflare Workers entry point for FastAPI application.
For Cloudflare Workers for Platforms (Python runtime).

This file serves as the entry point for Cloudflare Workers for Platforms.
The FastAPI app is imported and exported for Cloudflare's Python runtime.
"""

from relay_fastapi import app

# Export the FastAPI app for Cloudflare Workers for Platforms
# Cloudflare's Python runtime will automatically handle ASGI conversion
__all__ = ["app"]

