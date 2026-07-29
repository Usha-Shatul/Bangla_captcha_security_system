from flask import Blueprint, request, jsonify, current_app
from utils.auth import hash_password, verify_password, generate_token, generate_session_id
from database.models import get_db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"detail": "ব্যবহারকারীর নাম এবং পাসওয়ার্ড প্রয়োজন।"}), 400

    if len(username) < 3:
        return jsonify({"detail": "ব্যবহারকারীর নাম কমপক্ষে ৩ অক্ষর হতে হবে।"}), 400

    if len(password) < 6:
        return jsonify({"detail": "পাসওয়ার্ড কমপক্ষে ৬ অক্ষর হতে হবে।"}), 400

    db = get_db()
    try:
        existing = db.execute(
            "SELECT id FROM users WHERE username = %s", (username,)
        ).fetchone()
        if existing:
            return jsonify({"detail": "এই ব্যবহারকারীর নাম ইতিমধ্যে বিদ্যমান।"}), 409

        password_hashed = hash_password(password)
        cursor = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, password_hashed),
        )
        user_id = cursor.lastrowid
        db.commit()

        token = generate_token(
            user_id,
            username,
            current_app.config["JWT_SECRET"],
            current_app.config["JWT_EXPIRY_HOURS"],
        )

        return jsonify({
            "token": token,
            "user": {"id": user_id, "username": username},
        }), 201

    finally:
        db.close()


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"detail": "ব্যবহারকারীর নাম এবং পাসওয়ার্ড প্রয়োজন।"}), 400

    db = get_db()
    try:
        user = db.execute(
            "SELECT id, username, password_hash FROM users WHERE username = %s",
            (username,),
        ).fetchone()

        if not user or not verify_password(password, user["password_hash"]):
            return jsonify({"detail": "ভুল ব্যবহারকারীর নাম বা পাসওয়ার্ড।"}), 401

        token = generate_token(
            user["id"],
            user["username"],
            current_app.config["JWT_SECRET"],
            current_app.config["JWT_EXPIRY_HOURS"],
        )

        return jsonify({
            "token": token,
            "user": {"id": user["id"], "username": user["username"]},
        })

    finally:
        db.close()


@auth_bp.route("/api/auth/me", methods=["GET"])
def get_current_user():
    from utils.auth import verify_token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"detail": "অনুমোদন প্রয়োজন।"}), 401

    token = auth_header[7:]
    payload = verify_token(token, current_app.config["JWT_SECRET"])
    if not payload:
        return jsonify({"detail": "অবৈধ টোকেন।"}), 401

    db = get_db()
    try:
        user = db.execute(
            "SELECT id, username FROM users WHERE id = %s", (payload["user_id"],)
        ).fetchone()
        if not user:
            return jsonify({"detail": "ব্যবহারকারী পাওয়া যায়নি।"}), 404

        return jsonify({"id": user["id"], "username": user["username"]})
    finally:
        db.close()
