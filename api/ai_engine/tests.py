from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .auditor import analyze


class AuditEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="auditor",
            email="auditor@example.com",
            password="AuditPass123!",
        )
        login_response = self.client.post(
            "/api/auth/token/",
            {"username": self.user.username, "password": "AuditPass123!"},
            format="json",
        )
        self.access_token = login_response.json().get("access")

    def _auth_headers(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_audit_requires_authentication(self):
        response = self.client.post(
            "/api/audit/",
            {"secret": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_audit_detects_jwt_token(self):
        response = self.client.post(
            "/api/audit/",
            {"secret": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def"},
            format="json",
            **self._auth_headers(self.access_token),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["identified_type"], "JSON Web Token (JWT)")
        self.assertEqual(payload["risk_level"], "critical")
        self.assertEqual(payload["risk_score"], 92)

    def test_audit_rejects_blank_secret(self):
        response = self.client.post(
            "/api/audit/",
            {"secret": " "},
            format="json",
            **self._auth_headers(self.access_token),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["identified_type"], "Empty Input")
        self.assertEqual(payload["risk_level"], "info")
        self.assertEqual(payload["risk_score"], 0)


class AuditorFunctionTests(TestCase):
    def test_analyze_empty_string_returns_info_profile(self):
        result = analyze("")
        self.assertEqual(result["identified_type"], "Empty Input")
        self.assertEqual(result["risk_level"], "info")
        self.assertEqual(result["risk_score"], 0)

    def test_analyze_github_token_returns_critical_risk(self):
        result = analyze("ghp_testgithubtoken1234567890")
        self.assertEqual(result["identified_type"], "GitHub Personal Access Token")
        self.assertEqual(result["risk_level"], "critical")
        self.assertEqual(result["risk_score"], 96)
