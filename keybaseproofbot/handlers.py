import argparse
import json
import logging
import os
import re

from telegram.ext import ConversationHandler
from telegram import Emoji

from keybaseproofbot.proof_handler import check_proof_message, lookup_proof, store_proof
from keybaseproofbot.wrapperfilter import filter_group, filter_private


@filter_group
def proof_message_handle(bot, update):
    if update.message.from_user.username == '':
        logging.info("User (%s) without username sent message.",
                     update.message.from_user.first_name)
        return

    entities = [
        entity for entity in update.message.entities if entity.type == 'pre'
    ]
    if len(entities) != 2:
        logging.warning(
            "Message with message id %s from sender %s does not have two pre blocks.",
            update.message.message_id, update.message.from_user.username)
        return

    succes, proof = check_proof_message(bot, update, entities)
    if succes:
        signed_block = update.message.text[entities[1].offset:entities[1]
                                                .offset + entities[1].length]
        store_proof(proof, signed_block, update)
        bot.sendMessage(
            chat_id=update.message.chat_id,
            text="Your proof was succesfully stored!", 
            reply_to_message_id=update.message.message_id)
    elif proof == 'invalid_sign':
        bot.sendMessage(
            chat_id=update.message.chat_id,
            text="Your proof is not valid. Paging @pingiun to take a look at it.",
            reply_to_message_id=update.message.message_id)
    elif proof == 'notimplemented':
        bot.sendMessage(
            chat_id=update.message.chat_id,
            text="Using other hosts than keybase.io is not supported yet.")


@filter_group
def other_message_handle(bot, update):
    bot.kickChatMember(
        chat_id=update.message.chat_id, user_id=update.message.from_user.id)


@filter_private
def start(bot, update):
    bot.sendMessage(
        chat_id=update.message.chat_id,
        text="Hello, welcome to the (unofficial) Keybase Telegram Proving Bot. "
        "I can help you search for Telegram user proofs. Please read this"
        " webpage for instructions on how to prove yourself: "
        "https://pingiun/post/telegram-proof\n\nYou can control me by sending "
        "these commands:\n\n"
        "/lookup - check if a user has proved their identity on Telegram\n"
        "/cancel - cancel the current command")


@filter_private
def notusername(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id,
        text="Please enter a username like @pingiun, or /cancel to cancel "
        "the current command.")


@filter_private
def cancel(bot, update):
    bot.sendMessage(
        chat_id=update.message.chat_id,
        text="Canceled current command.")
    return ConversationHandler.END


@filter_private
def lookup_start(bot, update, args=None):
    if len(args) == 1:
        if re.match(r'^@([A-Za-z_]+)$', args[0]):
            update.message.text = args[0]
            return lookup_username(bot, update)
    else:
        bot.sendMessage(chat_id=update.message.chat_id,
            text="Please enter a username (with @) to search for.")
        return 'enter_username'


@filter_private
def lookup_username(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id, text="Identifying " + update.message.text)
    bot.sendChatAction(chat_id=update.message.chat_id, action='typing')
    info = lookup_proof(bot, telegram_username=update.message.text[1:])
    if info:
        proof_object = json.loads(info.proof_object)
        fingerprint = ' '.join([proof_object['body']['key']['fingerprint'][i:i+4].upper() for i in range(0, len(proof_object['body']['key']['fingerprint']), 4)])
        bot.sendMessage(chat_id=update.message.chat_id, text=Emoji.HEAVY_CHECK_MARK + " public key fingerprint: " + fingerprint)
        bot.sendMessage(chat_id=update.message.chat_id, text="Verification message:")
        bot.forwardMessage(chat_id=update.message.chat_id, from_chat_id=info.chat_id, message_id=info.message_id)
    else:
        bot.sendMessage(chat_id=update.message.chat_id, text="No proof found.")
    return ConversationHandler.END