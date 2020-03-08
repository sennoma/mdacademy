import datetime as dt
from itertools import product

from django import forms
from django.contrib import admin, messages
from django.shortcuts import render
from django.urls import path
from django.views.generic import FormView
from django.shortcuts import redirect

from time_chart.models import Group, Place, TimeSlot, User


class DefineScheduleForm(forms.Form):
    times = (dt.time(i) for i in range(10, 22, 2))
    TIME_CHOICES = tuple(((t, str(t)) for t in times))
    place = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(),
        queryset=Place.objects.all(),
        required=True
    )

    dates = (dt.date.today()+dt.timedelta(days=i) for i in range(7))
    DATE_CHOICES = tuple(((d, str(d)) for d in dates))
    date = forms.TypedMultipleChoiceField(
        choices=DATE_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        # coerce=dt.date,
        required=False
    )
    # start_date = forms.DateField(widget=forms.SelectDateWidget(), initial=dt.date.today)
    # end_date = forms.DateField(widget=forms.SelectDateWidget(), initial=dt.date.today)
    time = forms.TypedMultipleChoiceField(
        choices=TIME_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        # coerce=dt.time,
        required=False
    )


class DefineScheduleView(FormView):
    template_name = 'admin/add_time_slots.html'
    form_class = DefineScheduleForm

    def get(self, request, *args, **kwargs):
        form = self.form_class()
        context = {
            'form': form,
            'title': "Add TimeSlots"
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = DefineScheduleForm(request.POST)
        if form.is_valid():
            time_slots = []
            for place, date, time in product(form.cleaned_data['place'],
                                             form.cleaned_data['date'],
                                             form.cleaned_data['time']):
                time_slots.append(TimeSlot(place=place,
                                           date=date,
                                           time=time))
            TimeSlot.objects.bulk_create(time_slots)
            messages.add_message(self.request, messages.WARNING,
                                 "TimeSlots are created")
            return redirect('/admin/time_chart/timeslot')

        messages.add_message(self.request, messages.WARNING, "Form is invalid")
        return redirect('/admin')


class ScheduleAdmin(admin.AdminSite):

    site_title = 'Time Chart Bot'
    index_title = 'Schedule admin'
    site_header = 'MotoDrug Academy'

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [
            path('time_chart/timeslot/create-schedule/',
                 self.admin_view(DefineScheduleView.as_view()),
                 name='create_schedule'),
        ]
        return new_urls + urls


admin_site = ScheduleAdmin(name='scheduleadmin')


class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'allow_signup', 'week_limit')


admin_site.register(Group, GroupAdmin)
admin_site.register(User)
admin_site.register(Place)
admin_site.register(TimeSlot)
