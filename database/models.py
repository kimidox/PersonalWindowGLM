from datetime import datetime

from sqlalchemy import Column, String, Integer, TIMESTAMP, JSON, Text, UnicodeText

from database import Base, engine
from database.utils import get_local_time


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    created_at = Column(TIMESTAMP, default=get_local_time())
    updated_at = Column(TIMESTAMP, default=get_local_time())
    def to_dict(self):
        return {c.name:getattr(self,c.name) for c in self.__table__.columns}
class Conversations(Base):
    __tablename__ = 'conversations'
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, unique=True, index=True)
    user_id = Column(String, index=True)
    title = Column(String)
    # SkillAgent 当前轮已加载的 skill id（由 Memory 同步；兼容旧库见 sqlite_memory 迁移）
    active_skill_ids = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, default=get_local_time())
    updated_at = Column(TIMESTAMP, default=get_local_time())
    def to_dict(self):
        return {c.name:getattr(self,c.name) for c in self.__table__.columns}
class Messages(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True)
    conversation_id = Column(String, index=True)
    role = Column(String)

    content = Column(Text)
    # 使用json,使用UnicodeText 是因为我要看数据库内容
    ext=Column(JSON)
    created_at = Column(TIMESTAMP, default=get_local_time())
    updated_at = Column(TIMESTAMP, default=get_local_time())

    def to_dict(self):
        return {c.name:getattr(self,c.name) for c in self.__table__.columns}

if __name__ == '__main__':
    Base.metadata.create_all(engine)