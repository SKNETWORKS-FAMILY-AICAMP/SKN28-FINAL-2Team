from django.conf import settings
from django.db import models

from apps.travel.models import Package


class Bookmark(models.Model):

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="bookmarked_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "package")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} ♥ {self.package.name}"
