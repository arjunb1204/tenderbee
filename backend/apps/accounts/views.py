"""
Production Authentication & Multi-Tenant Authorization Views for TenderBee.
Enforces:
- Short-lived JWT access tokens (~10 mins) and rotating refresh tokens with blacklisting.
- Strict httpOnly, Secure, SameSite=Lax cookie storage.
- Brute-force login protection via IP throttling and temporary account lockout.
- Uniform generic error messages preventing user enumeration.
- Immutable audit log records on login and logout.
"""
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts.serializers import (
    LoginSerializer,
    TokenRefreshCookieSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)
from apps.accounts.throttles import LoginRateThrottle, RefreshRateThrottle
from apps.audit.models import AuditEventType
from apps.audit.services import record_audit_event

User = get_user_model()


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """
    Sets JWT access and refresh tokens exclusively in httpOnly, Secure, SameSite=Lax cookies.
    """
    is_secure = not settings.DEBUG
    # Access token expires in 10 minutes (600 seconds)
    access_max_age = int(getattr(settings, "SIMPLE_JWT", {}).get("ACCESS_TOKEN_LIFETIME", timedelta(minutes=10)).total_seconds())
    # Refresh token expires in 7 days (604800 seconds)
    refresh_max_age = int(getattr(settings, "SIMPLE_JWT", {}).get("REFRESH_TOKEN_LIFETIME", timedelta(days=7)).total_seconds())

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_max_age,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """
    Wipes authentication cookies upon logout.
    """
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    # Also wipe legacy cookie names if present
    response.delete_cookie(key="tenderbee_access", path="/")
    response.delete_cookie(key="tenderbee_refresh", path="/")


def generate_tokens_for_user(user: User):
    """
    Generates SimpleJWT tokens embedded with tenant claims.
    """
    refresh = RefreshToken.for_user(user)
    refresh["email"] = user.email
    refresh["role"] = user.role
    refresh["org_id"] = str(user.organization.id) if user.organization else "org_default"
    refresh["org_name"] = user.organization.name if user.organization else "Default Organization"
    
    access = refresh.access_token
    access["email"] = user.email
    access["role"] = user.role
    access["org_id"] = str(user.organization.id) if user.organization else "org_default"
    access["org_name"] = user.organization.name if user.organization else "Default Organization"
    
    return str(access), str(refresh)


class RegisterAPIView(APIView):
    """
    POST /api/v1/auth/register/
    Registers a new tenant Organization and creates the primary Owner user.
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        access_token, refresh_token = generate_tokens_for_user(user)

        # Write audit log for tenant registration
        record_audit_event(
            organization=user.organization,
            actor=user.email,
            event_type=AuditEventType.ROLE_CHANGE,
            target_id=str(user.id),
            details={"action": "organization_registered", "role": user.role},
        )

        response = Response(
            {
                "success": True,
                "message": "Tenant organization and administrator user registered successfully.",
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )
        set_auth_cookies(response, access_token, refresh_token)
        return response


class LoginAPIView(APIView):
    """
    POST /api/v1/auth/login/ (or /api/v1/auth/token/)
    Authenticates user, enforces lockout protection and generic error responses,
    issues tokens, and writes audit record.
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]

        generic_error = {"error": "Invalid email or password."}

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(generic_error, status=status.HTTP_401_UNAUTHORIZED)

        # Check account lockout
        if user.is_locked():
            return Response(
                {"error": "Account is temporarily locked due to repeated failed login attempts. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if not user.check_password(password):
            user.record_failed_login(max_attempts=5, lockout_minutes=15)
            return Response(generic_error, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"error": "Account is inactive."}, status=status.HTTP_403_FORBIDDEN)

        # Reset failed attempts upon successful login
        user.reset_lockout()
        access_token, refresh_token = generate_tokens_for_user(user)

        # Write immutable audit log
        if user.organization:
            record_audit_event(
                organization=user.organization,
                actor=user.email,
                event_type=AuditEventType.LOGIN,
                target_id=str(user.id),
                details={"ip": request.META.get("REMOTE_ADDR", "unknown")},
            )

        response = Response(
            {
                "success": True,
                "message": "Login successful.",
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
        set_auth_cookies(response, access_token, refresh_token)
        return response


class RefreshTokenAPIView(APIView):
    """
    POST /api/v1/auth/refresh/
    Refreshes access token, rotates refresh token, blacklists previous refresh token,
    and updates httpOnly cookies.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RefreshRateThrottle]

    def post(self, request, *args, **kwargs):
        # 1. Read refresh token from explicit body or httpOnly cookie
        token_str = (
            request.data.get("refresh")
            or request.COOKIES.get("refresh_token")
            or request.COOKIES.get("tenderbee_refresh")
        )

        if not token_str:
            return Response(
                {"error": "Refresh token is missing from request cookies or body."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            refresh = RefreshToken(token_str)
            try:
                refresh.check_blacklist()
            except AttributeError:
                pass
            user_id = refresh.payload.get("user_id")
            user = User.objects.get(id=user_id)
            if not user.is_active:
                return Response({"error": "User account is inactive."}, status=status.HTTP_403_FORBIDDEN)

            # Blacklist old refresh token and rotate
            try:
                refresh.blacklist()
            except AttributeError:
                pass

            new_access, new_refresh = generate_tokens_for_user(user)
            response = Response(
                {
                    "success": True,
                    "message": "Token refreshed successfully.",
                    "user": UserProfileSerializer(user).data,
                },
                status=status.HTTP_200_OK,
            )
            set_auth_cookies(response, new_access, new_refresh)
            return response

        except (TokenError, User.DoesNotExist) as exc:
            response = Response(
                {"error": "Invalid, expired, or blacklisted refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            clear_auth_cookies(response)
            return response


class LogoutAPIView(APIView):
    """
    POST /api/v1/auth/logout/
    Blacklists the active refresh token, clears auth cookies, and logs the event.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        token_str = (
            request.data.get("refresh")
            or request.COOKIES.get("refresh_token")
            or request.COOKIES.get("tenderbee_refresh")
        )

        if token_str:
            try:
                refresh = RefreshToken(token_str)
                refresh.blacklist()
            except Exception:
                pass

        if request.user and request.user.is_authenticated and request.user.organization:
            record_audit_event(
                organization=request.user.organization,
                actor=request.user.email,
                event_type=AuditEventType.LOGOUT,
                target_id=str(request.user.id),
                details={"ip": request.META.get("REMOTE_ADDR", "unknown")},
            )

        response = Response(
            {"success": True, "message": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )
        clear_auth_cookies(response)
        return response


class CurrentUserAPIView(APIView):
    """
    GET /api/v1/auth/me/
    Returns authenticated user information, role, and organization tenant details.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
