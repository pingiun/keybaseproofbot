import logging

from telegram.ext import CommandHandler, ConversationHandler, Filters, InlineQueryHandler, MessageHandler, RegexHandler, Updater

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
    help_handler = CommandHandler('help', handlers.start)
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(help_handler)

    lookup_command = CommandHandler(
        'lookup', handlers.lookup_start, pass_args=True)
    username_regex = MessageHandler([], handlers.lookup_username)
    cancel_command = CommandHandler('cancel', handlers.cancel)
    notusername = MessageHandler([], handlers.notusername)
    lookup_conversation = ConversationHandler(
        [lookup_command], {'enter_kbusername': [username_regex]},
        [cancel_command, notusername])

    dispatcher.add_handler(lookup_conversation)

    newproof_command = CommandHandler(
        'newproof', handlers.newproof, pass_args=True)
    kbusername_handler = MessageHandler([], handlers.make_json)
    signed_block_regex = MessageHandler([], handlers.check_block)
    notkbusername = MessageHandler([], handlers.notkbusername)
    newproof_conversation = ConversationHandler([newproof_command], {
        'enter_kbusername': [kbusername_handler],
        'sign_block': [signed_block_regex]
    }, [cancel_command, notkbusername])
    dispatcher.add_handler(newproof_conversation)

    # Inline handler:
    inline_handler = InlineQueryHandler(handlers.inline_handler)
    dispatcher.add_handler(inline_handler)

    # Group handlers:
    proofmsg_handler = MessageHandler(
        [CustomFilter.supergrouptext],
        handlers.proof_message_handle,
        allow_edited=True)
    dispatcher.add_handler(proofmsg_handler)
    othermsg_handler = MessageHandler([
        Filters.audio, Filters.contact, Filters.document, Filters.location,
        Filters.photo, Filters.sticker, Filters.venue, Filters.video,
        Filters.voice
    ], handlers.other_message_handle)
    dispatcher.add_handler(othermsg_handler)

    updater.start_polling()
