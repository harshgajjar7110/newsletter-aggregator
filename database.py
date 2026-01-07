from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class Newsletter(Base):
    __tablename__ = 'newsletters'

    id = Column(Integer, primary_key=True)
    sender = Column(String(255))
    subject = Column(String(255))
    date_received = Column(DateTime)
    content_text = Column(Text)
    # audio_path deprecated in favor of Web Speech API
    audio_path = Column(String(255), nullable=True)
    gmail_id = Column(String(255), unique=True) # To prevent duplicate syncs
    status = Column(String(50), default='unread') # unread, in_progress, done

    def __repr__(self):
        return f"<Newsletter(sender='{self.sender}', subject='{self.subject}')>"

class Settings(Base):
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True)
    value = Column(String(255))

    def __repr__(self):
        return f"<Settings(key='{self.key}', value='{self.value}')>"

# Setup Database
engine = create_engine('sqlite:///newsletters.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_session():
    return Session()
