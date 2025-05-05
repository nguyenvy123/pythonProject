from telegram import Update, Bot
from telegram.ext import Updater, MessageHandler, Filters

BOT_TOKEN = "7696186849:AAHUow8NJaYAkR1Zyminds-Sh5juF0MLY2U"  # Thay token của bạn vào đây

def get_chat_id(update: Update, context):
    print(f"Group Chat ID: {update.effective_chat.id}")

updater = Updater(token=BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(MessageHandler(Filters.all, get_chat_id))

updater.start_polling()
updater.idle()