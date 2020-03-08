from django.db import models


class Group(models.Model):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)
    allow_signup = models.BooleanField(default=False)
    week_limit = models.PositiveSmallIntegerField(default=2)

    def __str__(self):
        return self.name


class User(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    is_active = models.BooleanField(default=True)
    nick_name = models.CharField(max_length=100, default="")
    first_name = models.CharField(max_length=100, default="")
    last_name = models.CharField(max_length=100, default="")
    group = models.ForeignKey(Group, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.nick_name or " ".join((self.first_name, self.last_name))


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
    limit = models.PositiveSmallIntegerField(default=5)

    def __str__(self):
        return f"{self.date} {self.time} ({self.place})"
