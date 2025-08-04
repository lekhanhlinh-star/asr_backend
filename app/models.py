from sqlalchemy import Column, String, Integer, Boolean, JSON as SQLAlchemyJSON, Text, ForeignKey
from database import Base

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String(32), primary_key=True, index=True)
    status = Column(Integer, default=0)
    file_len = Column(String(50))
    file_name = Column(String(255))
    total_segments = Column(Integer, nullable=True)
    speaker_number = Column(String(10))
    has_separate = Column(Boolean, default=False)
    language = Column(String(50))
    pd = Column(String(50), nullable=True)
    hotWord = Column(String(50), nullable=True)
    file_path = Column(String(255), nullable=True)
    result = Column(SQLAlchemyJSON, nullable=True)
    error = Column(Text, nullable=True)

class TaskSegment(Base):
    __tablename__ = "task_segments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(32), ForeignKey("tasks.id"))
    segment_id = Column(Integer)
    segment_len = Column(String(50))
    file_path = Column(String(255))
    status = Column(Integer, default=0)  # 0: uploaded, 2: processing, 9: completed

