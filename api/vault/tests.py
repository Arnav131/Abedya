import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from vault.honeypot_models import HoneypotEntry


@override_settings(HONEYPOT={"ENABLED": False})
class HoneypotTriggerViewTests(TestCase):
	def setUp(self):
		self.client = APIClient()
		self.user = get_user_model().objects.create_user(
			username="alice",
			email="alice@example.com",
			password="StrongPass123!",
		)
		self.client.force_authenticate(user=self.user)

	def _create_entry(self, **kwargs):
		defaults = {
			"user": self.user,
			"category": "api_key",
			"provider": "stripe",
			"fake_secret": "sk_test_decoy_value",
			"honeypot_id": uuid.uuid4(),
			"generator": "fallback",
		}
		defaults.update(kwargs)
		return HoneypotEntry.objects.create(**defaults)

	@patch("ai_engine.honeypot_alert_api.send_breach_alert")
	def test_trigger_marks_entry_and_dispatches_email(self, mock_send_breach_alert):
		entry = self._create_entry()
		mock_send_breach_alert.return_value = {
			"success": True,
			"alert_id": "alert-123",
			"message_id": "message-123",
			"error": None,
		}

		response = self.client.post(
			"/api/honeypot/trigger/",
			{
				"entry_id": str(entry.id),
				"severity": "high",
				"triggered_ip": "203.0.113.10",
			},
			format="json",
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["message"], "Honeypot alert recorded.")
		self.assertTrue(payload["email_alert"]["attempted"])
		self.assertTrue(payload["email_alert"]["success"])

		entry.refresh_from_db()
		self.assertTrue(entry.is_triggered)
		self.assertEqual(entry.triggered_ip, "203.0.113.10")
		self.assertIsNotNone(entry.triggered_at)

		self.assertEqual(mock_send_breach_alert.call_count, 1)
		call_kwargs = mock_send_breach_alert.call_args.kwargs
		self.assertEqual(call_kwargs["recipient_email"], self.user.email)
		self.assertEqual(call_kwargs["recipient_name"], self.user.username)
		self.assertEqual(call_kwargs["breach_details"]["category"], "api_key")
		self.assertEqual(call_kwargs["breach_details"]["severity"], "high")

	@patch("ai_engine.honeypot_alert_api.send_breach_alert")
	def test_trigger_with_missing_user_email_skips_dispatch(self, mock_send_breach_alert):
		user_without_email = get_user_model().objects.create_user(
			username="noemail",
			email="",
			password="StrongPass123!",
		)

		entry = self._create_entry(user=user_without_email)
		self.client.force_authenticate(user=user_without_email)

		response = self.client.post(
			"/api/honeypot/trigger/",
			{"entry_id": str(entry.id)},
			format="json",
		)

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertFalse(payload["email_alert"]["attempted"])
		self.assertFalse(payload["email_alert"]["success"])
		self.assertIn("no email", payload["email_alert"]["reason"].lower())

		entry.refresh_from_db()
		self.assertTrue(entry.is_triggered)
		self.assertIsNotNone(entry.triggered_at)
		self.assertEqual(mock_send_breach_alert.call_count, 0)


@override_settings(HONEYPOT={"ENABLED": False})
class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = "/api/auth/register/"
        self.token_url = "/api/auth/token/"
        self.refresh_url = "/api/auth/token/refresh/"
        self.user_data = {
            "username": "alice",
            "email": "alice@example.com",
            "password": "StrongPass123!",
        }

    def test_register_creates_user_and_returns_public_fields(self):
        response = self.client.post(self.register_url, self.user_data, format="json")
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["username"], self.user_data["username"])
        self.assertEqual(payload["email"], self.user_data["email"])
        self.assertIn("id", payload)
        self.assertNotIn("password", payload)

    def test_register_duplicate_username_is_rejected(self):
        self.client.post(self.register_url, self.user_data, format="json")
        response = self.client.post(
            self.register_url,
            {"username": "alice", "email": "alice2@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())

    def test_register_duplicate_email_is_rejected(self):
        self.client.post(self.register_url, self.user_data, format="json")
        response = self.client.post(
            self.register_url,
            {"username": "alice2", "email": "alice@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    def test_login_returns_jwt_tokens(self):
        get_user_model().objects.create_user(**self.user_data)
        response = self.client.post(
            self.token_url,
            {"username": self.user_data["username"], "password": self.user_data["password"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("access", payload)
        self.assertIn("refresh", payload)

    def test_refresh_token_rotates_access_token(self):
        get_user_model().objects.create_user(**self.user_data)
        login_response = self.client.post(
            self.token_url,
            {"username": self.user_data["username"], "password": self.user_data["password"]},
            format="json",
        )
        refresh_token = login_response.json().get("refresh")
        response = self.client.post(self.refresh_url, {"refresh": refresh_token}, format="json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("access", payload)
        self.assertNotEqual(payload.get("access"), login_response.json().get("access"))


@override_settings(HONEYPOT={"ENABLED": False})
class VaultEntryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username="vaultuser",
            email="vaultuser@example.com",
            password="VaultPass123!",
        )
        self.other_user = get_user_model().objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="OtherPass123!",
        )
        self.access_token = self._login_and_get_access_token(
            self.user.username, "VaultPass123!"
        )
        self.other_access_token = self._login_and_get_access_token(
            self.other_user.username, "OtherPass123!"
        )

    def _login_and_get_access_token(self, username, password):
        response = self.client.post(
            "/api/auth/token/",
            {"username": username, "password": password},
            format="json",
        )
        return response.json().get("access")

    def _auth_headers(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_store_and_retrieve_vault_entry(self):
        payload = {
            "label": "Test Secret",
            "ciphertext": "QmFzZTY0RW5jb2RlZERhdGE=",
            "iv": "dGVzdGl2",
            "salt": "dGVzdHNhbHQ=",
        }
        create_response = self.client.post(
            "/api/vault/store/",
            payload,
            format="json",
            **self._auth_headers(self.access_token),
        )
        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["label"], payload["label"])
        self.assertEqual(created["ciphertext"], payload["ciphertext"])
        self.assertEqual(created["iv"], payload["iv"])
        self.assertEqual(created["salt"], payload["salt"])

        list_response = self.client.get(
            "/api/vault/",
            format="json",
            **self._auth_headers(self.access_token),
        )
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        items = payload.get("results", [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], created["id"])
        self.assertEqual(items[0]["ciphertext"], payload["results"][0]["ciphertext"])

    def test_user_cannot_retrieve_other_users_entry(self):
        entry = self.client.post(
            "/api/vault/store/",
            {
                "label": "Other Secret",
                "ciphertext": "QmFzZTY0Q2lwaGVydGV4dA==",
                "iv": "b3RoZXJpdl9kYXRh",
                "salt": "b3RoZXJfc2FsdA==",
            },
            format="json",
            **self._auth_headers(self.other_access_token),
        ).json()

        response = self.client.get(
            f"/api/vault/{entry['id']}/",
            format="json",
            **self._auth_headers(self.access_token),
        )
        self.assertEqual(response.status_code, 404)

    def test_list_endpoint_returns_only_owned_entries(self):
        self.client.post(
            "/api/vault/store/",
            {
                "label": "Own Secret",
                "ciphertext": "QmFzZTY0T3du",
                "iv": "b3duaXZfZGF0YQ==",
                "salt": "b3duX3NhbHQ=",
            },
            format="json",
            **self._auth_headers(self.access_token),
        )
        self.client.post(
            "/api/vault/store/",
            {
                "label": "Other Secret",
                "ciphertext": "QmFzZTY0T3RoZXI=",
                "iv": "b3RoZXJpdl9kYXRh",
                "salt": "b3RoZXJfc2FsdA==",
            },
            format="json",
            **self._auth_headers(self.other_access_token),
        )

        list_response = self.client.get(
            "/api/vault/",
            format="json",
            **self._auth_headers(self.access_token),
        )
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        entries = payload.get("results", [])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["label"], "Own Secret")
