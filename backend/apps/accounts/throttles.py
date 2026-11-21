"""
Custom DRF Throttle classes for authentication, document uploads, and external AI calls.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, SimpleRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"
    rate = "10/minute"


class RefreshRateThrottle(AnonRateThrottle):
    scope = "refresh"
    rate = "20/minute"


class UploadRateThrottle(UserRateThrottle):
    scope = "uploads"
    rate = "30/minute"


class ExternalAPIRateThrottle(UserRateThrottle):
    scope = "external"
    rate = "40/minute"
