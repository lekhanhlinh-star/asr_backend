from sqlalchemy import Column, String, Integer, Boolean, JSON as SQLAlchemyJSON, Text
from database import Base

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String(32), primary_key=True, index=True)
    status = Column(Integer, default=0)
    file_len = Column(String(50))
    file_name = Column(String(255))
    speaker_number = Column(String(10))
    has_separate = Column(Boolean, default=False)
    language = Column(String(50))
    pd = Column(String(50), nullable=True)
    hotWord = Column(String(50), nullable=True)
    file_path = Column(String(255), nullable=True)
    result = Column(SQLAlchemyJSON, nullable=True)
    error = Column(Text, nullable=True)