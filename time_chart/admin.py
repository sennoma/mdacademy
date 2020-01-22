from django.contrib import admin

from time_chart.models import User, Group, Place, TimeSlot

admin.site.register(Group)
admin.site.register(User)
admin.site.register(Place)
admin.site.register(TimeSlot)
