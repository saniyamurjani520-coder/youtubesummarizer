# YouTube Summarizer

A polished Flask app that accepts any YouTube link, tries to fetch its transcript, and generates a concise summary with useful companion features such as metadata, chat, quiz generation, translation, history, and auth.

## Included features
- Paste any YouTube URL or video ID
- Fetch transcript when available
- Fallback to video title/description metadata when captions are missing
- Brief, detailed, and bullet-point summaries
- Thumbnail and metadata display
- Chat-style Q&A over the transcript
- Quiz generation
- Translation support
- Saved summary history (for signed-in users)
- Responsive UI

## Setup
1. Create and activate a Python virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

## Run locally
```powershell
python main.py
```

Then open http://127.0.0.1:8000 in your browser.

## Notes
- Some videos do not expose subtitles or transcripts, so the app uses metadata as a fallback.
- The translation endpoint uses a public LibreTranslate service and may be slower on some requests.
