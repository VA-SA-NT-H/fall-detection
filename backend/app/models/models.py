from sqlalchemy import Column, Integer, String
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    phone_number = Column(String, nullable=True) # Caregiver SMS target number
    twilio_sid = Column(String, nullable=True)
    twilio_token = Column(String, nullable=True)
    twilio_phone = Column(String, nullable=True)
