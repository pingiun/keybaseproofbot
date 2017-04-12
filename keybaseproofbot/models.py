from sqlalchemy import Column, BigInteger, String

from keybaseproofbot.database import Base


class Proof(Base):
    __tablename__ = 'proofs'
    user_id = Column(BigInteger, primary_key=True)
    keybase_username = Column(String)
    telegram_username = Column(String)
    chat_id = Column(BigInteger)
    message_id = Column(BigInteger)
    proof_object = Column(String)
    signed_block = Column(String)

    def __init__(self, user_id, keybase_username, telegram_username, chat_id,
                 message_id, proof_object, signed_block):
        self.user_id = user_id
        self.keybase_username = keybase_username
        self.telegram_username = telegram_username
        self.chat_id = chat_id
        self.message_id = message_id
        self.proof_object = proof_object
        self.signed_block = signed_block
