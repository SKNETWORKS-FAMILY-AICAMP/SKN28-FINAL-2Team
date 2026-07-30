from django.urls import path

from .views import GoogleLoginAPIView, KakaoLoginAPIView, LogoutAPIView, MeAPIView

urlpatterns = [
    path("google/", GoogleLoginAPIView.as_view(), name="google-login"),
    path("kakao/", KakaoLoginAPIView.as_view(), name="kakao-login"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("me/", MeAPIView.as_view(), name="me"),
]