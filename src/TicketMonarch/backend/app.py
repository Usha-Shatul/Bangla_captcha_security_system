import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_BACKEND_DIR, "..", ".."))

if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

from flask import Flask, request, jsonify
from flask_cors import CORS
from config import Config
from database.models import init_db, migrate_db, get_db


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["JWT_SECRET"] = Config.JWT_SECRET
    app.config["JWT_EXPIRY_HOURS"] = Config.JWT_EXPIRY_HOURS
    Config.init_dirs()

    CORS(app, origins=Config.CORS_ORIGINS, supports_credentials=True)

    from routes.captcha import _get_easy_loader, _get_medium_loader
    _get_easy_loader()
    _get_medium_loader()

    from routes.auth import auth_bp
    from routes.captcha import captcha_bp
    from routes.behavior import behavior_bp
    from routes.rl import rl_bp
    from routes.dev import dev_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(captcha_bp)
    app.register_blueprint(behavior_bp)
    app.register_blueprint(rl_bp)
    app.register_blueprint(dev_bp)

    @app.route("/api/health", methods=["GET"])
    def health():
        return {
            "status": "ok",
            "service": "TicketMonarch Backend",
            "database": "MySQL",
            "rl_algorithm": Config.RL_ALGORITHM,
        }

    @app.route("/api/booking/ticket", methods=["POST"])
    def book_ticket():
        from utils.auth import verify_token

        auth_header = request.headers.get("Authorization", "")
        user_id = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = verify_token(token, Config.JWT_SECRET)
            if payload:
                user_id = payload.get("user_id")

        data = request.get_json()
        session_id = data.get("session_id")
        destination = data.get("destination")
        travel_date = data.get("date")
        passengers = data.get("passengers", 1)
        seat = data.get("seat", "")

        if not destination or not travel_date:
            return jsonify({"detail": "গন্ত্যস্থল এবং তারিখ প্রয়োজন।"}), 400

        captcha_verified = False
        if session_id:
            try:
                db = get_db()
                try:
                    session = db.execute(
                        "SELECT solved FROM captcha_sessions WHERE session_id = %s",
                        (session_id,),
                    ).fetchone()
                    if session:
                        captcha_verified = bool(session["solved"])
                    else:
                        captcha_verified = True
                finally:
                    db.close()
            except Exception:
                captcha_verified = True

        if not captcha_verified:
            return jsonify({"detail": "ক্যাপচা যাচাই প্রয়োজন।"}), 403

        try:
            db = get_db()
            try:
                cursor = db.execute(
                    """INSERT INTO bookings
                       (user_id, session_id, destination, travel_date, passengers, seat_preference, captcha_verified)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (user_id, session_id, destination, travel_date, passengers, seat, 1),
                )
                booking_id = cursor.lastrowid
                db.commit()
            finally:
                db.close()

            return jsonify({
                "status": "confirmed",
                "booking_id": booking_id,
                "destination": destination,
                "date": travel_date,
                "passengers": passengers,
                "seat": seat,
            })
        except Exception as e:
            return jsonify({"detail": f"বুকিং ব্যর্থ: {str(e)}"}), 500

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"detail": "পেজ পাওয়া যায়নি।"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"detail": "সার্ভারে সমস্যা হয়েছে।"}), 500

    return app


if __name__ == "__main__":
    init_db()
    migrate_db()
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="127.0.0.1", port=port, debug=debug)
