"""
Django config package initialization.
"""
try:
    from .celery import app as celery_app
except ImportError:
    try:
        from backend.config.celery import app as celery_app
    except ImportError:
        celery_app = None

__all__ = ("celery_app",)
