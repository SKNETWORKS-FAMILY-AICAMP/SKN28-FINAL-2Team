from django.contrib import admin

from .models import CartItem, Reservation, ReservationItem

admin.site.register(CartItem)
admin.site.register(Reservation)
admin.site.register(ReservationItem)
