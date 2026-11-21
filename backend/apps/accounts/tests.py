"""
Unit and integration tests for Accounts and JWT Authentication.
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import Organization, User, UserRole


class AccountsJWTAuthTests(APITestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.register_url = reverse("accounts:auth-register")
        self.token_url = reverse("accounts:token-obtain-pair")
        self.me_url = reverse("accounts:auth-me")

    def test_organization_and_user_registration(self):
        """Verifies that tenant organization and admin user can be registered."""
        payload = {
            "organization_name": "Bharat Heavy Infra Ltd",
            "gstin": "27AABCU9603R1ZN",
            "udyam_number": "UDYAM-MH-01-0012345",
            "email": "bidlead@bharatinfra.in",
            "username": "bharat_admin",
            "password": "StrongPassword2026!",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["user"]["email"], "bidlead@bharatinfra.in")
        self.assertIsNotNone(response.data["user"]["organization"])
        self.assertEqual(response.data["user"]["organization"]["name"], "Bharat Heavy Infra Ltd")

        # Verify DB records
        user = User.objects.get(email="bidlead@bharatinfra.in")
        self.assertEqual(user.role, UserRole.OWNER)
        self.assertTrue(user.organization.id.startswith("org_"))

    def test_jwt_token_obtain_and_custom_claims(self):
        """Verifies obtaining JWT token in httpOnly cookies and validating custom claims."""
        # First register
        org = Organization.objects.create(name="Tata Tech Solutions")
        user = User.objects.create_user(
            email="manager@tatatech.com",
            username="tatamanager",
            password="SecurePassTata123",
            organization=org,
            role=UserRole.MEMBER,
        )

        # Login
        payload = {
            "email": "manager@tatatech.com",
            "password": "SecurePassTata123",
        }
        response = self.client.post(self.token_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.cookies)
        self.assertIn("refresh_token", response.cookies)
        self.assertEqual(response.data["user"]["role"], "member")
        self.assertEqual(response.data["user"]["organization"]["id"], org.id)

        # Access protected endpoint with cookie
        me_resp = self.client.get(self.me_url)
        self.assertEqual(me_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(me_resp.data["email"], "manager@tatatech.com")
        self.assertEqual(me_resp.data["organization"]["id"], org.id)

    def test_unauthenticated_request_rejected(self):
        """Verifies that accessing protected endpoint without token returns 401."""
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
