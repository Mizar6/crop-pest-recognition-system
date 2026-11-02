"""系统配置模块。

砍掉登录与模型管理后：
- 不再需要 JWT 密钥与用户表
- 使用固定模型权重（settings.MODEL_PATH）
- 保留 MySQL 连接与上传目录
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# server 目录
SERVER_DIR = Path(__file__).resolve().parents[2]
# 项目根目录（client / server / train_project 的父级）
PROJECT_ROOT = SERVER_DIR.parent

# 加载 server 目录下的 .env
load_dotenv(SERVER_DIR / ".env")


class Settings:
    """应用全局配置。"""

    APP_NAME: str = "农作物病虫害叶片智能识别系统"

    # --- 数据库 ---
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "123456")
    DB_NAME: str = os.getenv("DB_NAME", "db_plant_diseases")

    # --- 文件存储 ---
    UPLOAD_ROOT: str = os.getenv("UPLOAD_ROOT", "D:/uploads45")

    # --- 模型 ---
    # 相对路径基于项目根目录解析，也可直接写绝对路径
    MODEL_PATH: str = os.getenv(
        "MODEL_PATH", "train_project/runs_retrain/yolo26n_cos120/weights/best.pt"
    )
    MODEL_NAME: str = os.getenv("MODEL_NAME", "YOLO26n 病虫害检测模型")
    DEFAULT_CONF: float = float(os.getenv("DEFAULT_CONF", "0.25"))
    DEFAULT_IMGSZ: int = int(os.getenv("DEFAULT_IMGSZ", "640"))

    # --- AI 问答（融合模块） ---
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    RAG_BASE_URL: str = os.getenv(
        "RAG_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    RAG_EMBEDDING_MODEL: str = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-v3")
    RAG_QA_MODEL: str = os.getenv("RAG_QA_MODEL", "qwen-plus")
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "4"))
    RAG_HISTORY_LIMIT: int = int(os.getenv("RAG_HISTORY_LIMIT", "10"))
    # 检索最高分低于该阈值 -> 开启联网搜索兜底
    RAG_SEARCH_THRESHOLD: float = float(os.getenv("RAG_SEARCH_THRESHOLD", "0.60"))
    VSTORE_DIR: str = os.getenv("VSTORE_DIR", "data/vstore")

    @property
    def vstore_path(self) -> Path:
        p = Path(self.VSTORE_DIR)
        return p if p.is_absolute() else (SERVER_DIR / p)

    @property
    def database_url(self) -> str:
        """拼接 SQLAlchemy 数据库连接串。"""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def model_abs_path(self) -> Path:
        """模型权重的绝对路径。"""
        p = Path(self.MODEL_PATH)
        return p if p.is_absolute() else (PROJECT_ROOT / p)


settings = Settings()
