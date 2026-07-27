from django.conf import settings
from django.db import models


class History(models.Model):
    """사용자 이용 기록 로그.

    fake_data.json의 histories(id/date/time) 구조를 참고해 구성했다.
    추후 AI 대화(RAG) 세션이 연결되면 action="chat_start" 등으로 기록을 남길 수 있다.
    """

    class Action(models.TextChoices):
        VISIT = "visit", "방문"
        CHAT_START = "chat_start", "AI 대화 시작"
        SEARCH = "search", "검색"
        VIEW_PACKAGE = "view_package", "패키지 조회"
        ITINERARY_SAVE = "itinerary_save", "일정 저장"
        RESERVATION = "reservation", "예약 요청"

    code = models.CharField(
        max_length=20, unique=True, blank=True, null=True,
        help_text='예: HIS001 (외부/시드 데이터 참조용 코드)',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="histories", null=True, blank=True,
    )
    action = models.CharField(max_length=30, choices=Action.choices, default=Action.VISIT)
    detail = models.CharField(max_length=255, blank=True)

    date = models.DateField()
    time = models.TimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-time"]
        verbose_name = "이용 기록"
        verbose_name_plural = "이용 기록"

    def __str__(self):
        who = self.user.email if self.user else "anonymous"
        return f"[{self.code or self.id}] {who} - {self.action} ({self.date} {self.time})"
