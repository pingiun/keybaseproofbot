import time

import json
import logging
import re
import requests
from telegram import InlineQueryResultArticle, InputTextMessageContent, ParseMode
from telegram.ext import ConversationHandler

from keybaseproofbot.models import Proof
from keybaseproofbot.proof_handler import check_proof_message, lookup_proof, store_proof, check_key
from keybaseproofbot.utils import fix_dashes
from keybaseproofbot.wrapperfilter import filter_group, filter_private


@filter_group
def proof_message_handle(bot, update):
    if update.message.from_user.username == '':
        logging.info("User (%s) without username sent message.",
                     update.message.from_user.first_name)
        return

    entities = [
        entity for entity in update.message.entities if entity.type == 'pre' or entity.type == 'code'
    ]
    if len(entities) != 2:
        logging.warning(
            "Message with message id %s from sender %s does not have two pre blocks.",
            update.message.message_id, update.message.from_user.username)
        bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
        return

    succes, proof = check_proof_message(bot, update, entities)
    if succes:
        signed_block = update.message.text[entities[1].offset:entities[1]
                                                                  .offset + entities[1].length]
        store_proof(proof, signed_block, update)
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Your proof was succesfully stored!",
            reply_to_message_id=update.message.message_id)
    elif proof == 'invalid_sign':
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Your proof is not valid. Paging @pingiun to take a look at it.",
            reply_to_message_id=update.message.message_id)
        bot.deleteMessage(chat_id=update.message.chat_id, message_id=update.message.id)
    elif proof == 'notimplemented':
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Using other hosts than keybase.io is not supported yet.")
        bot.deleteMessage(chat_id=update.message.chat_id, message_id=update.message.id)


@filter_group
def other_message_handle(bot, update):
    bot.deleteMessage(
        chat_id=update.message.chat_id, message_id=update.message.id)


def inline_handler(bot, update):
    query = update.inline_query.query

    proofs = Proof.query.filter(
        Proof.telegram_username.like("%{}%".format(query))).all()
    results = [
        InlineQueryResultArticle(
            id=proof.telegram_username,
            title=proof.telegram_username,
            input_message_content=InputTextMessageContent(
                "✅ https://keybase.io/{} is @{} on Telegram (cached). You can talk to @KeybaseProofBot for current information, or check out @KeybaseProofs.".format(
                    proof.keybase_username, proof.telegram_username))) for proof in proofs
    ]

    update.inline_query.answer(results)


@filter_private
def start(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text="Hello, welcome to the (unofficial) Keybase Telegram Proving Bot. "
             "I can help you search for Telegram user proofs.\n"
             "*Please keep in mind that this bot is unofficial, which means that your telegram proof "
             "is not included in your signature chain. Revocations are also not implemented (yet).*\n\n"
             "You can control me with these commands:\n\n"
             "/newproof - build a proof message to post in @KeybaseProofs\n"
             "/lookup - check if a user has proved their identity on Telegram\n"
             "/forwardproof - the bot forwards the proof message for a certain Telegram user\n"
             "/cancel - cancel the current command",
        parse_mode=ParseMode.MARKDOWN)


@filter_private
def notusername(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id,
        text="Please enter a username like @pingiun, or /cancel to cancel "
             "the current command.")


@filter_private
def notkbusername(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id, text="Please enter a correct input.")


@filter_private
def cancel(bot, update):
    bot.send_message(
        chat_id=update.message.chat_id, text="Canceled current command.")
    return ConversationHandler.END


@filter_private
def newproof(bot, update, args):
    if not update.message.from_user.username:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="You need to have a username to prove it!")
    if len(args) == 1:
        update.message.text = args[0]
        return make_json(bot, update)

    bot.send_message(
        chat_id=update.message.chat_id,
        text="Please enter a keybase username to connect to your Telegram account."
    )
    return 'enter_kbusername'


temp_proof_data = {}


@filter_private
def make_json(bot, update):
    match = re.match(r'^(?:(?:(?:https://)?keybase.io/)|@)?([A-Za-z_]+)$',
                     update.message.text)
    if not match:
        return notkbusername(bot, update)
    username = match.group(0)

    r = requests.get(
        'https://keybase.io/_/api/1.0/user/lookup.json?usernames={}&fields=basics,public_keys'.format(username))
    try:
        keybase = r.json()
    except json.decoder.JSONDecodeError as e:
        logging.exception(e)
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Something went wrong while looking up your username.")
        return ConversationHandler.END

    try:
        fingerprint = keybase['them'][0]['public_keys']['primary'][
            'key_fingerprint']
        host = 'keybase.io'
        key_id = fingerprint[:-16]
        kid = keybase['them'][0]['public_keys']['primary']['kid']
        uid = keybase['them'][0]['id']
        username = keybase['them'][0]['basics']['username']
    except KeyError:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Your username was not found on Keybase!")
        return

    try:
        data = {
            'body': {
                'key': {
                    'fingerprint': fingerprint,
                    'host': host,
                    'key_id': key_id,
                    'kid': kid,
                    'uid': uid,
                    'username': username,
                },
                'service': {
                    'name': 'telegram',
                    'username': update.message.from_user.username,
                },
                'type': 'web_service_binding',
                'version': 1,
            },
            'ctime': int(time.time()),
            'expire_in': 60 * 60 * 24 * 365 * 1,  # Expire in 1 year
            'tag': 'signature'
        }
        temp_proof_data[update.message.chat_id] = data
        json_block = json.dumps(data, indent=4)
    except Exception as e:
        logging.exception(e)
        bot.send_message(
            chat_id=update.message.chat_id, text="Something went wrong!")
        return

    bot.send_message(chat_id=update.message.chat_id,
                    text="Okay, please paste the following into your terminal (where you can use the keybase cli client) and paste the output here.")
    bot.send_message(
        chat_id=update.message.chat_id,
        text="```\nkeybase pgp sign --message \"{}\"\n```".format(json_block.replace(r'"', r'\"')),
        parse_mode=ParseMode.MARKDOWN)

    bot.send_message(chat_id=update.message.chat_id,
                     text="If want to use gpg(2) you can copy and paste this command instead:")
    bot.send_message(chat_id=update.message.chat_id,
                     text="```\necho \"{}\" | gpg -a --sign\n```".format(json_block.replace(r'"', r'\"')),
                     parse_mode=ParseMode.MARKDOWN)

    return 'sign_block'


@filter_private
def check_block(bot, update):
    if update.message.text.startswith('/cancel'):
        return cancel()

    lines = update.message.text.split('\n')
    if len(lines) > 1 and not ("BEGIN PGP MESSAGE" in lines[0] and "END PGP MESSAGE" in lines[-1]):
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Your message is not a valid gpg message.")
        return ConversationHandler.END
    del lines

    pgp_content = fix_dashes(update.message.text)

    proof_data = temp_proof_data[update.message.chat_id]

    # See mom, i clean up after myself:
    del temp_proof_data[update.message.chat_id]

    fingerprint = ' '.join([
        proof_data['body']['key']['fingerprint'][i:i + 4].upper()
        for i in range(0, len(proof_data['body']['key']['fingerprint']), 4)
    ])
    succes, proof = check_key(bot, proof_data, pgp_content,
                              update.message.from_user.username,
                              update.message.chat_id)

    if succes:
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Your signed block is valid. You can now copy and paste the following "
                 "message to @KeybaseProofs.")
        bot.send_message(chat_id=update.message.chat_id,
                        text="Keybase proof\n\n"
                             "I hereby claim:\n\n"
                             "- I am @{} on telegram.\n"
                             "- I am {} on keybase.\n"
                             "- I have a public key whose fingerprint is {}\n\n"
                             "To claim this, I am signing this object:\n"
                             "```\n{}\n```\n"
                             "with the key from above, yielding:\n"
                             "```\n{}\n```\n"
                             "Finally, I am proving my Telegram account by posting it in @KeybaseProofs"
                        .format(update.message.from_user.username,
                                proof_data['body']['key']['username'],
                                fingerprint,
                                json.dumps(
                                    proof_data, sort_keys=True, indent=4),
                                pgp_content))
    elif proof == 'invalid_sign':
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Your signed block is not valid.",
            reply_to_message_id=update.message.message_id)
    elif proof == 'notimplemented':
        bot.send_message(
            chat_id=update.message.chat_id,
            text="Using other hosts than keybase.io is not supported yet.")
    else:
        logging.error("Unhandled check_proof result: " + proof)


@filter_private
def lookup_start(bot, update, args):
    if len(args) >= 1:
        update.message.text = ' '.join(args)
        return lookup_username(bot, update)

    bot.send_message(
        chat_id=update.message.chat_id,
        text="Please enter a query to search for.")
    return 'enter_username'


@filter_private
def lookup_username(bot, update):
    bot.send_chat_action(chat_id=update.message.chat_id, action='typing')
    info = lookup_proof(bot, query=update.message.text)

    if info:
        proof_object = json.loads(info.proof_object)
        fingerprint = ' '.join([
            proof_object['body']['key']['fingerprint'][i:i + 4].upper()
            for i in range(0,
                           len(proof_object['body']['key']['fingerprint']), 4)
        ])
        bot.send_message(
            chat_id=update.message.chat_id,
            text="▶ Identifying https://keybase.io/{}".format(info.keybase_username))
        bot.send_message(
            chat_id=update.message.chat_id,
            text="✅ public key fingerprint: " +
                 fingerprint)
        bot.send_chat_action(chat_id=update.message.chat_id, action='typing')
        succes, proof = check_key(bot,
                                  json.loads(info.proof_object), info.signed_block,
                                  info.telegram_username, info.user_id)
        if succes == 'no_expiry':
            bot.send_message(chat_id=update.message.chat_id,
                             text="😕 \"@{}\" on telegram. "
                                  "But the proof has no expiry set, so be careful.".format(info.telegram_username))
        elif succes:
            bot.send_message(
                chat_id=update.message.chat_id,
                text="✅ \"@{}\" on telegram".format(info.telegram_username))
        else:
            if proof == 'not_username':
                bot.send_message(chat_id=update.message.chat_id,
                                 text="❌ WARNING: \"{}\" on telegram may have deleted their account, or changed their username. "
                                      "The user may not be who they claim they are!".format(info.telegram_username))
            elif proof == 'invalid_sign':
                bot.send_message(chat_id=update.message.chat_id,
                                 text="❌ WARNING: \"{}\" on telegram has not signed their proof correctly. "
                                      "The user may not be who they claim they are!".format(info.telegram_username))
            elif proof == 'malformed':
                bot.send_message(chat_id=update.message.chat_id,
                                 text="❌ WARNING: \"{}\" has a malformed proof, it could not be verified.".format(info.telegram_username))
            elif proof == 'expired':
                bot.send_message(chat_id=update.message.chat_id,
                                 text="❌ WARNING: \"{}\" has let their proof expire. It cannot be trusted anymore. "
                                      "The user may not be who they claim they are!".format(info.telegram_username))
            else:
                bot.send_message(chat_id=update.message.chat_id,
                                 text="Could not verify Telegram username, you are advised to check for yourself. (Internal error)")

                logging.error("Check proof failed for lookup. Return message: %s", proof)
        bot.send_message(
            chat_id=update.message.chat_id,
            text="▶ If you want to check the proof message yourself, use the /forwardproof command."
        )
    else:
        bot.send_message(chat_id=update.message.chat_id, text="No proof found for your query.")
    return ConversationHandler.END


@filter_private
def forward_proof_start(bot, update, args):
    if len(args) >= 1:
        update.message.text = ' '.join(args)
        return forward_proof(bot, update)

    bot.send_message(
        chat_id=update.message.chat_id,
        text="Please enter a username to search for.")
    return 'enter_username'


@filter_private
def forward_proof(bot, update):
    match = re.match(r'(?:@)?([A-Za-z_]+)', update.message.text)
    if match:
        info = lookup_proof(bot, telegram_username=match.group(0))
        if info:
            bot.send_message(chat_id=update.message.chat_id, text="This is the proof message for that user:")
            bot.forwardMessage(chat_id=update.message.chat_id, from_chat_id=info.chat_id, message_id=info.message_id)
        else:
            bot.send_message(chat_id=update.message.chat_id, text="No proof found for your query.")
        return ConversationHandler.END
    else:
        bot.send_message(chat_id=update.message.chat_id,
                        text="That is not a valid Telegram username, try again.")
