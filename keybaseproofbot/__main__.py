import argparse
import sys

from keybaseproofbot.config import config

if __name__ == "__main__":
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
