from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 使用包目录而非 cwd，避免从其他工作目录启动时找不到库文件；SQLite 不会自动创建父目录。
_DB_DIR = Path(__file__).resolve().parent / "sqllite_data"
_DB_DIR.mkdir(parents=True, exist_ok=True)
DB_FILE = _DB_DIR / "sqllite_test.db"

engine = create_engine(
    f"sqlite:///{DB_FILE.resolve().as_posix()}",
    connect_args={"check_same_thread": False}  # SQLite特有参数，解决线程安全问题
)

# 3. 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine,expire_on_commit= False)

# 4. 创建基类（用于定义数据模型）
Base = declarative_base()

# 5. 优化后的会话获取函数（生成器 + 确保关闭）
def get_local_session():
    db = SessionLocal()
    try:
        yield db  # 提供会话
    finally:
        db.close()  # 确保会话最终关闭


@contextmanager
def get_session():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()  # 出错时回滚
        raise e
    finally:
        db.close()  # 确保会话关闭

if __name__ == '__main__':
    pass