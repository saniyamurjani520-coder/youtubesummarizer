import re
import json
import sqlite3
import random
from collections import Counter
from datetime import datetime

import requests
import yt_dlp
from flask import Flask, render_template, request, redirect, url_for, flash
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
    YouTubeTranscriptApiException,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

from summarizer import (
    STOP_WORDS,
    summarize_text,
    tokenize_sentences,
    tokenize_words,
)

app = Flask(__name__)
app.secret_key = "dev-secret"

# Simple sqlite DB
DB_PATH = "data.db"

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

LIBRE_URL = "https://libretranslate.de/translate"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            video_id TEXT,
            title TEXT,
            summary TEXT,
            style TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


class User:
    def __init__(self, id, username):
        self.id = id
        self.username = username

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return User(row["id"], row["username"])
    return None


init_db()


def extract_youtube_id(url: str) -> str | None:
    url = url.strip()
    if not url:
        return None

    if "youtube.com" in url or "youtu.be" in url:
        parsed = urlparse(url)
        if parsed.hostname in ("www.youtube.com", "youtube.com"):
            query = parse_qs(parsed.query)
            if "v" in query:
                return query["v"][0]
            if parsed.path.startswith("/embed/"):
                return parsed.path.split("/embed/")[-1]
        if parsed.hostname == "youtu.be":
            return parsed.path.lstrip("/")

    if re.match(r"^[A-Za-z0-9_-]{11}$", url):
        return url

    return None


def fetch_video_metadata(video_id: str) -> dict:
    meta = {
        "title": None,
        "description": None,
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "watch_url": f"https://www.youtube.com/watch?v={video_id}",
    }
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "extract_flat": True}) as ydl:
            info = ydl.extract_info(meta["watch_url"], download=False)
            if info:
                meta["title"] = info.get("title")
                meta["description"] = info.get("description")
                meta["thumbnail"] = info.get("thumbnail") or meta["thumbnail"]
                meta["author"] = info.get("uploader")
    except Exception:
        pass
    return meta


def get_transcript_text(video_id: str, languages=None) -> str:
    if languages is None:
        languages = ["en", "en-US", "en-GB", "hi"]
    try:
        transcript_obj = YouTubeTranscriptApi().fetch(video_id, languages=languages)
        snippets = []
        if hasattr(transcript_obj, "to_raw_data"):
            raw = transcript_obj.to_raw_data()
            for s in raw:
                if isinstance(s, dict):
                    snippets.append(s.get("text", ""))
                else:
                    snippets.append(getattr(s, "text", ""))
        else:
            try:
                for s in transcript_obj:
                    if isinstance(s, dict):
                        snippets.append(s.get("text", ""))
                    else:
                        snippets.append(getattr(s, "text", ""))
            except TypeError:
                s = transcript_obj
                if isinstance(s, dict):
                    snippets.append(s.get("text", ""))
                else:
                    snippets.append(getattr(s, "text", ""))
        text = " ".join([t for t in snippets if t])
        return text.strip()
    except (NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApiException):
        meta = fetch_video_metadata(video_id)
        fallback = " ".join([part for part in [meta.get("title"), meta.get("description")] if part])
        return fallback.strip()


@app.route("/", methods=["GET", "POST"])
def index():
    summary = None
    error = None
    video_url = ""

    if request.method == "POST":
        video_url = request.form.get("video_url", "").strip()
        video_id = extract_youtube_id(video_url)

        if not video_id:
            error = "Please enter a valid YouTube URL or video ID."
        else:
            # For simple form submit we perform a brief summary by default
            style = request.form.get("style", "brief")
            try:
                metadata = fetch_video_metadata(video_id)
                transcript_text = get_transcript_text(video_id)
                summary = summarize_text(transcript_text, style=style)

                # save history if logged in
                if current_user.is_authenticated:
                    title = metadata.get("title") if metadata else None
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO summaries (user_id, video_id, title, summary, style, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            int(current_user.get_id()),
                            video_id,
                            title,
                            summary,
                            style,
                            datetime.utcnow().isoformat(),
                        ),
                    )
                    conn.commit()
                    conn.close()
            except NoTranscriptFound:
                error = (
                    "Transcript unavailable in English for this video. "
                    "Try a different video or add a supported language."
                )
            except YouTubeTranscriptApiException as exc:
                error = f"Transcript unavailable for this video: {exc}"
            except Exception as exc:
                error = f"Unable to process the video: {exc}"

    return render_template(
        "index.html",
        summary=summary,
        error=error,
        video_url=video_url,
    )


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('Username and password required')
            return redirect(url_for('register'))
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, generate_password_hash(password)))
            conn.commit()
            uid = cur.lastrowid
            conn.close()
            user = User(uid, username)
            login_user(user)
            return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            flash('Username already taken')
            conn.close()
            return redirect(url_for('register'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        cur = conn.cursor()
        cur.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
        row = cur.fetchone()
        conn.close()
        if row and check_password_hash(row['password_hash'], password):
            user = User(row['id'], username)
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid credentials')
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/history')
@login_required
def history():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id, video_id, title, summary, style, created_at FROM summaries WHERE user_id = ? ORDER BY id DESC', (int(current_user.get_id()),))
    rows = cur.fetchall()
    conn.close()
    return render_template('history.html', rows=rows)


@app.route('/api/metadata', methods=['POST'])
def api_metadata():
    data = request.get_json() or {}
    video = data.get('video_url') or data.get('video_id')
    video_id = extract_youtube_id(video) if video else None
    if not video_id:
        return json.dumps({'error': 'invalid video id'}), 400, {'Content-Type': 'application/json'}
    meta = fetch_video_metadata(video_id)
    try:
        o = requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json", timeout=5)
        if o.status_code == 200:
            j = o.json()
            meta['title'] = j.get('title') or meta.get('title')
            meta['author'] = j.get('author_name') or meta.get('author')
            meta['thumbnail'] = j.get('thumbnail_url') or meta.get('thumbnail')
    except Exception:
        pass
    return json.dumps(meta), 200, {'Content-Type': 'application/json'}


@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json() or {}
    video = data.get('video_url') or data.get('video_id')
    question = data.get('question', '')
    video_id = extract_youtube_id(video) if video else None
    if not video_id or not question:
        return json.dumps({'error': 'missing parameters'}), 400, {'Content-Type': 'application/json'}
    try:
        text = get_transcript_text(video_id)
        if not text:
            return json.dumps({'answer': 'No transcript or video metadata available for this link.'}), 200, {'Content-Type': 'application/json'}
        sentences = re.split(r"(?<=[.!?])\s+", text)
        q_words = set([w.lower() for w in re.findall(r"\w+", question) if w.lower() not in STOP_WORDS])
        scores = []
        for s in sentences:
            words = set([w.lower() for w in re.findall(r"\w+", s)])
            score = len(q_words & words)
            if score > 0:
                scores.append((score, s))
        scores.sort(reverse=True)
        top = [s for _, s in scores[:3]]
        answer = ' '.join(top) if top else 'No specific answer found; here is a short excerpt: ' + ' '.join(sentences[:2])
        return json.dumps({'answer': answer}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return json.dumps({'error': str(e)}), 500, {'Content-Type': 'application/json'}


@app.route('/api/quiz', methods=['POST'])
def api_quiz():
    data = request.get_json() or {}
    video = data.get('video_url') or data.get('video_id')
    video_id = extract_youtube_id(video) if video else None
    if not video_id:
        return json.dumps({'error': 'missing video id'}), 400, {'Content-Type': 'application/json'}
    try:
        text = get_transcript_text(video_id)
        sentences = tokenize_sentences(text)
        words = tokenize_words(text)
        freq = Counter(words)
        questions = []
        for i in range(3):
            if i >= len(sentences):
                break
            s = sentences[i]
            candidates = [w for w in re.findall(r"\b[a-zA-Z0-9']+\b", s) if w.lower() not in STOP_WORDS and len(w) > 3]
            if not candidates:
                continue
            answer = candidates[0]
            options = [answer]
            # pick distractors
            common = [w for w, _ in freq.most_common(20) if w.lower() != answer.lower()]
            random.shuffle(common)
            for c in common[:3]:
                options.append(c)
            random.shuffle(options)
            questions.append({'question': s.replace(answer, '_____'), 'options': options, 'answer': answer})
        return json.dumps({'questions': questions}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return json.dumps({'error': str(e)}), 500, {'Content-Type': 'application/json'}


@app.route('/api/translate', methods=['POST'])
def api_translate():
    data = request.get_json() or {}
    text = data.get('text')
    target = data.get('target', 'en')
    if not text:
        return json.dumps({'error': 'missing text'}), 400, {'Content-Type': 'application/json'}
    try:
        r = requests.post(LIBRE_URL, json={
            'q': text,
            'source': 'auto',
            'target': target,
            'format': 'text'
        }, timeout=10)
        if r.status_code == 200:
            j = r.json()
            return json.dumps({'translated': j.get('translatedText')}), 200, {'Content-Type': 'application/json'}
        return json.dumps({'error': 'translation failed'}), 500, {'Content-Type': 'application/json'}
    except Exception as e:
        return json.dumps({'error': str(e)}), 500, {'Content-Type': 'application/json'}


@app.route('/health')
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8000)
