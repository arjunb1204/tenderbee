"""
Strict Serializers for User authentication, Registration, Profile, and Token Management.
Enforces explicit fields, read-only guarantees, and Django password validation.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.accounts.models import Organization, UserRole

User = get_user_model()


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("id", "name", "gstin", "udyam_number", "pan", "created_at")
        read_only_fields = ("id", "created_at")


class UserProfileSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "username", "role", "organization", "date_joined")
        read_only_fields = ("id", "email", "username", "role", "organization", "date_joined")


class UserRegistrationSerializer(serializers.Serializer):
    """
    Registers a new tenant Organization and creates the primary Owner user.
    Enforces Django's Argon2-backed password validators.
    """
    organization_name = serializers.CharField(max_length=255, required=True)
    gstin = serializers.CharField(max_length=15, required=False, allow_blank=True)
    udyam_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    pan = serializers.CharField(max_length=10, required=False, allow_blank=True)

    email = serializers.EmailField(required=True)
    username = serializers.CharField(max_length=150, required=False)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return normalized

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        org_name = validated_data.pop("organization_name")
        gstin = validated_data.get("gstin", "")
        udyam = validated_data.get("udyam_number", "")
        pan = validated_data.get("pan", "")

        email = validated_data["email"].lower()
        username = validated_data.get("username") or email.split("@")[0]
        password = validated_data["password"]

        with transaction.atomic():
            org = Organization.objects.create(
                name=org_name,
                gstin=gstin,
                udyam_number=udyam,
                pan=pan,
            )
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                organization=org,
                role=UserRole.OWNER,
            )
        return user


class LoginSerializer(serializers.Serializer):
    """
    Authentication input serializer.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)


class TokenRefreshCookieSerializer(serializers.Serializer):
    """
    Refresh token input serializer supporting cookie and body.
    """
    refresh = serializers.CharField(required=False, allow_blank=True)
