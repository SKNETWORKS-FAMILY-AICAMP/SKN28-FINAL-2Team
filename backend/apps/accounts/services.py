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


def kakao_login(access_token: str):

    response = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    response.raise_for_status()

    info = response.json()

    account = info.get("kakao_account", {})
    profile = account.get("profile", {})

    email = account.get("email")
    nickname = profile.get("nickname", "")
    picture = profile.get("profile_image_url", "")
    provider_id = str(info["id"])

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