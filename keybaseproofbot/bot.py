import logging

from telegram.ext import CommandHandler, ConversationHandler, Filters, InlineHanderl, MessageHandler, RegexHandler, Updater

from keybaseproofbot.database import db_session, init_db
from keybaseproofbot import handlers
from keybaseproofbot.filters import CustomFilter
from keybaseproofbot.config import config

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)

def main():
    init_db()
    updater = Updater(token=config['TG_TOKEN'])
    dispatcher = updater.dispatcher

    # Private handlers:
    start_handler = CommandHandler('start', handlers.start)
    dispatcher.add_handler(start_handler)

    lookup_command = CommandHandler('lookup', handlers.lookup_start, pass_args=True)
    username_regex = RegexHandler(r'^@([A-Za-z_]+)$', handlers.lookup_username)
    cancel_command = CommandHandler('cancel', handlers.cancel)
    notusername = MessageHandler([], handlers.notusername)
    lookup_conversation = ConversationHandler([lookup_command], {'enter_username': [username_regex]}, [cancel_command, notusername])

    dispatcher.add_handler(lookup_conversation)

    # Inline handler:
    inline_handler = InlineHandler(handlers.inline_handler)
    dispatcher.add_handler(inline_handler)

    # Group handlers:
    proofmsg_handler = MessageHandler(
        [CustomFilter.supergrouptext], handlers.proof_message_handle, allow_edited=True)
    dispatcher.add_handler(proofmsg_handler)
    othermsg_handler = MessageHandler(
        [Filters.audio, Filters.contact, Filters.document, Filters.location,
         Filters.photo, Filters.sticker, Filters.venue, Filters.video,
         Filters.voice], handlers.other_message_handle)
    dispatcher.add_handler(othermsg_handler)

    updater.start_polling()
