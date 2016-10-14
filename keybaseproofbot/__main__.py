import argparse
import os
import sys

from keybaseproofbot.config import config

if __name__ == "__main__":
    if os.getenv('FLYNN_POSTGRES'):
        config['DATABASE_URL'] = os.getenv('DATABASE_URL')
        config['GROUP_ID'] = os.getenv('GROUP_ID')
        config['TG_TOKEN'] = os.getenv('TG_TOKEN')
    else:
        parser = argparse.ArgumentParser(
        description="Unofficial Keybase Telegram User Proof Bot")
        parser.add_argument(
            '-c',
            '--config',
            nargs='?',
            type=argparse.FileType('r'),
            default='settings.py',
            help="Config file to use")
        args = parser.parse_args()
        exec(args.config.read(), config)
    from keybaseproofbot.bot import main
    main()
