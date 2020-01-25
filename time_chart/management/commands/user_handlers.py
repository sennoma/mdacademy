import datetime as dt

from django.db.models import Count
from telegram import (
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardButton,
)
from telegram.ext import ConversationHandler

from time_chart.models import Group, User, Place, TimeSlot

from time_chart.management.commands.config import (
    ASK_GROUP_NUM_STATE,
    ASK_LAST_NAME_STATE,
    ASK_PLACE_STATE,
    ASK_DATE_STATE,
    ASK_TIME_STATE,
    LIST_OF_ADMINS,
    WEEKDAYS,
    WEEKDAYS_SHORT,
    DATE_FORMAT,
    TIME_FORMAT,
    RETURN_UNSUBSCRIBE_STATE,
)
from time_chart.management.commands.tools import (
    ReplyKeyboardWithCancel
)


# commands
def start_cmd(update, context):
    bot = context.bot
    user_id = update.effective_user.id
    nick = update.effective_user.username or ""
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    usr, _ = User.objects.get_or_create(id=user_id)
    usr.nick_name = nick
    usr.first_name = first_name
    usr.last_name = last_name
    usr.save()

    groups = Group.objects.filter(is_active=True).only('name')
    if groups:
        keyboard = [[KeyboardButton(group.name)] for group in groups]
        reply_markup = ReplyKeyboardWithCancel(keyboard, one_time_keyboard=True)
        bot.send_message(chat_id=update.message.chat_id,
                         text="Привет! Я MD-помошник. Буду вас записывать на занятия. "
                              "Записаться можно при наличии времени в расписании, написав мне \"запиши меня\". "
                              "И я предложу выбрать из тех дат, которые остались свободными. "
                              "Удалить запись можно написав мне \"Отпиши меня\" или \"Отмени запись\". "
                              "А сейчас представься, пожалуйста, чтобы я знал, кого я записываю на занятия. "
                              "Укажи номер своей группы.",
                         reply_markup=reply_markup)
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Я не нахожу активных групп. Нужно связаться с администратором.")
    return ASK_GROUP_NUM_STATE


def store_group_num(update, context):
    user_id = update.effective_user.id
    bot = context.bot
    group_name = update.message.text.strip().split()[0]
    if not group_name:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Я немного не понял. Просто напиши номер или название своей группы.")
        return ASK_GROUP_NUM_STATE

    try:
        group = Group.objects.get(name=group_name)
        User.objects.filter(pk=user_id).update(group=group.id)
    except:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Что-то пошло не так. Попробуй еще раз.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    bot.send_message(chat_id=update.message.chat_id,
                     text="Теперь напиши, пожалуйста, фамилию.")
    return ASK_LAST_NAME_STATE


def store_last_name(update, context):
    user_id = update.effective_user.id
    bot = context.bot
    last_name = update.message.text.strip()
    if not last_name:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Я немного не понял. Просто напиши свою фамилию.")
        return ASK_LAST_NAME_STATE
    User.objects.filter(pk=user_id).update(last_name=last_name)
    usr = User.objects.get(pk=user_id)
    bot.send_message(chat_id=update.message.chat_id,
                     text=f"Спасибо. Я тебя записал. Твоя фамилия {usr.last_name},"
                          f" и ты из группы {usr.group.name} правильно? Если нет,"
                          " то используй команду /start чтобы изменить данные о себе."
                          " Если всё верно, попробуй записаться. Напиши 'Запиши меня'.")
    return ConversationHandler.END


def ask_place(update, context):
    """Entry point for 'subscribe' user conversation"""
    user_id = update.effective_user.id
    bot = context.bot
    usr = User.objects.get(pk=user_id)
    signup_allowed = usr.group.allow_signup
    if not signup_allowed:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Сейчас запись на занятия закрыта для вашей группы.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    subs = TimeSlot.objects.filter(people__pk=usr.pk)
    if user_id not in LIST_OF_ADMINS and len(subs) > 1:
        bot.send_message(chat_id=update.message.chat_id,
                         text="У тебя уже есть две записи на эту неделю. Сначала отмени другую запись.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    places = Place.objects.filter(is_active=True)
    if not places:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Сейчас нету актуальных площадок для записи.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    keyboard = [[KeyboardButton(place.name)] for place in places]
    reply_markup = ReplyKeyboardWithCancel(keyboard, one_time_keyboard=True)
    bot.send_message(chat_id=update.message.chat_id,
                     text="На какую площадку хочешь?",
                     reply_markup=reply_markup)
    return ASK_PLACE_STATE


def ask_date(update, context, ):
    """Asks date to subscribe to

    Dates are offered starting from 'tomorrow'. Users are not allowed to edit
    their subscriptions for 'today' and earlier.
    """
    msg = update.message.text.strip()
    bot = context.bot
    if msg == "Отмена":
        bot.send_message(chat_id=update.message.chat_id,
                         text="Отменил. Попробуй заново.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    context.user_data['place'] = msg
    time_slots = TimeSlot.objects.filter(open=True,
                                         date__gt=dt.date.today(),
                                         place__name=msg).distinct('date')
    if not time_slots:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Нету открытых дат для записи.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    keyboard = [[
        InlineKeyboardButton("{} {}".format(WEEKDAYS_SHORT[time_slot.date.weekday()],
                                            time_slot.date),
                             callback_data=str(time_slot.date))
    ] for time_slot in time_slots]
    reply_markup = ReplyKeyboardWithCancel(keyboard, one_time_keyboard=True)
    bot.send_message(chat_id=update.message.chat_id,
                     text="На когда?",
                     reply_markup=reply_markup)
    return ASK_DATE_STATE


def ask_time(update, context):
    """Asks time to subscribe to

    Checks that the date given is not earlier than 'tomorrow'. Users are not
    allowed to edit their subscriptions for 'today' and earlier.
    """
    date = update.message.text.strip().split()[1]
    bot = context.bot
    if date == "Отмена":
        bot.send_message(chat_id=update.message.chat_id,
                         text="Отменил. Попробуй заново.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    try:
        # checks the actual date correctness
        date = dt.datetime.strptime(date, DATE_FORMAT).date()
    except ValueError:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Похоже, это была некорректная дата. Попробуй еще раз.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    if date <= dt.date.today():
        bot.send_message(chat_id=update.message.chat_id,
                         text="Нельзя записаться на уже зафиксированные даты (сегодня и ранее)."
                              "Можно записываться на 'завтра' и позже.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    # check for existing subscription for the date, 2 subs are not allowed per user per date
    user_id = update.effective_user.id
    subs = TimeSlot.objects.filter(people__pk=user_id, date=date)
    if user_id not in LIST_OF_ADMINS and len(subs) > 0:
        bot.send_message(chat_id=update.message.chat_id,
                         text="У тебя уже есть запись на {}. "
                              "Чтобы записаться отмени ранее сделанную запись.".format(date),
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    context.user_data['date'] = date.isoformat()
    place = context.user_data['place']
    time_slots = TimeSlot.objects.filter(date=date, place__name=place)
    keyboard = [[
        KeyboardButton(
            "{} (свободно слотов {})".format(time_slot.time.strftime("%H:%M"),
                                             time_slot.limit - time_slot.people.count()),
            callback_data=str(time_slot.time)
        )
    ] for time_slot in time_slots]
    reply_markup = ReplyKeyboardWithCancel(keyboard, one_time_keyboard=True)
    bot.send_message(chat_id=update.message.chat_id,
                     text="Теперь выбери время",
                     reply_markup=reply_markup)
    return ASK_TIME_STATE


def store_sign_up(update, context):
    msg = update.message.text.strip().split()[0]
    bot = context.bot
    if msg == "Отмена":
        bot.send_message(chat_id=update.message.chat_id,
                         text="Отменил. Попробуй заново.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    try:
        time = dt.datetime.strptime(msg, TIME_FORMAT).time()
    except ValueError:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Похоже, это было некорректное время. Попробуй еще раз.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    date = context.user_data['date']
    place = context.user_data['place']
    user_id = update.effective_user.id

    time_slot = TimeSlot.objects.get(date=date, place__name=place, time=time)

    if time_slot.people.count() == time_slot.limit:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Упс, на этот тайм слот уже записалось {} человек. "
                              "Попробуй записаться на другое время.".format(time_slot.limit))
    else:
        time_slot.people.add(User.objects.get(pk=user_id))
        # if time_slot.people.count() == time_slot.limit:
        #     time_slot.open = False
        time_slot.save()
        bot.send_message(chat_id=update.message.chat_id,
                         text="Ok, записал на {} {} {}".format(
                             place, date, time.strftime("%H:%M")),
                         reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def ask_unsubscribe(update, context):
    """Entry point for 'unsubscribe' user conversation

    Offer only subscriptions starting from 'tomorrow' for cancel.
    """
    user_id = update.effective_user.id
    user_subs = TimeSlot.objects.filter(people__id=user_id,
                                        date__gt=dt.date.today())
    bot = context.bot
    if user_subs:
        keyboard = [[
            InlineKeyboardButton("{} {} {}".format(user_sub.place.name,
                                                   user_sub.date,
                                                   user_sub.time.strftime("%H:%M")),
                                 callback_data=user_sub.pk)
        ] for user_sub in user_subs]
        reply_markup = ReplyKeyboardWithCancel(keyboard, one_time_keyboard=True)
        bot.send_message(chat_id=update.message.chat_id,
                         text="Какое отменяем?",
                         reply_markup=reply_markup)
        return RETURN_UNSUBSCRIBE_STATE
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Нечего отменять, у тебя нет записи на ближайшие занятия.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


def unsubscribe(update, context):
    """Handler for 'unsubscribe' command

    The command allows user to unsubscribe himself from a specificclass.
    Removes him from schedule. Check that the date given is not 'today'
    or earlier.
    """
    try:
        bot = context.bot
        msg = update.message.text.strip()
        if msg == "Отмена":
            bot.send_message(chat_id=update.message.chat_id,
                             text="Отменил. Попробуй заново.",
                             reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        place, date, time = msg.split()
        try:
            date = dt.datetime.strptime(date, DATE_FORMAT).date()
            time = dt.datetime.strptime(time, TIME_FORMAT).time()
        except ValueError:
            bot.send_message(chat_id=update.message.chat_id,
                             text="Похоже, это была некорректная дата или время."
                                  " Попробуй еще раз.",
                             reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if date <= dt.date.today():
            bot.send_message(chat_id=update.message.chat_id,
                             text="Нельзя отменять запись в день занятия.",
                             reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

        user_id = update.effective_user.id
        time_slot = TimeSlot.objects.get(date=date, place__name=place, time=time)
        time_slot.people.remove(User.objects.get(pk=user_id))
        bot.send_message(chat_id=update.message.chat_id,
                         text="Ok, удалил запись на {} {} {}".format(place, date, time),
                         reply_markup=ReplyKeyboardRemove())
    except:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Что-то пошло не так. Попробуй еще раз.",
                         reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
