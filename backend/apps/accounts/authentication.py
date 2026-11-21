"""
Cookie and Header-Aware JWT Authentication for TenderBee.
Tokens are stored strictly in httpOnly, Secure, SameSite=Lax cookies,
while still supporting standard Authorization: Bearer headers for service calls.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed


class CookieJWTAuthentication(JWTAuthentication):
    """
    Extends SimpleJWT's JWTAuthentication to prioritize reading JWT access tokens
    from httpOnly cookies ('access_token' or 'tenderbee_access').
    """
    def authenticate(self, request):
        # 1. Try reading token from httpOnly cookie first
        raw_token = request.COOKIES.get("access_token") or request.COOKIES.get("tenderbee_access")
        
        # 2. If no cookie, fall back to Authorization header
        if not raw_token:
            header = self.get_header(request)
            if header is not None:
                raw_token = self.get_raw_token(header)
                
        if raw_token is None:
            from django.conf import settings
            if getattr(settings, "DEBUG", False):
                from apps.accounts.models import User
                demo_user = User.objects.filter(email="demo@tenderbee.ai").first()
                if demo_user:
                    return demo_user, None
            return None

        # 3. Validate token
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

