import uuid
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()


class TouristSpot(models.Model):

    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    tags = models.CharField(max_length=255, blank=True, help_text="쉼표로 구분된 태그 (예: 힐링,자연,포토스팟)")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source_id = models.CharField( max_length=20, unique=True, null=True, blank=True, )

    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def __str__(self):
        return self.name

class Place(models.Model):
    content_id = models.BigIntegerField(primary_key=True)
    content_type_id = models.IntegerField()
    lcls3_code = models.CharField(max_length=30)
    title = models.CharField(max_length=255)
    addr1 = models.CharField(max_length=500, blank=True, null=True)
    addr2 = models.CharField(max_length=255, blank=True, null=True)
    area_code = models.IntegerField(blank=True, null=True)
    sigungu_code = models.IntegerField(blank=True, null=True)
    zipcode = models.CharField(max_length=20, blank=True, null=True)
    longitude = models.DecimalField(max_digits=16, decimal_places=12)
    latitude = models.DecimalField(max_digits=16, decimal_places=12)
    location = models.BinaryField()
    map_level = models.IntegerField(blank=True, null=True)
    api_created_at = models.DateTimeField(blank=True, null=True)
    api_modified_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "places"

    def __str__(self):
        return self.title
    

class Accommodation(models.Model):

    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    price_per_night = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    review_count = models.PositiveIntegerField(default=0)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Restaurant(models.Model):

    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    category = models.CharField(max_length=50, blank=True, help_text="예: 흑돼지, 해산물, 카페")
    price_range = models.CharField(max_length=50, blank=True, help_text="예: 1~2만원")
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    review_count = models.PositiveIntegerField(default=0)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Package(models.Model):

    class Category(models.TextChoices):
        STAY = "stay", "숙소"
        CAR = "car", "렌터카"
        ACTIVITY = "activity", "액티비티"
        TOUR = "tour", "투어"

    class Style(models.TextChoices):
        FAMILY = "family", "가족여행"
        HEALING = "healing", "힐링여행"
        ACTIVITY = "activity", "액티비티"
        FOOD = "food", "맛집여행"

    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=Category.choices)
    style = models.CharField(max_length=20, choices=Style.choices, blank=True)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    price = models.PositiveIntegerField(default=0)
    duration_days = models.PositiveSmallIntegerField(default=1, help_text="상품 이용 일수")
    region = models.CharField(max_length=50, blank=True, default="제주")
    accommodation_included = models.BooleanField(default=False)
    included_items = models.JSONField(default=list, blank=True, help_text='예: ["자차보험","내비게이션"]')
    course = models.JSONField(default=list, blank=True, help_text="코스 설명 리스트")
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    review_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


# 최종 여행 일정

class Itinerary(models.Model):
    """최종 여행 일정표 """

    class Style(models.TextChoices):
        FAMILY = "family", "가족여행"
        HEALING = "healing", "힐링여행"
        ACTIVITY = "activity", "액티비티"
        FOOD = "food", "맛집여행"
        TREKKING = "trekking", "트레킹"

    class Transport(models.TextChoices):
        CAR = "car", "렌터카"
        BUS = "bus", "버스"

    class Status(models.TextChoices):
        DRAFT = "draft", "임시저장"
        CONFIRMED = "confirmed", "확정"

    class CompanionType(models.TextChoices):
        SOLO = "solo", "혼자"
        COUPLE = "couple", "연인"
        FRIEND = "friend", "친구"
        FAMILY = "family", "가족"

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)

    title = models.CharField(max_length=150, default="제주 여행")
    subtitle = models.CharField(max_length=150, blank=True, help_text='예: "부모님과 함께"')

    start_date = models.DateField()
    end_date = models.DateField()
    companion_type = models.CharField(max_length=20, choices=CompanionType.choices, default=CompanionType.SOLO)
    companion_count = models.PositiveSmallIntegerField(default=1)
    transport = models.CharField(max_length=10, choices=Transport.choices, default=Transport.CAR)
    style = models.CharField(max_length=20, choices=Style.choices, blank=True)
    budget_per_person = models.PositiveIntegerField(null=True, blank=True)

    # M004-F-005 예상 비용(평균) — 카테고리별로 직접 보관 후 합산
    accommodation_cost = models.PositiveIntegerField(default=0, help_text="숙소")
    transport_cost = models.PositiveIntegerField(default=0, help_text="렌터카/교통")
    activity_cost = models.PositiveIntegerField(default=0, help_text="액티비티")
    food_cost = models.PositiveIntegerField(default=0, help_text="식비")
    etc_cost = models.PositiveIntegerField(default=0, help_text="기타")

    selected_package = models.ForeignKey(
        Package, on_delete=models.SET_NULL, null=True, blank=True, related_name="itineraries"
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    is_public = models.BooleanField(default=False, help_text="공개 설정 (선택)")
    share_token = models.UUIDField(null=True, blank=True, unique=True, help_text="공유 링크용 토큰")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def total_cost(self) -> int:
        """카테고리별 비용 합산."""
        return (
            self.accommodation_cost
            + self.transport_cost
            + self.activity_cost
            + self.food_cost
            + self.etc_cost
        )

    @property
    def duration_label(self) -> str:
        nights = (self.end_date - self.start_date).days
        return f"{nights}박 {nights + 1}일" if nights > 0 else "당일치기"

    def ensure_share_token(self):
        if not self.share_token:
            self.share_token = uuid.uuid4()
            self.save(update_fields=["share_token"])
        return self.share_token


class ItineraryDay(models.Model):
    """일자별 일정 """

    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name="days")
    day_number = models.PositiveSmallIntegerField(help_text="1일차, 2일차 ...")
    date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["day_number"]
        unique_together = ("itinerary", "day_number")

    def __str__(self):
        return f"{self.itinerary.title} - Day {self.day_number}"


class ItineraryItem(models.Model):
    """일자별 일정 항목 추천 결과 또는 사용자가 직접 추가."""

    class ItemType(models.TextChoices):
        SPOT = "spot", "관광지"
        RESTAURANT = "restaurant", "맛집"
        ACCOMMODATION = "accommodation", "숙소"
        ACTIVITY = "activity", "액티비티"
        CUSTOM = "custom", "직접 추가"

    day = models.ForeignKey(ItineraryDay, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveSmallIntegerField(default=0)
    time = models.CharField(max_length=10, blank=True, help_text='예: "09:30"')

    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.CUSTOM)
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True)
    thumbnail = models.CharField(max_length=10, blank=True, help_text="이모지 썸네일 (예: 🌋)")
    cost = models.PositiveIntegerField(default=0)

    # 카탈로그 연동 추천 결과에서 가져온 경우 원본 참조
    spot = models.ForeignKey(TouristSpot, on_delete=models.SET_NULL, null=True, blank=True)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.SET_NULL, null=True, blank=True)
    accommodation = models.ForeignKey(Accommodation, on_delete=models.SET_NULL, null=True, blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    memo = models.CharField(max_length=255, blank=True, help_text="직접 추가 일정용 메모")

    class Meta:
        ordering = ["order", "time"]

    def __str__(self):
        return f"{self.title} ({self.day})"
