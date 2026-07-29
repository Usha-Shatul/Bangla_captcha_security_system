"""
MySQL Database Setup Script for Adaptive Bangla CAPTCHA.

Run this once to initialize the MySQL database:
    python db_setup.py

Requires MySQL 8.0+ running with credentials matching .env config.
"""

import os
import sys
import mysql.connector
from mysql.connector import Error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from config import Config


def setup_database():
    print("=" * 60)
    print("Adaptive Bangla CAPTCHA - MySQL Setup")
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

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DATABASE}` "
                        f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"\n[OK] Database '{Config.MYSQL_DATABASE}' created/verified")

        cursor.execute(f"USE `{Config.MYSQL_DATABASE}`")

        schema_path = os.path.join(os.path.dirname(__file__), "database", "schema.sql")
        if os.path.isfile(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            for statement in schema_sql.split(";"):
                statement = statement.strip()
                if not statement or statement.startswith("--"):
                    continue
                try:
                    cursor.execute(statement)
                except Error as e:
                    if "Duplicate" not in str(e) and "already exists" not in str(e):
                        print(f"  [WARN] {e}")

            conn.commit()
            print("[OK] Schema tables created/verified")
        else:
            print("[SKIP] schema.sql not found — tables will be created on first app start")

        from database.models import init_db
        init_db()
        print("[OK] Models init_db() completed")

        from database.models import migrate_db
        migrate_db()
        print("[OK] Migrations applied")

        cursor.close()
        conn.close()

        print("\n" + "=" * 60)
        print("Setup Complete!")
        print(f"\nStart the backend:  cd {os.path.dirname(__file__)} && python app.py")
        print(f"Start the frontend: cd ../frontend && npm run dev")
        print("=" * 60)

    except Error as e:
        print(f"\n[ERROR] MySQL connection failed: {e}")
        print("\nPlease check:")
        print(f"  1. MySQL is running on {Config.MYSQL_HOST}:{Config.MYSQL_PORT}")
        print(f"  2. User '{Config.MYSQL_USER}' has access")
        print(f"  3. Password is correct in .env file")
        print(f"\nTo create the user manually:")
        print(f"  CREATE USER '{Config.MYSQL_USER}'@'localhost' IDENTIFIED BY 'your_password';")
        print(f"  GRANT ALL PRIVILEGES ON *.* TO '{Config.MYSQL_USER}'@'localhost';")
        print(f"  FLUSH PRIVILEGES;")
        sys.exit(1)


if __name__ == "__main__":
    setup_database()
