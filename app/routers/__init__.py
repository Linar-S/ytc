"""HTTP routers for the application."""

from app.routers import auth, channels, health, pages, videos

__all__ = ["auth", "channels", "health", "pages", "videos"]
