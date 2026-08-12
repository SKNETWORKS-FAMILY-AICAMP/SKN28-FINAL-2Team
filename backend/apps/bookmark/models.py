from django.conf import settings
from django.db import models


class Bookmark(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )

    package_db_id = models.BigIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "package_db_id")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} ♥ package {self.package_db_id}"