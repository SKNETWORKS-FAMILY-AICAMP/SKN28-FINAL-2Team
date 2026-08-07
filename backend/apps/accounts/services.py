import requests

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from django.conf import settings

from .models import User


def google_login(token: str):
    info = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        settings.GOOGLE_CLIENT_ID,
    )

    email = info["email"]
    nickname = info.get("name", "")
    picture = info.get("picture", "")
    provider_id = info["sub"]

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "nickname": nickname,
            "profile_image": picture,
            "provider": "google",
            "provider_id": provider_id,
        },
    )

    if not created:
        user.nickname = nickname
        user.profile_image = picture
        user.provider = "google"
        user.provider_id = provider_id
        user.save(
            update_fields=[
                "nickname",
                "profile_image",
                "provider",
                "provider_id",
            ]
        )

    return user


def get_kakao_access_token(code: str) -> str:
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_REST_API_KEY,
        "redirect_uri": settings.KAKAO_REDIRECT_URI,
        "code": code,
    }

    if settings.KAKAO_CLIENT_SECRET:
        data["client_secret"] = settings.KAKAO_CLIENT_SECRET

    response = requests.post(
        "https://kauth.kakao.com/oauth/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
        data=data,
        timeout=15,
    )

    response.raise_for_status()

    token_data = response.json()

    return token_data["access_token"]



def kakao_login(access_token: str):

    response = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=15,
    )

    response.raise_for_status()

    info = response.json()

    account = info.get("kakao_account", {})
    profile = account.get("profile", {})

    provider_id = str(info["id"])
    email = account.get("email") or f"kakao_{provider_id}@users.tamnaplan.local"
    nickname = profile.get("nickname", "")
    picture = profile.get("profile_image_url", "")

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "nickname": nickname,
            "profile_image": picture,
            "provider": "kakao",
            "provider_id": provider_id,
        },
    )

    if not created:
        user.nickname = nickname
        user.profile_image = picture
        user.provider = "kakao"
        user.provider_id = provider_id
        user.save(
            update_fields=[
                "nickname",
                "profile_image",
                "provider",
                "provider_id",
            ]
        )

    return user