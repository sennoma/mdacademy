import os

# bot config
BOT_TOKEN = os.environ['BOT_TOKEN']

CLASSES_HOURS = ["10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"

# Conversation states
(ASK_PLACE_STATE,
 ASK_DATE_STATE,
 ASK_TIME_STATE,
 RETURN_UNSUBSCRIBE_STATE,
 ACCEPT_TERMS_STATE,
 ASK_GROUP_NUM_STATE,
 ASK_LAST_NAME_STATE,
 REMOVE_SCHEDULE_STATE) = range(8)

# classes states
CLOSED, OPEN = False, True

LIST_OF_ADMINS = list(map(int, os.environ['ADMIN_IDS'].split(',')))

WEEKDAYS = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье"
)

WEEKDAYS_SHORT = (
    "Пн",
    "Вт",
    "Ср",
    "Чт",
    "Пт",
    "Сб",
    "Вc"
)
