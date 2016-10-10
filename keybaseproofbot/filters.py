class CustomFilter:
    @staticmethod
    def supergrouptext(message):
        return message['chat']['type'] == 'supergroup' and message.text != ''
