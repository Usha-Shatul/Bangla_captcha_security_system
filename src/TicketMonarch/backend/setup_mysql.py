"""
MySQL Database Setup Script for Adaptive Bangla CAPTCHA.

Creates the database and all tables from schema.sql.

Usage:
    python setup_mysql.py
"""

import os
import sys
import mysql.connector
from mysql.connector import Error

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_BACKEND_DIR, "..", ".."))

if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

from config import Config


def setup():
    print("=" * 60)
    print("Adaptive Bangla CAPTCHA — MySQL Setup")
    print("=" * 60)

    print(f"\nHost:     {Config.MYSQL_HOST}:{Config.MYSQL_PORT}")
    print(f"User:     {Config.MYSQL_USER}")
    print(f"Database: {Config.MYSQL_DATABASE}")
    print(f"RL Algo:  {Config.RL_ALGORITHM}")

    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            charset="utf8mb4",
        )
        cursor = conn.cursor()

        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DATABASE}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        print(f"\n[OK] Database '{Config.MYSQL_DATABASE}' created/verified")

        cursor.execute(f"USE `{Config.MYSQL_DATABASE}`")

        schema_path = os.path.join(_BACKEND_DIR, "database", "schema.sql")
        if os.path.isfile(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            for statement in schema_sql.split(";"):
                statement = statement.strip()
                if not statement or statement.startswith("--"):
                    continue
                # Skip DATABASE/USE statements (already handled)
                if "CREATE DATABASE" in statement or "USE " in statement:
                    continue
                try:
                    cursor.execute(statement)
                except Error as e:
                    if "Duplicate" not in str(e) and "already exists" not in str(e):
                        print(f"  [WARN] {e}")

            conn.commit()
            print("[OK] Schema tables created/verified")
        else:
            print("[SKIP] schema.sql not found")

        cursor.close()
        conn.close()

        print("\n" + "=" * 60)
        print("Setup Complete!")
        print(f"\nStart backend:  cd {_BACKEND_DIR} && python app.py")
        print(f"Start frontend: cd ../frontend && npm run dev")
        print("=" * 60)

    except Error as e:
        print(f"\n[ERROR] MySQL connection failed: {e}")
        print("\nPlease check:")
        print(f"  1. MySQL is running on {Config.MYSQL_HOST}:{Config.MYSQL_PORT}")
        print(f"  2. User '{Config.MYSQL_USER}' has access")
        print(f"  3. Password is correct in .env")
        sys.exit(1)


if __name__ == "__main__":
    setup()
