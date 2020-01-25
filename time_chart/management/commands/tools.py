import logging
import re
from functools import wraps

from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)

from time_chart.management.commands.config import (
    LIST_OF_ADMINS,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# regex
date_regex = re.compile(".*([0-9]{4}-[0-9]{2}-[0-9]{2}).*")


def restricted(msg="Ага, счас! Только администратору можно!", returns=None):
    def restricted_deco(func):
        @wraps(func)
        def wrapper(bot, update, *args, **kwargs):
            user_id = update.effective_user.id
            if user_id not in LIST_OF_ADMINS:
                bot.send_message(chat_id=update.message.chat_id,
                                 text=msg,
                                 reply_markup=ReplyKeyboardRemove())
                return returns
            return func(bot, update, *args, **kwargs)
        return wrapper

    return restricted_deco


class ReplyKeyboardWithCancel(ReplyKeyboardMarkup):

    def __init__(self,
                 keyboard,
                 resize_keyboard=False,
                 one_time_keyboard=False,
                 selective=False,
                 **kwargs):
        keyboard.append([KeyboardButton("Отмена")])
        super(ReplyKeyboardWithCancel, self).__init__(
            keyboard,
            resize_keyboard=resize_keyboard,
            one_time_keyboard=one_time_keyboard,
            selective=selective,
            **kwargs
        )
