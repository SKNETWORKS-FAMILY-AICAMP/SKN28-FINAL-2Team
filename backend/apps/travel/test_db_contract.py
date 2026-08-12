from datetime import date
from unittest.mock import patch

from django.db import connections, models
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from django.test.utils import override_settings

from config.env_validation import validate_production_environment

from .models import Itinerary, Package
from .serializers import ItinerarySerializer


def _production_environment(**overrides):
    environment = {
        "DJANGO_SECRET_KEY": "test-secret",
        "ALLOWED_HOSTS": "api.example.com",
        "CORS_ALLOWED_ORIGINS": "https://example.com",
        "CSRF_TRUSTED_ORIGINS": "https://api.example.com",
        "MYSQL_HOST": "db.example.internal",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "app",
        "MYSQL_PASSWORD": "secret",
        "ACCOUNT_DB_NAME": "accounts",
        "TRAVEL_DB_NAME": "travel",
        "MYSQL_DATABASE": "travel",
        "OPENAI_API_KEY": "test-key",
        "CHROMA_MODE": "http",
        "CHROMA_HOST": "chroma.example.internal",
        "CHROMA_PORT": "8000",
    }
    environment.update(overrides)
    return environment


class ProductionEnvironmentContractTests(SimpleTestCase):
    def test_mysql_connector_backend_is_django_compatible(self):
        self.assertEqual(connections["default"].display_name, "MySQL")

    def test_mysql_connections_enable_strict_mode(self):
        expected = "SET sql_mode='STRICT_TRANS_TABLES'"

        for alias in ("default", "travel"):
            self.assertEqual(
                connections[alias].settings_dict["OPTIONS"]["init_command"],
                expected,
            )

    def test_valid_http_environment_passes(self):
        validate_production_environment(_production_environment())

    def test_shared_catalog_database_names_must_match(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "must identify the same"):
            validate_production_environment(
                _production_environment(MYSQL_DATABASE="other_travel")
            )

    def test_production_origins_must_use_https(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "https://"):
            validate_production_environment(
                _production_environment(CORS_ALLOWED_ORIGINS="http://example.com")
            )

    def test_production_requires_shared_http_chroma(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "must be 'http'"):
            validate_production_environment(
                _production_environment(
                    CHROMA_MODE="persistent",
                    CHROMA_PERSIST_DIRECTORY="/data",
                )
            )


class ReadinessEndpointTests(SimpleTestCase):
    @override_settings(
        ALLOWED_HOSTS=["api.example.com"],
        SECURE_SSL_REDIRECT=True,
    )
    def test_health_allows_internal_alb_http_probe(self):
        response = self.client.get("/health/", HTTP_HOST="10.20.18.103:8000")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("config.urls._readiness_status", return_value={"databases": "ok"})
    def test_ready_returns_dependency_status(self, _status):
        response = self.client.get("/ready/", secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")

    @patch("config.urls._readiness_status", side_effect=RuntimeError("offline"))
    def test_ready_returns_503_without_internal_details(self, _status):
        response = self.client.get("/ready/", secure=True)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unavailable", "error": "RuntimeError"},
        )


class CrossDatabaseReferenceContractTests(SimpleTestCase):
    def test_package_model_matches_the_seeded_catalog_schema(self):
        field_names = {field.name for field in Package._meta.local_fields}

        self.assertIn("match_profile", field_names)
        self.assertNotIn("companion", field_names)
        self.assertNotIn("tags", field_names)

    def test_selected_package_keeps_the_existing_column_without_a_foreign_key(self):
        field = Itinerary._meta.get_field("selected_package")

        self.assertIsInstance(field, models.BigIntegerField)
        self.assertEqual(field.db_column, "selected_package_id")

    def test_selected_package_keeps_the_serializer_api_field(self):
        serializer = ItinerarySerializer(
            data={
                "start_date": "2026-08-10",
                "end_date": "2026-08-11",
                "selected_package": 777,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["selected_package"], 777)


class ItineraryDatabaseContractTests(TestCase):
    def test_selected_package_id_is_stored_without_a_catalog_row(self):
        itinerary = Itinerary.objects.create(
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 11),
            selected_package=777,
        )

        saved = Itinerary.objects.get(pk=itinerary.pk)
        self.assertEqual(saved.selected_package, 777)
