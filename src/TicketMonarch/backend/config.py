import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    JWT_SECRET = os.environ.get("JWT_SECRET", "jwt-secret-change-in-production")
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "ticketmonarch_db")

    DB_PATH = os.environ.get(
        "DB_PATH",
        os.path.join(os.path.dirname(__file__), "database", "app.db"),
    )

    EASY_CAPTCHA_DATASET_DIR = os.environ.get(
        "EASY_CAPTCHA_DATASET_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "datasets", "easy"),
    )
    MEDIUM_CAPTCHA_DATASET_DIR = os.environ.get(
        "MEDIUM_CAPTCHA_DATASET_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "datasets", "medium"),
    )

    CAPTCHA_SESSION_DIR = os.path.join(
        os.path.dirname(__file__), "database", "captcha_cache"
    )

    RL_CHECKPOINT_DIR = os.environ.get(
        "RL_CHECKPOINT_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "rl_captcha", "checkpoints"),
    )
    CLASSIFIER_MODEL_DIR = os.environ.get(
        "CLASSIFIER_MODEL_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "classifier", "saved_models"),
    )

    RL_ALGORITHM = os.environ.get("RL_ALGORITHM", "ppo")

    MAX_CAPTCHA_ATTEMPTS = 3
    DIFFICULTY_LEVELS = 3

    MEDIUM_GRID_SIZE = 3
    MEDIUM_TARGET_MIN = 3
    MEDIUM_TARGET_MAX = 5

    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

    BEHAVIOR_SAMPLE_INTERVAL_MS = 2000
    BOT_THRESHOLD = float(os.environ.get("BOT_THRESHOLD", "0.7"))

    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

    @classmethod
    def init_dirs(cls):
        for d in [
            cls.CAPTCHA_SESSION_DIR,
            cls.DATA_DIR,
            cls.EASY_CAPTCHA_DATASET_DIR,
            cls.MEDIUM_CAPTCHA_DATASET_DIR,
        ]:
            os.makedirs(d, exist_ok=True)
