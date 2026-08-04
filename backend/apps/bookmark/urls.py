from django.urls import path

from .views import BookmarkDetailAPIView, BookmarkListCreateAPIView

urlpatterns = [
    path("", BookmarkListCreateAPIView.as_view(), name="bookmark-list-create"),
    path("<int:pk>/", BookmarkDetailAPIView.as_view(), name="bookmark-detail"),
]
