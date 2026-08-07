from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    ordering = ("id",)

    list_display = (
        "id",
        "email",
        "nickname",
        "provider",
        "is_staff",
    )

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("User", {"fields": ("nickname", "profile_image", "provider", "provider_id")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "nickname",
                    "provider",
                    "provider_id",
                ),
            },
        ),
    )

    search_fields = ("email",)