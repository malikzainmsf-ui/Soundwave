import os
import uuid
import random
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                    session, flash, send_from_directory, jsonify, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from db import get_db, init_db

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
COVER_DIR = os.path.join(BASE_DIR, "static", "covers")
ALLOWED_AUDIO = {"mp3", "wav", "ogg", "m4a"}
ALLOWED_IMAGE = {"png", "jpg", "jpeg", "webp"}
ACCENT_COLORS = ["#FFB13C", "#6C5CE7", "#00C2A8", "#FF5C7A", "#4FA8FF", "#E8A33D"]

app = Flask(__name__)
app.secret_key = "soundwave-dev-secret-change-in-production"
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # 60MB uploads

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(COVER_DIR, exist_ok=True)
init_db()


def allowed_file(filename, allowed_set):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_set


def current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    db.close()
    return user


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    return {"me": current_user()}


# ---------- Auth ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not (username and display_name and email and password):
            flash("Fill in all fields.", "error")
            return redirect(url_for("register"))
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("register"))
        if not username.replace("_", "").isalnum():
            flash("Username can only contain letters, numbers, underscores.", "error")
            return redirect(url_for("register"))

        db = get_db()
        exists = db.execute("SELECT id FROM users WHERE username = ? OR email = ?",
                             (username, email)).fetchone()
        if exists:
            db.close()
            flash("Username or email already taken.", "error")
            return redirect(url_for("register"))

        db.execute(
            "INSERT INTO users (username, display_name, email, password_hash, avatar_color) VALUES (?, ?, ?, ?, ?)",
            (username, display_name, email, generate_password_hash(password), random.choice(ACCENT_COLORS))
        )
        db.commit()
        user = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        db.close()
        session["user_id"] = user["id"]
        flash("Welcome to SoundWave!", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ? OR email = ?",
                           (identifier, identifier)).fetchone()
        db.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['display_name']}.", "success")
            nxt = request.args.get("next")
            return redirect(nxt or url_for("index"))
        flash("Invalid username/email or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("index"))


# ---------- Core pages ----------

@app.route("/")
def index():
    db = get_db()
    recent = db.execute("""
        SELECT songs.*, users.username, users.display_name, users.avatar_color
        FROM songs JOIN users ON songs.user_id = users.id
        ORDER BY songs.created_at DESC LIMIT 12
    """).fetchall()
    trending = db.execute("""
        SELECT songs.*, users.username, users.display_name, users.avatar_color
        FROM songs JOIN users ON songs.user_id = users.id
        ORDER BY songs.play_count DESC, songs.created_at DESC LIMIT 8
    """).fetchall()
    db.close()
    return render_template("index.html", recent=recent, trending=trending)


@app.route("/charts")
def charts():
    db = get_db()
    by_plays = db.execute("""
        SELECT songs.*, users.username, users.display_name, users.avatar_color
        FROM songs JOIN users ON songs.user_id = users.id
        ORDER BY songs.play_count DESC LIMIT 50
    """).fetchall()
    by_likes = db.execute("""
        SELECT songs.*, users.username, users.display_name, users.avatar_color,
               (SELECT COUNT(*) FROM likes WHERE likes.song_id = songs.id) AS like_count
        FROM songs JOIN users ON songs.user_id = users.id
        ORDER BY like_count DESC LIMIT 50
    """).fetchall()
    db.close()
    return render_template("charts.html", by_plays=by_plays, by_likes=by_likes)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    songs, artists = [], []
    if q:
        db = get_db()
        like = f"%{q}%"
        songs = db.execute("""
            SELECT songs.*, users.username, users.display_name, users.avatar_color
            FROM songs JOIN users ON songs.user_id = users.id
            WHERE songs.title LIKE ? OR songs.artist_name LIKE ? OR songs.genre LIKE ?
            ORDER BY songs.play_count DESC LIMIT 40
        """, (like, like, like)).fetchall()
        artists = db.execute("""
            SELECT * FROM users WHERE username LIKE ? OR display_name LIKE ? LIMIT 20
        """, (like, like)).fetchall()
        db.close()
    return render_template("search.html", q=q, songs=songs, artists=artists)


# ---------- Upload ----------

@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        artist_name = request.form.get("artist_name", "").strip()
        genre = request.form.get("genre", "").strip()
        description = request.form.get("description", "").strip()
        audio_file = request.files.get("audio_file")
        cover_file = request.files.get("cover_file")

        if not title or not audio_file or audio_file.filename == "":
            flash("Title and an audio file are required.", "error")
            return redirect(url_for("upload"))
        if not allowed_file(audio_file.filename, ALLOWED_AUDIO):
            flash("Audio must be mp3, wav, ogg, or m4a.", "error")
            return redirect(url_for("upload"))

        ext = audio_file.filename.rsplit(".", 1)[1].lower()
        stored_name = f"{uuid.uuid4().hex}.{ext}"
        audio_file.save(os.path.join(UPLOAD_DIR, stored_name))

        cover_name = ""
        if cover_file and cover_file.filename and allowed_file(cover_file.filename, ALLOWED_IMAGE):
            cext = cover_file.filename.rsplit(".", 1)[1].lower()
            cover_name = f"{uuid.uuid4().hex}.{cext}"
            cover_file.save(os.path.join(COVER_DIR, cover_name))

        db = get_db()
        db.execute("""
            INSERT INTO songs (user_id, title, artist_name, genre, description, filename, cover_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session["user_id"], title, artist_name or current_user()["display_name"],
              genre, description, stored_name, cover_name))
        db.commit()
        song_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.close()
        flash("Track uploaded.", "success")
        return redirect(url_for("song_detail", song_id=song_id))

    return render_template("upload.html")


# ---------- Song detail / interactions ----------

@app.route("/song/<int:song_id>")
def song_detail(song_id):
    db = get_db()
    song = db.execute("""
        SELECT songs.*, users.username, users.display_name, users.avatar_color
        FROM songs JOIN users ON songs.user_id = users.id
        WHERE songs.id = ?
    """, (song_id,)).fetchone()
    if not song:
        db.close()
        abort(404)
    comments = db.execute("""
        SELECT comments.*, users.username, users.display_name, users.avatar_color
        FROM comments JOIN users ON comments.user_id = users.id
        WHERE song_id = ? ORDER BY comments.created_at DESC
    """, (song_id,)).fetchall()
    like_count = db.execute("SELECT COUNT(*) AS c FROM likes WHERE song_id = ?", (song_id,)).fetchone()["c"]
    liked = False
    my_playlists = []
    if "user_id" in session:
        liked = db.execute("SELECT 1 FROM likes WHERE song_id = ? AND user_id = ?",
                            (song_id, session["user_id"])).fetchone() is not None
        my_playlists = db.execute("SELECT * FROM playlists WHERE user_id = ?",
                                   (session["user_id"],)).fetchall()
    db.close()
    return render_template("song.html", song=song, comments=comments, like_count=like_count,
                            liked=liked, my_playlists=my_playlists)


@app.route("/song/<int:song_id>/play", methods=["POST"])
def register_play(song_id):
    db = get_db()
    db.execute("UPDATE songs SET play_count = play_count + 1 WHERE id = ?", (song_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@app.route("/song/<int:song_id>/like", methods=["POST"])
@login_required
def toggle_like(song_id):
    db = get_db()
    existing = db.execute("SELECT 1 FROM likes WHERE song_id = ? AND user_id = ?",
                           (song_id, session["user_id"])).fetchone()
    if existing:
        db.execute("DELETE FROM likes WHERE song_id = ? AND user_id = ?", (song_id, session["user_id"]))
        liked = False
    else:
        db.execute("INSERT INTO likes (song_id, user_id) VALUES (?, ?)", (song_id, session["user_id"]))
        liked = True
    db.commit()
    count = db.execute("SELECT COUNT(*) AS c FROM likes WHERE song_id = ?", (song_id,)).fetchone()["c"]
    db.close()
    return jsonify({"liked": liked, "count": count})


@app.route("/song/<int:song_id>/comment", methods=["POST"])
@login_required
def add_comment(song_id):
    body = request.form.get("body", "").strip()
    if body:
        db = get_db()
        db.execute("INSERT INTO comments (user_id, song_id, body) VALUES (?, ?, ?)",
                   (session["user_id"], song_id, body))
        db.commit()
        db.close()
    return redirect(url_for("song_detail", song_id=song_id))


@app.route("/stream/<filename>")
def stream(filename):
    return send_from_directory(UPLOAD_DIR, filename, conditional=True)


# ---------- Profiles / follow ----------

@app.route("/profile/<username>")
def profile(username):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        db.close()
        abort(404)
    songs = db.execute("""
        SELECT songs.*, users.username, users.display_name, users.avatar_color
        FROM songs JOIN users ON songs.user_id = users.id
        WHERE users.id = ? ORDER BY songs.created_at DESC
    """, (user["id"],)).fetchall()
    followers = db.execute("SELECT COUNT(*) AS c FROM follows WHERE followed_id = ?", (user["id"],)).fetchone()["c"]
    following = db.execute("SELECT COUNT(*) AS c FROM follows WHERE follower_id = ?", (user["id"],)).fetchone()["c"]
    is_following = False
    if "user_id" in session:
        is_following = db.execute("SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = ?",
                                   (session["user_id"], user["id"])).fetchone() is not None
    db.close()
    return render_template("profile.html", profile_user=user, songs=songs,
                            followers=followers, following=following, is_following=is_following)


@app.route("/profile/<username>/follow", methods=["POST"])
@login_required
def follow(username):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        db.close()
        abort(404)
    if user["id"] == session["user_id"]:
        db.close()
        return redirect(url_for("profile", username=username))
    existing = db.execute("SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = ?",
                           (session["user_id"], user["id"])).fetchone()
    if existing:
        db.execute("DELETE FROM follows WHERE follower_id = ? AND followed_id = ?",
                   (session["user_id"], user["id"]))
    else:
        db.execute("INSERT INTO follows (follower_id, followed_id) VALUES (?, ?)",
                   (session["user_id"], user["id"]))
    db.commit()
    db.close()
    return redirect(url_for("profile", username=username))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        bio = request.form.get("bio", "").strip()
        db = get_db()
        db.execute("UPDATE users SET display_name = ?, bio = ? WHERE id = ?",
                   (display_name, bio, session["user_id"]))
        db.commit()
        db.close()
        flash("Profile updated.", "success")
        return redirect(url_for("profile", username=current_user()["username"]))
    return render_template("settings.html")


# ---------- Playlists ----------

@app.route("/playlists")
@login_required
def playlists():
    db = get_db()
    rows = db.execute("SELECT * FROM playlists WHERE user_id = ? ORDER BY created_at DESC",
                       (session["user_id"],)).fetchall()
    db.close()
    return render_template("playlists.html", playlists=rows)


@app.route("/playlists/new", methods=["POST"])
@login_required
def new_playlist():
    title = request.form.get("title", "").strip()
    if title:
        db = get_db()
        db.execute("INSERT INTO playlists (user_id, title) VALUES (?, ?)", (session["user_id"], title))
        db.commit()
        db.close()
        flash("Playlist created.", "success")
    return redirect(url_for("playlists"))


@app.route("/playlist/<int:playlist_id>")
def playlist_detail(playlist_id):
    db = get_db()
    pl = db.execute("""
        SELECT playlists.*, users.username, users.display_name
        FROM playlists JOIN users ON playlists.user_id = users.id
        WHERE playlists.id = ?
    """, (playlist_id,)).fetchone()
    if not pl:
        db.close()
        abort(404)
    songs = db.execute("""
        SELECT songs.*, users.username, users.display_name, users.avatar_color
        FROM playlist_songs
        JOIN songs ON playlist_songs.song_id = songs.id
        JOIN users ON songs.user_id = users.id
        WHERE playlist_songs.playlist_id = ?
        ORDER BY playlist_songs.position
    """, (playlist_id,)).fetchall()
    db.close()
    return render_template("playlist.html", playlist=pl, songs=songs)


@app.route("/playlist/<int:playlist_id>/add", methods=["POST"])
@login_required
def add_to_playlist(playlist_id):
    song_id = request.form.get("song_id")
    db = get_db()
    pl = db.execute("SELECT * FROM playlists WHERE id = ? AND user_id = ?",
                     (playlist_id, session["user_id"])).fetchone()
    if pl and song_id:
        pos = db.execute("SELECT COALESCE(MAX(position), 0) + 1 AS p FROM playlist_songs WHERE playlist_id = ?",
                          (playlist_id,)).fetchone()["p"]
        db.execute("INSERT OR IGNORE INTO playlist_songs (playlist_id, song_id, position) VALUES (?, ?, ?)",
                   (playlist_id, song_id, pos))
        db.commit()
        flash("Added to playlist.", "success")
    db.close()
    return redirect(request.referrer or url_for("playlists"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
