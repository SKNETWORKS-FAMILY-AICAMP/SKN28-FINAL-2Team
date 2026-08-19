from django.test import TestCase, override_settings


class DevLoginAPIViewTests(TestCase):

    @override_settings(DEBUG=True)
    def test_issues_tokens_for_the_local_development_user(self):
        response = self.client.post("/api/accounts/dev-login/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())

    @override_settings(DEBUG=False)
    def test_is_unavailable_outside_debug_mode(self):
        response = self.client.post("/api/accounts/dev-login/", secure=True)

        self.assertEqual(response.status_code, 404)
