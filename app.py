import hashlib
import os
from flask import Flask, render_template, request
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "1q2w3e4r5t6y@AA",
    "database": "right_to_reality",
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def compute_sha256(file_storage) -> str:
    file_storage.stream.seek(0)
    hasher = hashlib.sha256()
    for chunk in iter(lambda: file_storage.stream.read(8192), b""):
        hasher.update(chunk)
    file_storage.stream.seek(0)
    return hasher.hexdigest()


def fetch_recent_records(limit: int = 10):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, filename, sha256_hash, registered_at
            FROM media_records
            ORDER BY id DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows, None
    except Error as exc:
        return [], f"Database error: {exc}"


@app.route("/", methods=["GET"])
def index():
    records, db_error = fetch_recent_records()
    return render_template(
        "index.html",
        message=None,
        error=db_error,
        verification_result=None,
        records=records,
    )


@app.route("/register", methods=["POST"])
def register_image():
    uploaded_file = request.files.get("image")
    if not uploaded_file or not uploaded_file.filename:
        records, db_error = fetch_recent_records()
        return render_template(
            "index.html",
            message=None,
            error=db_error or "Please select an image file to register.",
            verification_result=None,
            records=records,
        )

    filename = os.path.basename(uploaded_file.filename)
    digest = compute_sha256(uploaded_file)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO media_records (filename, sha256_hash) VALUES (%s, %s)",
            (filename, digest),
        )
        conn.commit()
        cursor.close()
        conn.close()
        msg = f"Registered '{filename}' with SHA-256: {digest}"
        err = None
    except Error as exc:
        msg = None
        err = f"Failed to save record in MySQL: {exc}"

    records, fetch_err = fetch_recent_records()
    return render_template(
        "index.html",
        message=msg,
        error=err or fetch_err,
        verification_result=None,
        records=records,
    )


@app.route("/verify", methods=["POST"])
def verify_image():
    uploaded_file = request.files.get("image")
    if not uploaded_file or not uploaded_file.filename:
        records, db_error = fetch_recent_records()
        return render_template(
            "index.html",
            message=None,
            error=db_error or "Please select an image file to verify.",
            verification_result=None,
            records=records,
        )

    filename = os.path.basename(uploaded_file.filename)
    digest = compute_sha256(uploaded_file)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, filename, sha256_hash, registered_at
            FROM media_records
            WHERE sha256_hash = %s
            ORDER BY id DESC
            """,
            (digest,),
        )
        matches = cursor.fetchall()
        cursor.close()
        conn.close()
        result = {
            "checked_filename": filename,
            "sha256_hash": digest,
            "matches": matches,
        }
        err = None
    except Error as exc:
        result = None
        err = f"Failed to query MySQL: {exc}"

    records, fetch_err = fetch_recent_records()
    return render_template(
        "index.html",
        message=None,
        error=err or fetch_err,
        verification_result=result,
        records=records,
    )


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
