from telegram import (
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import ConversationHandler

from time_chart.models import Group, User

from time_chart.management.commands.config import (
    ASK_GROUP_NUM_STATE,
    ASK_LAST_NAME_STATE,
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

    groups = Group.objects.filter(active=True).only('name')
    if groups:
        keyboard = [[KeyboardButton(group.name, callback_data=group.name)] for group in groups]
        reply_markup = ReplyKeyboardWithCancel(keyboard)
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
    msg = update.message.text.strip().split()[0]
    try:
        group_name = msg

        if not group_name:
            bot.send_message(chat_id=update.message.chat_id,
                             text="Я немного не понял. Просто напиши номер или название своей группы.")
            return ASK_GROUP_NUM_STATE

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
    import ipdb
    ipdb.set_trace()
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
