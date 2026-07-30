from django.urls import path

from .views import HistoryListCreateAPIView

urlpatterns = [
    path("", HistoryListCreateAPIView.as_view(), name="history-list-create"),
]
