from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from .serializers import PackageSerializer


class PackageSerializerTests(SimpleTestCase):
    def test_course_returns_saved_places_without_external_route_calls(self):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchall.return_value = [
            (1, 1, "tourism", 123, "협재해변", "제주시", "한림읍", 33.3, 126.2)
        ]
        connection = MagicMock()
        connection.cursor.return_value = cursor

        with patch("django.db.connections", {"travel": connection}):
            course = PackageSerializer().get_course(SimpleNamespace(id=7))

        self.assertEqual(
            course,
            [
                {
                    "day": 1,
                    "items": [
                        {
                            "sequence": 1,
                            "item_type": "tourism",
                            "content_id": 123,
                            "title": "협재해변",
                            "address": "제주시 한림읍",
                            "latitude": 33.3,
                            "longitude": 126.2,
                        }
                    ],
                }
            ],
        )
