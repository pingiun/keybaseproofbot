import json
import logging
import re

import gnupg
import requests

from sqlalchemy import or_

from keybaseproofbot.database import db_session
from keybaseproofbot.models import Proof


def check_proof_message(bot, update, entities):
    username = update.message.from_user.username

    # Load the json object from the message
    try:
        keyobject = json.loads(update.message.text[entities[0].offset:entities[
            0].offset + entities[0].length])
    except json.decoder.JSONDecodeError:
        logging.warning(
            "Message with message id %s from sender %s does not have a valid json block.",
            update.message_id, username)
        return (False, None)

    return check_key(bot, keyobject,
                     update.message.text[entities[1].offset:entities[1]
                                         .offset + entities[1].length],
                     username, update.message.from_user.id)


def check_key(bot, proof_object, signed_block, username, user_id):
    try:
        chat = bot.getChat(user_id)
        if chat['username'] != username:
            return (False, 'not_username')
    except TelegramError as e:
        return (False, 'not_username')

    # Check if username in JSON object is the same as sending username and
    # get the keybase.io username from JSON object
    try:
        if proof_object['body']['service'][
                'name'] != 'telegram' or proof_object['body']['service'][
                    'username'] != username:
            logging.warning(
                "Proof with user id %s with username %s does not contain the right username.",
                user_id, username)
            return (False, 'not_username')

        if proof_object['body']['key']['host'] == 'keybase.io':
            keybaseusername = proof_object['body']['key']['username']
        else:
            raise NotImplementedError

        assert (len(proof_object['body']['key']['fingerprint']) == 40)
        assert (int(proof_object['body']['key']['fingerprint'], 16))
    except (KeyError, AssertionError, ValueError):
        logging.warning(
            "Proof with user id %s with username %s does not have the required fields.",
            user_id, username)
        return (False, None)
    except NotImplementedError:
        return (False, 'notimplemented')

    # Load the key from keybase, and import in GPG
    try:
        r = requests.get('https://keybase.io/{}/key.asc'.format(
            keybaseusername))
        gpg = gnupg.GPG(gnupghome='./keys',
                        keyring='pubring.gpg',
                        secret_keyring='secring.gpg')
        gpg.import_keys(r.text)
    except Exception as e:
        # TODO: Reageer goed op verschillende keybase errors
        raise e

    decrypted = gpg.decrypt(signed_block)

    # Check if the decrypted message is the same as the JSON object.
    try:
        if json.loads(str(decrypted)) == proof_object:
            logging.info("Succesfully checked %ss proof", username)
            return (True, proof_object)
        else:
            logging.warning(
                "JSON object is not the same as decrypted message.\nJSON object:\n{}\nDecrypted message:\n{}".
                format(json.dumps(proof_object), decrypted))
            return (False, 'invalid_sign')
    except json.decoder.JSONDecodeError:
        logging.warning("Decoded message is not a valid JSON object")


regexes = {
    'keybase': re.compile(r'^(?:keybase=)?(?:(?:(?:https:\/\/)?keybase.io\/)|@)?([A-Za-z_]+)$'),
    'telegram': re.compile(r'^(?:telegram=(?:@)?)?([A-Za-z_]+)$'),
    'email': re.compile(r'^email=([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)$'),
    'github': re.compile(r'^github=([A-Za-z_][a-zA-Z0-9_-]+)$'),
    'twitter': re.compile(r'^twitter=(?:@)?([A-Za-z_][a-zA-Z0-9-_]+)$'),
    'reddit': re.compile(r'^reddit=(?:(?:/)?u/)?([A-Za-z_][a-zA-Z0-9-]+)$'),
    'hackernews': re.compile(r'^hackernews=([A-Za-z_][a-zA-Z0-9_-]+)$'),
    'coinbase': re.compile(r'^coinbase=([A-Za-z_][a-zA-Z0-9_-]+)$'),
    'key_fingerprint': re.compile(r'fingerprint=[A-Fa-f0-9]{40}')
}

def lookup_proof(bot, query=None, telegram_username='%'):
    keybase_username = '%'
    if telegram_username == '%':
        searchvalues = dict()

        for word in query.split():
            for name, regex in regexes.items():
                match = regex.match(word)
                if match:
                    if name == 'telegram':
                        telegram_username = match.group(1)
                    elif name == 'keybase':
                        keybase_username = match.group(1)
                    elif name == 'email':
                        pass
                    else:
                        searchvalues[name] = match.group(1)

        if searchvalues:
            r = requests.get('https://keybase.io/_/api/1.0/user/lookup.json?fields=basics&' + 
                '&'.join(['{}={}'.format(name, value) for name, value in searchvalues.items()]))
            keybase_username = r.json()['them'][0]['basics']['username']

        if keybase_username == '%' and telegram_username == '%':
            return None

    if keybase_username != '%' and telegram_username == '%':
        proof = Proof.query.filter(or_(Proof.telegram_username == keybase_username, Proof.keybase_username == keybase_username))
    else:
        proof = Proof.query.filter(
            Proof.telegram_username.like(telegram_username), Proof.keybase_username.like(keybase_username)).first()

    return proof


def store_proof(proof, signed_block, update):
    try:
        session = db_session()
        newproof = Proof(
            user_id=update.message.from_user.id,
            keybase_username=proof['body']['key']['username'],
            telegram_username=proof['body']['service']['username'],
            chat_id=update.message.chat_id,
            message_id=update.message.message_id,
            proof_object=json.dumps(proof),
            signed_block=signed_block)
        session.add(newproof)
    except Exception as e:
        raise e
    else:
        session.commit()
