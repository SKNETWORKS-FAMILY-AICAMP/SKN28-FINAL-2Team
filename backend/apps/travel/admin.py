from django.contrib import admin

from .models import (
    Accommodation,
    Itinerary,
    ItineraryDay,
    ItineraryItem,
    Package,
    Restaurant,
    TouristSpot,
)

admin.site.register(TouristSpot)
admin.site.register(Accommodation)
admin.site.register(Restaurant)
admin.site.register(Package)
admin.site.register(Itinerary)
admin.site.register(ItineraryDay)
admin.site.register(ItineraryItem)
