from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    username = None

    PROVIDER_CHOICES = (
        ("google", "Google"),
        ("kakao", "Kakao"),
    )

    STYLE_CHOICES = (
        ("family", "가족형"),
        ("healing", "힐링형"),
        ("activity", "액티비티형"),
        ("food", "맛집형"),
    )

    email = models.EmailField(unique=True)
    nickname = models.CharField(max_length=50)
    profile_image = models.URLField(blank=True)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_id = models.CharField(max_length=100, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    preferred_style = models.CharField(max_length=20, choices=STYLE_CHOICES, blank=True)
    preferred_budget = models.PositiveIntegerField(null=True, blank=True, help_text="1인당 선호 예산(원)")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email