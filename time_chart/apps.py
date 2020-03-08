from django.apps import AppConfig
from django.contrib.admin.apps import SimpleAdminConfig


class TimeChartAdminConfig(SimpleAdminConfig):
    name = 'time_chart'
    verbose_name = 'Time Chart Bot'
    default_site = 'time_chart.admin.ScheduleAdmin'
