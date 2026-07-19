# SoundWave

A full-stack music sharing platform — SoundCloud-style — built with Flask + SQLite.

## Features
- User accounts (sign up, log in, sessions)
- Artist profiles with bio, avatar, follower counts
- Upload tracks (mp3/wav/ogg/m4a) with cover art
- Persistent bottom audio player with real streaming (supports seeking / range requests)
- Likes, comments, play counts
- Charts (top by plays, top by likes)
- Search (tracks, artists, genres)
- Playlists (create, add tracks)
- Follow system

## Important — about content
This app ships **empty**. It does not, and must not, include copyrighted commercial
music (major-label songs, e.g. from artists like Arijit Singh) — hosting that without
a license is illegal. The platform is built the same way the real SoundCloud started:
a place where users upload their **own** original tracks, covers, or licensed audio.
If you want demo content, use royalty-free tracks (e.g. from Free Music Archive,
Pixabay Music, or your own recordings).

## Setup

```bash
cd soundwave
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5050** in your browser.

The SQLite database (`soundwave.db`) is created automatically on first run.
Uploaded audio goes to `static/uploads/`, cover art to `static/covers/`.

## Project structure
```
soundwave/
├── app.py              # All routes / application logic
├── db.py                # SQLite schema + connection helper
├── requirements.txt
├── static/
│   ├── css/style.css    # Design system
│   ├── js/player.js     # Global audio player + like/playlist interactions
│   ├── uploads/         # Uploaded audio files
│   └── covers/          # Uploaded cover art
└── templates/           # Jinja2 HTML templates
```

## Notes for taking this to production
- Change `app.secret_key` in `app.py` to a real secret (currently a placeholder).
- Switch from the Flask dev server to a real WSGI server (gunicorn/uWSGI) behind nginx.
- Move file storage to S3 or similar cloud storage instead of local disk.
- Add rate limiting on login/register/upload endpoints.
- Consider transcoding uploads to a consistent bitrate/format (e.g. with ffmpeg) so
  playback is consistent across devices.
- Add email verification and password-reset flows.
- For real scale, move from SQLite to Postgres.
