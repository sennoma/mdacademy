import aiohttp
import asyncio
import urllib.parse

from django.db import models
from model_utils import FieldTracker

from time_chart.management.commands import config


async def send_notifications(chat_ids):
    async with aiohttp.ClientSession() as session:
        msg = urllib.parse.quote("Для вашей группы расписание открыто для записи на занятия.")
        for chat_id in chat_ids:
            await session.get(f'https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage?chat_id={chat_id}&text={msg}')


class Group(models.Model):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)
    allow_signup = models.BooleanField(default=False)
    week_limit = models.PositiveSmallIntegerField(default=2)
    color = models.CharField(max_length=9, default="#ffffff00")

    tracker = FieldTracker()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.pk and not self.tracker.previous('allow_signup') and self.allow_signup:
            chat_ids = [u.bot_chat_id for u in self.user_set.all()]

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            task = send_notifications(chat_ids)
            loop.run_until_complete(task)


class User(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    is_active = models.BooleanField(default=True)
    nick_name = models.CharField(max_length=100, default="", blank=True)
    first_name = models.CharField(max_length=100, default="", blank=True)
    last_name = models.CharField(max_length=100, default="")
    group = models.ForeignKey(Group, null=True, on_delete=models.SET_NULL)
    bot_chat_id = models.BigIntegerField(null=True)

    def __str__(self):
        return self.last_name or self.nick_name


# *********** Time Schedule models ***************************

class Place(models.Model):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class TimeSlot(models.Model):

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['place', 'date', 'time'],
                name='time_slot_place_date_time_key')
        ]

    place = models.ForeignKey(Place, null=True, on_delete=models.SET_NULL)
    date = models.DateField()
    time = models.TimeField()
    open = models.BooleanField(default=False)

    people = models.ManyToManyField(User, blank=True)
    limit = models.PositiveSmallIntegerField(default=8)

    allowed_groups = models.ManyToManyField(Group, default=None, blank=True)

    def __str__(self):
        return f"{self.date} {self.time} ({self.place})"
