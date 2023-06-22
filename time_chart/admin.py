import datetime as dt
import io
from collections import defaultdict
from itertools import zip_longest

import xlsxwriter
from dal import autocomplete
from django import forms
from django.contrib import admin
from django.db import connection
from django.db.models import Count
from django.forms.widgets import TextInput
from django.http import HttpResponse
from django.urls import path

from time_chart.management.commands.config import (
    DATE_FORMAT,
    WEEKDAYS,
    WEEKDAYS_SHORT
)
from time_chart.management.commands.tools import logger
from time_chart.models import Group, Place, TimeSlot, User
from time_chart.views import UserAutocomplete, DefineScheduleView


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


class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'nick_name', 'first_name', 'last_name', 'is_active', 'group_name')
    actions = ["get_user_report"]
    list_filter = ('group_id',)

    def get_user_report(self, request, queryset):
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=schedule.xlsx'
        xlsx_data = self.make_report(queryset)
        response.write(xlsx_data)
        return response

    def make_report(self, queryset, complete=False):

        users = queryset.select_related().all()

        groups = list(set([user.group.name for user in users]))
        groups.sort()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)

        places = list(Place.objects.filter(is_active=True))
        places_count = len(places)

        slots=[]

        for user in users:
            slots += list(TimeSlot.objects.filter(people__id=user.id))

        dates = [slot.date for slot in slots]
        weeks = [(date.isocalendar()[0], date.isocalendar()[1]) for date in dates]
        weeks = list(set(weeks))
        weeks.sort()

        worksheet = workbook.add_worksheet()

        date_format = workbook.add_format({
            'align': 'center',
            'bold': True,
        })

        for user_index, user in enumerate(users):
            worksheet.write(2 + user_index, 0, user.last_name)

        for week_index, (year, week) in enumerate(weeks):

            week_begin = dt.datetime.strptime(f'{year} {week} 1', '%Y %W %w')
            week_end = dt.datetime.strptime(f'{year} {week} 0', '%Y %W %w')
            week_header = f'{year} {week_begin.month}.{week_begin.day}-{week_end.month}.{week_end.day}'

            if places_count == 1:
                worksheet.write(0,  1 + week_index, week_header, date_format)
            else:
                worksheet.merge_range(
                    0,
                    1 + week_index * places_count,
                    0,
                    1 + week_index * places_count + (places_count - 1),
                    week_header,
                    date_format)

            for place_index, place in enumerate(places):
                worksheet.write(1,  1 + week_index * places_count + place_index, place.name)

            for user_index, user in enumerate(users):

                for place_index, place in enumerate(places):

                    user_slots = list(TimeSlot.objects.filter(people__id=user.id, place_id=place.id).order_by('date'))

                    days = []
                    for slot_index, slot in enumerate(user_slots):
                        if slot.date.isocalendar()[0] == year and slot.date.isocalendar()[1] == week :
                            days.append(WEEKDAYS_SHORT[slot.date.weekday()])

                    worksheet.write(2 + user_index, 1 + week_index * places_count + place_index, ', '.join(days))

        workbook.close()

        return output.getvalue()

    def group_name(self, obj):
        if obj.group:
            return obj.group.name
        return ''

    group_name.admin_order_field = "group__name"

class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ('__all__')
        widgets = {
            'people': autocomplete.ModelSelect2Multiple(url='/admin/user-autocomplete/')
        }


class TimeSlotAdmin(admin.ModelAdmin):
    form = TimeSlotForm
    actions = ["get_complete_schedule", "get_current_schedule", "mark_closed", "mark_open"]
    ordering = ("place_id", "date", "time")
    list_filter = ('place_id',)

    def get_queryset(self, request):
        """
        Return a QuerySet of all model instances that can be edited by the
        admin site. This is used by changelist_view.
        """
        qs = super().get_queryset(request)
        qs = qs.filter(date__gte=dt.date.today())
        qs = qs.order_by('date', 'time', 'place')
        return qs

    def mark_open(modeladmin, request, queryset):
        queryset.update(open=True)

    def mark_closed(modeladmin, request, queryset):
        queryset.update(open=False)

    def get_current_schedule(self, request, queryset):
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=schedule.xlsx'
        xlsx_data = self.make_schedule(queryset)
        response.write(xlsx_data)
        return response

    get_current_schedule.short_description = "Export Selected time slots as Schedule"

    def get_complete_schedule(self, request, queryset):
        response = HttpResponse(content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=schedule.xlsx'
        xlsx_data = self.make_schedule(queryset, complete=True)
        response.write(xlsx_data)
        return response

    get_complete_schedule.short_description = "Export Complete Schedule"

    def make_schedule(self, queryset, complete=False):
        add_count = True

        if complete:
            qs = TimeSlot.objects.select_related().all()
        else:
            qs = queryset.select_related().all()

        times = list(set([time_slot.time.strftime('%H:%M') for time_slot in qs]))
        times.sort()

        people = set([u for t in qs for u in t.people.all()])

        column_width = max([len(str(p.group)) + len(p.last_name) + 4 for p in people])

        user_count = User.objects.filter(
            id__in=[p.id for p in people],
            timeslot__date__lt=dt.date.today()
        ).annotate(time_slot_count=Count('timeslot'))
        user_count = dict({u.id: u.time_slot_count for u in user_count})
        lines = [(line.place.name, line.date.isoformat(), line.time.strftime('%H:%M'),
                  str(u.group), u.last_name,
                  str(user_count.get(u.id, 0)),  # visit count
                  u.group.color)
                 for line in qs for u in line.people.all()]
        # partition by places
        records_by_date_place = defaultdict(list)
        for line in lines:
            # group by date+place
            records_by_date_place[(line[1], line[0])].append(line)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        try:
            merge_format = workbook.add_format({
                'align': 'center',
                'bold': True,
            })
            merge_format.set_border()

            worksheet = workbook.add_worksheet()
            row = 0
            for key in sorted(records_by_date_place.keys()):
                records = records_by_date_place[key]
                row += 1
                # merge cells and write 'day date place'
                date = dt.datetime.strptime(key[0], DATE_FORMAT).date()
                day = WEEKDAYS[date.weekday()]
                place = key[1]
                worksheet.merge_range(row, 1, row, len(times), f'{day}, {date.strftime("%d-%m-%Y")}, {place}', merge_format)
                worksheet.set_column(1, len(times), column_width)
                row += 1
                # write time slots
                col = 1
                for time in times:
                    cell_format = workbook.add_format()
                    cell_format.set_bold()
                    cell_format.set_border()
                    worksheet.write(row, col, time, cell_format)
                    # logger.debug("writing classes row")
                    col += 1
                row += 1
                students_lists = defaultdict(list)
                for line in sorted(records, key=lambda x: (x[3], x[4]) or ('', '')):  # sort by (group, last name)
                    string = f"{line[3]} {line[4]} ({line[5]})" if add_count else f"{line[3]} {line[4]}"
                    students_lists[line[2]].append((string, line[6]))  # append cell text and bg color
                lines = []
                for time in times:
                    lines.append(students_lists[time])
                for line in zip_longest(*lines, fillvalue=("", "")):
                    col = 1
                    for val, color in line:
                        if color:
                            cell_format = workbook.add_format()
                            cell_format.set_bg_color(color)
                            cell_format.set_border()
                            worksheet.write(row, col, val, cell_format)
                        else:
                            cell_format = workbook.add_format()
                            cell_format.set_border()
                            worksheet.write(row, col, val, cell_format)
                        # logger.debug("writing data row")
                        col += 1
                    row += 1
        except Exception as e:
            logger.error(e)
        finally:
            workbook.close()

        return output.getvalue()


admin_site.register(Group, GroupAdmin)
admin_site.register(User, UserAdmin)
admin_site.register(Place)
admin_site.register(TimeSlot, TimeSlotAdmin)
