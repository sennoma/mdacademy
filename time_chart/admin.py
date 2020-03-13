import csv
import datetime as dt
from dal import autocomplete
from django import forms
from django.contrib import admin
from django.forms.widgets import TextInput
from django.http import HttpResponse
from django.urls import path

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


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ('__all__')
        widgets = {
            'people': autocomplete.ModelSelect2Multiple(url='/admin/user-autocomplete/')
        }


class TimeSlotAdmin(admin.ModelAdmin):
    form = TimeSlotForm
    actions = ["export_as_csv"]

    def get_queryset(self, request):
        """
        Return a QuerySet of all model instances that can be edited by the
        admin site. This is used by changelist_view.
        """
        qs = super().get_queryset(request)
        qs = qs.filter(date__gte=dt.date.today())
        qs = qs.order_by('date', 'time', 'place')
        return qs

    def export_as_csv(self, request, queryset):

        meta = self.model._meta
        field_names = [field.name for field in meta.fields]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(meta)
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            row = writer.writerow([getattr(obj, field) for field in field_names])

        return response

    export_as_csv.short_description = "Export Selected time slots as Schedule"


# def schedule(bot, update, args):
#     add_count = False
#     full_schedule = False
#     if len(args) > 0:
#         if args[0] not in ('++', 'all'):
#             bot.send_message(chat_id=update.message.chat_id, text="Наверное аргумент неправильный.")
#             return
#         add_count = args[0] == '++'
#         full_schedule = args[0] == 'all'
#
#     if full_schedule:
#         schedule = db.execute_select(db.get_full_schedule_sql, (dt.date(2019, 4, 1).isoformat(),))
#     else:
#         schedule = db.execute_select(db.get_full_schedule_sql, (dt.date.today().isoformat(),))
#
#     user_ids = list(set(map(lambda x: x[5] or 'unknown', schedule)))
#     user_count = db.execute_select(db.get_user_visits_count, (dt.date.today().isoformat(), user_ids))
#     user_count = dict(user_count)
#     lines = [(line[0], str(line[1]), line[2],  # place, date, time
#                        str(line[3]), line[4],  # GroupNum LastName
#                        str(user_count.get(line[5], 0)))  # visit count
#              for line in schedule]
#     # partition by places
#     records_by_date_place = defaultdict(list)
#     for line in lines:
#         # group by date+place
#         records_by_date_place[(line[1], line[0])].append(line)
#     workbook = xlsxwriter.Workbook('/tmp/schedule.xlsx')
#     try:
#         merge_format = workbook.add_format({
#             'align': 'center',
#             'bold': True,
#         })
#         worksheet = workbook.add_worksheet()
#         row = 0
#         for key in sorted(records_by_date_place.keys()):
#             records = records_by_date_place[key]
#             row += 1
#             # merge cells and write 'day date place'
#             date = dt.datetime.strptime(key[0], DATE_FORMAT).date()
#             day = WEEKDAYS[date.weekday()]
#             place = key[1]
#             worksheet.merge_range(row, 1, row, 4, f"{day}, {date}, {place}", merge_format)
#             row += 1
#             # write time slots
#             col = 1
#             for time in CLASSES_HOURS:
#                 worksheet.write(row, col, time)
#                 col += 1
#             row += 1
#             students_lists = defaultdict(list)
#             for line in sorted(records, key=lambda x: x[4] or ''):  # sort by last name
#                 string = f"{line[3]} {line[4]} ({line[5]})" if add_count else f"{line[3]} {line[4]}"
#                 students_lists[line[2]].append(string)
#             lines = []
#             for time in CLASSES_HOURS:
#                 lines.append(students_lists[time])
#             for line in zip_longest(*lines, fillvalue=""):
#                 col = 1
#                 for val in line:
#                     worksheet.write(row, col, val)
#                     col += 1
#                 row += 1
#     except Exception as e:
#         logger.error(e)
#     finally:
#         workbook.close()
#         bot.send_document(chat_id=update.message.chat_id, document=open('/tmp/schedule.xlsx', 'rb'))


admin_site.register(Group, GroupAdmin)
admin_site.register(User)
admin_site.register(Place)
admin_site.register(TimeSlot, TimeSlotAdmin)
