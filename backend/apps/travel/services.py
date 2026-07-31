from datetime import timedelta
import traceback

from django.db import transaction

from .models import (
    Place,
    Itinerary,
    ItineraryDay,
    ItineraryItem,
)


@transaction.atomic
def generate_itinerary(itinerary: Itinerary):
    print("===== generate_itinerary 시작 =====")

    try:
        itinerary.days.all().delete()
        print("기존 일정 삭제 완료")

        places = list(Place.objects.order_by("content_id"))
        print(f"Place 개수: {len(places)}")

        if not places:
            print("Place가 없습니다.")
            return itinerary

        total_days = (itinerary.end_date - itinerary.start_date).days + 1
        print(f"생성할 일수: {total_days}")

        schedule_times = ["09:00", "11:00", "14:00", "16:00"]
        thumbnails = ["🌄", "📸", "🍴", "🌅"]

        place_index = 0

        for day in range(total_days):
            print(f"Day {day + 1} 생성")

            itinerary_day = ItineraryDay.objects.create(
                itinerary=itinerary,
                day_number=day + 1,
                date=itinerary.start_date + timedelta(days=day),
            )

            print(f"ItineraryDay id={itinerary_day.id}")

            for order in range(4):
                place = places[place_index % len(places)]
                place_index += 1

                ItineraryItem.objects.create(
                    day=itinerary_day,
                    order=order + 1,
                    time=schedule_times[order],
                    item_type=ItineraryItem.ItemType.SPOT,
                    title=place.title,
                    description=place.addr1 or "",
                    thumbnail=thumbnails[order],
                    latitude=place.latitude,
                    longitude=place.longitude,
                    cost=0,
                    spot=None,
                    restaurant=None,
                    accommodation=None,
                    memo="",
                )

            print(f"Day {day + 1} 완료")

        print("===== generate_itinerary 완료 =====")
        return itinerary

    except Exception:
        traceback.print_exc()
        raise