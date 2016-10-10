from functools import wraps

from keybaseproofbot.config import config


def filter_group(f):

    @wraps(f)
    def wrapper(bot, update, *args, **kwargs):
        if update.message.chat_id == config['GROUP_ID']:
            return f(bot, update, *args, **kwargs)
        else:
            bot.leaveChat(chat_id=update.message.chat_id)

    return wrapper


def filter_private(f):

    @wraps(f)
    def wrapper(bot, update, *args, **kwargs):
        if update.message.chat.type == 'private':
            return f(bot, update, *args, **kwargs)

    return wrapper
