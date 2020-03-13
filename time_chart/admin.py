import datetime as dt
from itertools import product

from dal import autocomplete
from django import forms
from django.contrib import admin, messages
from django.forms.widgets import TextInput
from django.shortcuts import redirect, render
from django.urls import path
from django.views.generic import FormView

from time_chart.models import Group, Place, TimeSlot, User


class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = User.objects.all()
        if self.q:
            qs = qs.filter(nick_name__istartswith=self.q)
        return qs


class DefineScheduleForm(forms.Form):
    place = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(),
        queryset=Place.objects.all(),
        required=True
    )

    start_date = forms.DateField(widget=forms.SelectDateWidget(), initial=dt.date.today)
    end_date = forms.DateField(widget=forms.SelectDateWidget(), initial=dt.date.today)

    times = (dt.time(i) for i in range(10, 22, 2))
    TIME_CHOICES = tuple(((t, str(t)) for t in times))
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
        if not form.is_valid():
            messages.add_message(self.request, messages.WARNING, "Form is invalid")
            # TODO: how to show form invalid
            return redirect('/admin/time_chart/timeslot/create-schedule/')

        time_slots = []
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        if start_date > end_date:
            messages.add_message(self.request, messages.WARNING,
                                 "end_date should be greater than start_date")
            return redirect('/admin/time_chart/timeslot/create-schedule/')
        if (end_date - start_date).days > 7:
            messages.add_message(self.request, messages.WARNING,
                                 "You are trying to add too many days into schedule")
            return redirect('/admin/time_chart/timeslot/create-schedule/')
        dates = []
        date = start_date
        while date <= end_date:
            dates.append(date)
            date += dt.timedelta(days=1)
        for place, date, time in product(form.cleaned_data['place'],
                                         dates,
                                         # form.cleaned_data['date'],
                                         form.cleaned_data['time']):
            time_slots.append(TimeSlot(place=place,
                                       date=date,
                                       time=time))
        TimeSlot.objects.bulk_create(time_slots)
        messages.add_message(self.request, messages.WARNING,
                             "TimeSlots are created")
        return redirect('/admin/time_chart/timeslot')


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
            path(
                'user-autocomplete/',
                self.admin_view(UserAutocomplete.as_view()),
                name='user-autocomplete',
            ),
        ]
        return new_urls + urls


admin_site = ScheduleAdmin(name='scheduleadmin')


class GroupForm(forms.ModelForm):

    class Meta:
        model = Group
        fields = '__all__'
        widgets = {
            'color': TextInput(attrs={'type': 'color'}),
        }


class GroupAdmin(admin.ModelAdmin):
    form = GroupForm
    list_display = ('name', 'is_active', 'allow_signup', 'week_limit')


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ('__all__')
        widgets = {
            'people': autocomplete.ModelSelect2Multiple(url='/admin/user-autocomplete/')
        }


class TimeSlotAdmin(admin.ModelAdmin):
    form = TimeSlotForm


admin_site.register(Group, GroupAdmin)
admin_site.register(User)
admin_site.register(Place)
admin_site.register(TimeSlot, TimeSlotAdmin)
