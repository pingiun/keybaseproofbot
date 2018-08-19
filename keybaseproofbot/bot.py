import logging
from telegram.ext import CommandHandler, ConversationHandler, Filters, InlineQueryHandler, MessageHandler, Updater

from keybaseproofbot import handlers
from keybaseproofbot.config import config
from keybaseproofbot.database import init_db
from keybaseproofbot.filters import CustomFilter

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
    username_regex = MessageHandler(None, handlers.lookup_username)
    cancel_command = CommandHandler('cancel', handlers.cancel)
    lookup_conversation = ConversationHandler(
        [lookup_command], {'enter_username': [username_regex]},
        [cancel_command])

    dispatcher.add_handler(lookup_conversation)

    forwardproof_command = CommandHandler(
        'forwardproof', handlers.forward_proof_start, pass_args=True)
    forwardproof = MessageHandler(None, handlers.forward_proof)
    forwardproof_conversation = ConversationHandler(
        [forwardproof_command], {'enter_username': [forwardproof]},
        [cancel_command])

    dispatcher.add_handler(forwardproof_conversation)

    newproof_command = CommandHandler(
        'newproof', handlers.newproof, pass_args=True)
    kbusername_handler = MessageHandler(None, handlers.make_json)
    signed_block_regex = MessageHandler(None, handlers.check_block)
    newproof_conversation = ConversationHandler([newproof_command], {
        'enter_kbusername': [kbusername_handler],
        'sign_block': [signed_block_regex]
    }, [cancel_command])
    dispatcher.add_handler(newproof_conversation)

    # Inline handler:
    inline_handler = InlineQueryHandler(handlers.inline_handler)
    dispatcher.add_handler(inline_handler)

    # Group handlers:
    proofmsg_handler = MessageHandler(
        CustomFilter.supergrouptext,
        handlers.proof_message_handle,
        edited_updates=True)
    dispatcher.add_handler(proofmsg_handler)
    othermsg_handler = MessageHandler(
        Filters.audio | Filters.contact | Filters.document | Filters.location |
        Filters.photo | Filters.sticker | Filters.venue | Filters.video |
        Filters.voice, handlers.other_message_handle)
    dispatcher.add_handler(othermsg_handler)

    dispatcher.add_error_handler(
        lambda bot, update, error: logging.error(error))

    updater.start_polling()
