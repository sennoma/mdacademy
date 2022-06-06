import datetime as dt

from django.db.models import Count, F, Q
from telegram import (
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardButton,
)
from telegram.ext import ConversationHandler
from telegram.parsemode import ParseMode

from time_chart.models import Group, User, Place, TimeSlot

from time_chart.management.commands.config import (
    ACCEPT_TERMS_STATE,
    ASK_GROUP_NUM_STATE,
    ASK_LAST_NAME_STATE,
    ASK_PLACE_STATE,
    ASK_DATE_STATE,
    ASK_TIME_STATE,
    LIST_OF_ADMINS,
    WEEKDAYS_SHORT,
    DATE_FORMAT,
    TIME_FORMAT,
    RETURN_UNSUBSCRIBE_STATE,
)
from time_chart.management.commands.tools import (
    logger,
    ReplyKeyboardWithCancel
)


def is_past_19():
    """Is current time past 19:00 (UTC+3)"""
    if dt.datetime.utcnow().time().hour >= 16:
        return True
    return False


# commands
def start_cmd(update, context):
    bot = context.bot
    user_id = update.effective_user.id
    nick = update.effective_user.username or ""
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    usr, _ = User.objects.get_or_create(id=user_id)
    usr.bot_chat_id = update.message.chat_id
    if nick:
        usr.nick_name = nick or ""
    if first_name:
        usr.first_name = first_name or ""
    if last_name:
        usr.last_name = last_name or ""
    usr.save()

    bot.send_message(chat_id=update.message.chat_id,
                     text="Привет! Я MD-помощник и я буду записывать тебя на занятия. "
                          "Я понимаю только слова-команды, поэтому прочитай внимательно всю инструкцию ниже. "
                          "Она останется в нашей переписке и ты в любой момент сможешь вернуться "
                          "в начало нашего диалога и перечитать, если что-то забыл. "
                          "Записаться можно при наличии времени в расписании, написав мне \"Запиши меня\". "
                          "И я предложу выбрать из тех дат, которые остались свободными. "
                          "Удалить запись можно написав мне \"Отпиши меня\" или \"Отмени запись\". "
                          "Если остались вопросы, напиши @MotoDrugAcademy личное сообщение. Если нет, "
                          "то подтверди, что ты всё прочитал и понял командой _Принимаю_",
                         parse_mode=ParseMode.MARKDOWN)

    return ACCEPT_TERMS_STATE


def accept_terms(update, context):
    bot = context.bot
    accept = update.message.text.strip()
    if "принимаю" not in accept.lower():
        bot.send_message(chat_id=update.message.chat_id,
                         text="Я немного не понял. Так ты принимаешь условия? Если принимаешь, то напиши мне"
                              " _Принимаю_.",
                         parse_mode=ParseMode.MARKDOWN)
        return ACCEPT_TERMS_STATE

    groups = Group.objects.filter(is_active=True).only('name')
    if groups:
        keyboard = [[KeyboardButton(group.name)] for group in groups]
        reply_markup = ReplyKeyboardWithCancel(keyboard, one_time_keyboard=True)
        bot.send_message(chat_id=update.message.chat_id,
                         text="Спасибо! Двигаемся дальше. Укажи, пожалуйста, номер твоей группы.",
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
                         text="Я немного не понял. Просто нажми кнопку с названием твоей группы на клавиатуре."
                              "Если клавиатуры нет, может она спраталась. Попробуй поискать кнопочку рядом со "
                              "строкой ввода.")
        return ASK_GROUP_NUM_STATE

    try:
        group = Group.objects.get(name=group_name)
        User.objects.filter(pk=user_id).update(group=group.id)
    except Exception as e:
        logger.error('Update "%s" caused error "%s"', update, e)
        bot.send_message(chat_id=update.message.chat_id,
                         text="Что-то пошло не так. Попробуй еще раз.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    bot.send_message(chat_id=update.message.chat_id,
                     text="Теперь напиши, пожалуйста, фамилию.",
                     reply_markup=ReplyKeyboardRemove())
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
                     text=f"Твоя фамилия {usr.last_name} и ты из группы {usr.group.name}, "
                          f"верно? Если нет, нажми /start и измени данные. Если все верно, то попробуй написать мне"
                          f" первую команду: _запиши меня_. Напоминаю, "
                          f"что я тебя уже запомнил и заново вводить свою фамилию больше не понадобится.",
                     parse_mode=ParseMode.MARKDOWN)
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

    if not usr.is_active:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Для вас запись закрыта. Обратитесь к администратору.",
                         reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    today = dt.date.today()
    if today.weekday() == 6:  # 6 == sunday
        start_of_the_week = today + dt.timedelta(days=1)
    else:
        start_of_the_week = today - dt.timedelta(days=today.weekday())
    subs = TimeSlot.objects.filter(people__pk=usr.pk,
                                   date__gte=start_of_the_week)
    if user_id not in LIST_OF_ADMINS and len(subs) >= usr.group.week_limit:
        bot.send_message(chat_id=update.message.chat_id,
                         text="У тебя уже достигнут лимит записей на эту неделю. "
                              "Сначала отмени другую запись.",
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


def ask_date(update, context):
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
    start_date = dt.date.today()
    if is_past_19():
        start_date = dt.date.today() + dt.timedelta(days=1)
    user_id = update.effective_user.id
    usr = User.objects.get(pk=user_id)
    qs = TimeSlot.objects.annotate(people_count=Count('people')).filter(
        Q(allowed_groups=usr.group) | Q(allowed_groups__isnull=True),
        open=True,
        date__gt=start_date,
        place__name=msg,
        limit__gt=F('people_count')
    ).order_by('date')
    time_slots = {}
    for ts in qs:
        time_slots[ts.date] = ts
    time_slots = time_slots.values()
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
    bot = context.bot
    res = update.message.text.strip().split()
    if len(res) > 1:
        _, date = res[:2]
    elif res[0] == "Отмена":
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
    context.user_data['date'] = date
    place = context.user_data['place']
    user_id = update.effective_user.id
    usr = User.objects.get(pk=user_id)
    qs = TimeSlot.objects.annotate(people_count=Count('people')).filter(
        Q(allowed_groups=usr.group) | Q(allowed_groups__isnull=True),
        date=date,
        place__name=place,
        open=True,
        limit__gt=F('people_count')
    ).order_by('time')
    time_slots = {}
    for ts in qs:
        time_slots[ts.time] = ts
    time_slots = time_slots.values()
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

    if not time_slot.open:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Упс, этот тайм слот закрыт для записи в данный момент. "
                              "Попробуй записаться на другое время или узнай у "
                              "администратора когда будет открыта запись на этот.".format(time_slot.limit))
    if time_slot.people.count() >= time_slot.limit:
        bot.send_message(chat_id=update.message.chat_id,
                         text="Упс, на этот тайм слот уже записалось {} человек. "
                              "Попробуй записаться на другое время.".format(time_slot.people.count()))
    elif date == (dt.date.today() + dt.timedelta(days=1)) and is_past_19():
        bot.send_message(chat_id=update.message.chat_id,
                         text="Не получилось записать. Запись на 'завтра' можно совершить до 19:00. "
                              "Попробуй записаться на другую дату.".format(time_slot.limit))
    else:
        user = User.objects.get(pk=user_id)
        time_slot.people.add(user)
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
    bot = context.bot
    try:
        msg = update.message.text.strip()
        if msg == "Отмена":
            bot.send_message(chat_id=update.message.chat_id,
                             text="Отменил. Попробуй заново.",
                             reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        res = msg.split()
        if len(res) == 3:
            place, date, time = res
        elif len(res) > 3:
            place, date, time = ' '.join(res[:-2]), res[-2], res[-1]
        else:
            bot.send_message(chat_id=update.message.chat_id,
                             text="Что-то пошло не так. Попробуй еще раз.",
                             reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
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
        if date == (dt.date.today() + dt.timedelta(days=1)) and is_past_19():
            bot.send_message(chat_id=update.message.chat_id,
                             text="Нельзя отменять запись на завтра после 19:00. Напиши администратору.",
                             reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END

        user_id = update.effective_user.id
        time_slot = TimeSlot.objects.get(date=date, place__name=place, time=time)
        time_slot.people.remove(User.objects.get(pk=user_id))
        bot.send_message(chat_id=update.message.chat_id,
                         text="Ok, удалил запись на {} {} {}".format(place, date, time),
                         reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logger.error('Update "%s" caused error "%s"', update, e)
        bot.send_message(chat_id=update.message.chat_id,
                         text="Что-то пошло не так. Попробуй еще раз.",
                         reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
