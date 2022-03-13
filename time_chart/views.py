import datetime as dt
from itertools import product

from dal import autocomplete
from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.generic import FormView

from time_chart.models import Group, Place, TimeSlot, User


class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = User.objects.select_related('group')
        if self.q:
            q = None
            try:
                q = int(self.q)
            except ValueError:
                pass

            if q:
                qs = qs.filter(id=q)
            else:
                qs = qs.filter(last_name__istartswith=self.q)

        return qs.all()

    def get_result_label(self, item):
        return f"{item.last_name} {item.first_name} ({item.group.name})"


class DefineScheduleForm(forms.Form):
    place = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(),
        queryset=Place.objects.all(),
        required=True
    )

    groups = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(),
        queryset=Group.objects.filter(is_active=True).all(),
        required=False
    )

    start_date = forms.DateField(widget=forms.SelectDateWidget(), initial=dt.date.today)
    end_date = forms.DateField(widget=forms.SelectDateWidget(), initial=dt.date.today)

    time = forms.TimeField(widget=forms.TimeInput(), required=True)
    open = forms.BooleanField(initial=True, required=False)


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
        open = form.cleaned_data['open']
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
        groups = form.cleaned_data['groups']
        time = form.cleaned_data['time']
        for place, date in product(form.cleaned_data['place'], dates):
            ts = TimeSlot(place=place, date=date, time=time, open=open)
            ts.save()
            ts.allowed_groups.set(groups or [])
            time_slots.append(ts)
            ts.save()
        messages.add_message(self.request, messages.WARNING, "TimeSlots are created")
        return redirect('/admin/time_chart/timeslot')
