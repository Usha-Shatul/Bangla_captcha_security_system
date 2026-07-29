import mysql.connector
from mysql.connector import pooling
from config import Config


_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="ticketmonarch_pool",
            pool_size=5,
            pool_reset_session=True,
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            autocommit=False,
        )
    return _pool


class MySQLWrapper:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, query, params=None):
        cursor = self._conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        return cursor

    def commit(self):
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def get_db():
    pool = _get_pool()
    conn = pool.get_connection()
    return MySQLWrapper(conn)


def init_db():
    pool = _get_pool()
    conn = pool.get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            username      VARCHAR(64)  NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_users_username (username)
        ) ENGINE=InnoDB
    """)
    conn.commit()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS captcha_sessions (
            id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            session_id       VARCHAR(64)  NOT NULL,
            user_id          INT UNSIGNED NULL,
            word_list        TEXT         NOT NULL,
            difficulty       TINYINT UNSIGNED NOT NULL DEFAULT 2,
            solved           TINYINT(1)   NOT NULL DEFAULT 0,
            used             TINYINT(1)   NOT NULL DEFAULT 0,
            created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_captcha_sessions_sid (session_id),
            KEY idx_captcha_sessions_user (user_id)
        ) ENGINE=InnoDB
    """)
    conn.commit()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS behavior_logs (
            id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            session_id        VARCHAR(64)  NOT NULL,
            user_ip           VARCHAR(64)  NULL,
            mouse_events      INT UNSIGNED NOT NULL DEFAULT 0,
            keyboard_events   INT UNSIGNED NOT NULL DEFAULT 0,
            bot_score         DOUBLE       NOT NULL DEFAULT 0,
            is_bot            TINYINT(1)   NOT NULL DEFAULT 0,
            confidence        DOUBLE       NOT NULL DEFAULT 0.5,
            method            VARCHAR(32)  NOT NULL DEFAULT 'unknown',
            label             VARCHAR(32)  NOT NULL DEFAULT 'unknown',
            features_json     TEXT         NULL,
            events_json       TEXT         NULL,
            created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_behavior_logs_session (session_id),
            KEY idx_behavior_logs_label (label)
        ) ENGINE=InnoDB
    """)
    conn.commit()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id                INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            user_id           INT UNSIGNED NULL,
            session_id        VARCHAR(64)  NULL,
            destination       VARCHAR(128) NOT NULL,
            travel_date       VARCHAR(32)  NOT NULL,
            passengers        INT          NOT NULL DEFAULT 1,
            seat_preference   VARCHAR(64)  NULL,
            captcha_verified  TINYINT(1)   NOT NULL DEFAULT 0,
            created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_bookings_user (user_id),
            KEY idx_bookings_session (session_id)
        ) ENGINE=InnoDB
    """)
    conn.commit()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rl_episodes (
            id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            session_id      VARCHAR(64)  NULL,
            action          INT          NULL,
            action_name     VARCHAR(32)  NULL,
            difficulty      TINYINT UNSIGNED NULL,
            reward          DOUBLE       NOT NULL DEFAULT 0,
            is_bot          TINYINT(1)   NOT NULL DEFAULT 0,
            bot_score       DOUBLE       NOT NULL DEFAULT 0,
            created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_rl_episodes_session (session_id)
        ) ENGINE=InnoDB
    """)
    conn.commit()

    conn.close()


def migrate_db():
    try:
        pool = _get_pool()
        conn = pool.get_connection()
        cursor = conn.cursor(dictionary=True)

        migrations = [
            "ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS label VARCHAR(32) NOT NULL DEFAULT 'unknown'",
            "ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS features_json TEXT NULL",
            "ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS events_json TEXT NULL",
            "ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS method VARCHAR(32) NOT NULL DEFAULT 'unknown'",
            "ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS confidence DOUBLE NOT NULL DEFAULT 0.5",
            "ALTER TABLE behavior_logs ADD COLUMN IF NOT EXISTS user_ip VARCHAR(64) NULL",
        ]
        for stmt in migrations:
            try:
                cursor.execute(stmt)
            except mysql.connector.errors.ProgrammingError:
                pass
        conn.commit()
        conn.close()
    except Exception:
        pass
