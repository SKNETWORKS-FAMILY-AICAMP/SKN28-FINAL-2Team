from __future__ import annotations

import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate

from apps.travel.views import ItineraryViewSet


engine_state = {
    "condition": {"duration_days": 1, "party_type": "solo"},
    "itinerary": {"days": []},
}

with (
    patch("apps.travel.views.recommend_packages") as mocked_recommend,
    patch.object(ItineraryViewSet, "get_object") as mocked_get_object,
):
    mocked_get_object.return_value = SimpleNamespace(engine_state=engine_state)
    mocked_recommend.return_value = {
        "status": "completed",
        "recommendations": [{"package_id": "VIRTUAL-JEJU-D1-01"}],
    }
    request = APIRequestFactory().get(
        "/api/travel/itineraries/1/package-recommendations/",
        {"top_k": 3},
    )
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
    view = ItineraryViewSet.as_view({"get": "package_recommendations"})
    response = view(request, pk=1)

    assert response.status_code == 200, response.status_code
    mocked_recommend.assert_called_once_with(engine_state, top_k=3)
    print("authenticated package recommendation smoke: PASS (HTTP 200, top_k=3)")
