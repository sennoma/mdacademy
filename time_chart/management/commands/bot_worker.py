"""Time chart bot documentation

Conversation:
 To ask bot to subscribe you to a classes write it: "З(з)апиши меня" starting
 with a capital or a lowercase letter. To ask bot to unsubscribe you from a class
 write: О[о]тпиши меня or О[о]тмени запись.
 Then follow it's instructions.
"""
from django.core.management.base import BaseCommand

from telegram import ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    PicklePersistence,
    RegexHandler,
    Updater
)

from time_chart.management.commands.config import (
    ASK_DATE_STATE,
    ASK_PLACE_STATE,
    ASK_TIME_STATE,
    ASK_GROUP_NUM_STATE,
    ASK_LAST_NAME_STATE,
    RETURN_UNSUBSCRIBE_STATE,
    BOT_TOKEN,
)
from time_chart.management.commands.tools import logger
from time_chart.management.commands.user_handlers import (
    start_cmd,
    store_group_num,
    store_last_name,
    ask_place,
    ask_date,
    ask_time,
    store_sign_up,
    ask_unsubscribe,
    unsubscribe,
)


def error(bot, update, error):
    """Log Errors caused by Updates."""
    bot.send_message(chat_id=update.message.chat_id, text="Произошла какая-то ошибка. Попробуй еще раз.")
    logger.warning('Update "%s" caused error "%s"', update, error)


def end_conversation(bot, update):
    user_id = update.effective_user.id
    logger.debug("User %s canceled the conversation.", user_id)
    bot.send_message(chat_id=update.message.chat_id,
                     text='Ок. На том и порешим пока.',
                     reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def unknown(bot, update):
    logger.info("User {} {} typed: {}".format(update.effective_user.id,
                                              update.effective_user.username,
                                              update.message.text))
    bot.send_message(chat_id=update.message.chat_id, text="Извини, не знаю такой команды.")


def run_bot():
    pp = PicklePersistence(filename='conversationbot')
    updater = Updater(token=BOT_TOKEN, use_context=True, persistence=pp)
    dispatcher = updater.dispatcher

    cancel_handler = CommandHandler('cancel', end_conversation)
    unknown_handler = MessageHandler(Filters.command, unknown)

    # Add user identity handler on /start command
    identity_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_cmd)],
        states={
            ASK_GROUP_NUM_STATE: [MessageHandler(Filters.text, store_group_num)],
            ASK_LAST_NAME_STATE: [MessageHandler(Filters.text, store_last_name)],
        },
        fallbacks=[CommandHandler('cancel', end_conversation)],
        name="identity_conversation",
        # persistent=True,
    )

    dispatcher.add_handler(identity_handler)
    dispatcher.add_handler(cancel_handler)
    dispatcher.add_handler(unknown_handler)

    # Add subscribe handler with the states ASK_DATE_STATE, ASK_TIME_STATE
    sign_up_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(".*([Зз]апиши меня).*"), ask_place)],
        states={
            ASK_PLACE_STATE: [MessageHandler(Filters.text, ask_date, pass_user_data=True)],
            ASK_DATE_STATE: [MessageHandler(Filters.text, ask_time, pass_user_data=True)],
            ASK_TIME_STATE: [MessageHandler(Filters.text, store_sign_up, pass_user_data=True)],
        },
        fallbacks=[CommandHandler('cancel', end_conversation)],
        name="subscribe_conversation",
        # persistent=True
    )
    dispatcher.add_handler(sign_up_conv_handler)

    # Add unsubscribe handler with the states
    unsubscribe_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(".*([Оо]тпиши меня|[Оо]тмени запись).*"), ask_unsubscribe)],
        states={
            RETURN_UNSUBSCRIBE_STATE: [MessageHandler(Filters.text, unsubscribe)],
        },
        fallbacks=[CommandHandler('cancel', end_conversation)],
        name="unsubscribe_conversation",
        # persistent=True
    )
    dispatcher.add_handler(unsubscribe_conv_handler)

    text_msg_handler = MessageHandler(Filters.text, unknown)
    dispatcher.add_handler(text_msg_handler)

    # log all errors
    dispatcher.add_error_handler(error)

    updater.start_polling(clean=True)

    updater.idle()


class Command(BaseCommand):
    help = 'Telegram bot worker'

    def handle(self, *args, **options):
        run_bot()
