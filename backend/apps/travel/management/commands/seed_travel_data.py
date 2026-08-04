from django.core.management.base import BaseCommand

from apps.travel.models import Accommodation, Package, Restaurant, TouristSpot


SPOTS = [
    dict(name="성산일출봉", address="제주 서귀포시 성산읍", description="일출 명소로 유명한 제주 동쪽의 대표 관광지",
         tags="자연,포토스팟,대표관광지", latitude=33.4581, longitude=126.9425),
    dict(name="섭지코지", address="제주 서귀포시 성산읍", description="해안 절벽과 등대가 어우러진 산책로",
         tags="자연,해안,포토스팟", latitude=33.4238, longitude=126.9280),
    dict(name="협재해변", address="제주 제주시 한림읍", description="에메랄드빛 바다와 하얀 모래 백사장",
         tags="해변,힐링,포토스팟", latitude=33.3941, longitude=126.2397),
    dict(name="사려니숲길", address="제주 제주시 조천읍", description="편백나무 향 가득한 산책로",
         tags="자연,힐링,산책", latitude=33.4088, longitude=126.6796),
    dict(name="중문관광단지", address="제주 서귀포시 중문동", description="다양한 액티비티와 리조트가 모인 관광단지",
         tags="액티비티,가족여행", latitude=33.2497, longitude=126.4128),
    dict(name="오설록 티뮤지엄", address="제주 서귀포시 안덕면", description="녹차밭과 티하우스를 함께 즐길 수 있는 공간",
         tags="힐링,포토스팟,카페", latitude=33.3055, longitude=126.2886),
    dict(name="카페 스누피가든", address="제주 제주시 구좌읍", description="사진 찍기 좋은 테마 카페 겸 정원",
         tags="카페,포토스팟,가족여행", latitude=33.4959, longitude=126.7885),
    dict(name="아르떼뮤지엄", address="제주 제주시 애월읍", description="몰입형 미디어아트 전시 공간",
         tags="실내,포토스팟,액티비티", latitude=33.4589, longitude=126.3355),
]

RESTAURANTS = [
    dict(name="똔사돈 본점", address="제주 제주시", description="현지인 추천 흑돼지 맛집",
         category="흑돼지", price_range="3~4만원", rating=4.7, review_count=890,
         latitude=33.4996, longitude=126.5312),
    dict(name="해녀의 부엌", address="제주 서귀포시", description="해물뚝배기가 대표 메뉴인 맛집",
         category="해산물", price_range="2~3만원", rating=4.6, review_count=412,
         latitude=33.2541, longitude=126.5602),
    dict(name="옛날물회국수", address="제주 서귀포시", description="제주식 시원한 물회국수 전문점",
         category="분식/국수", price_range="1~2만원", rating=4.5, review_count=356,
         latitude=33.2489, longitude=126.5601),
]

ACCOMMODATIONS = [
    dict(name="협재 오션스테이", address="제주 제주시 한림읍", description="협재해변 도보 5분 거리의 오션뷰 숙소",
         price_per_night=79500, rating=4.6, review_count=321,
         latitude=33.3946, longitude=126.2401),
]

PACKAGES = [
    dict(
        name="오션뷰 힐링 숙소", category=Package.Category.STAY, style=Package.Style.HEALING,
        description="협재 오션스테이 2박 패키지",
        price=159000, duration_days=2, accommodation_included=True,
        included_items=["오션뷰 객실", "조식 2인"], course=["체크인 15:00", "체크아웃 11:00"],
        rating=4.6, review_count=321,
    ),
    dict(
        name="렌터카 3일", category=Package.Category.CAR, style=Package.Style.FAMILY,
        description="아반떼 CN7 (자차 포함) 3일 대여",
        price=89700, duration_days=3, accommodation_included=False,
        included_items=["자차보험", "내비게이션", "블랙박스"], course=[],
        rating=4.7, review_count=532,
    ),
    dict(
        name="제주 승마 체험 2인", category=Package.Category.ACTIVITY, style=Package.Style.ACTIVITY,
        description="숲속 승마 트래킹 체험 (2인 기준)",
        price=70000, duration_days=1, accommodation_included=False,
        included_items=["승마 장비 대여", "안전 교육", "기념사진"], course=["트래킹 40분"],
        rating=4.8, review_count=218,
    ),
]


class Command(BaseCommand):
    help = "프론트엔드(React)에서 이미 사용 중인 이름/가격과 일치하는 관광지·숙소·맛집·패키지 샘플 데이터를 적재한다."

    def handle(self, *args, **options):
        spot_count = self._seed(TouristSpot, SPOTS)
        rest_count = self._seed(Restaurant, RESTAURANTS)
        acc_count = self._seed(Accommodation, ACCOMMODATIONS)
        pkg_count = self._seed(Package, PACKAGES)

        self.stdout.write(self.style.SUCCESS(
            f"완료: 관광지 {spot_count}건, 맛집 {rest_count}건, "
            f"숙소 {acc_count}건, 패키지 {pkg_count}건 확인/생성됨"
        ))

    @staticmethod
    def _seed(model, rows):
        count = 0
        for row in rows:
            _, created = model.objects.get_or_create(name=row["name"], defaults=row)
            count += 1
        return count
