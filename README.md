# Telegram GPT Bot - Extended (GIC Assistant)

This package includes an extended Telegram bot with:
- Save media/docs (local, S3, or GCS)
- Generate PDF report (ReportLab)
- Parse PDFs (pdfminer.six)
- Store case metadata in PostgreSQL (SQLAlchemy)

## Quick start (local test)
1. Install:
   pip install -r requirements.txt

2. Set env vars:
   export TELEGRAM_BOT_TOKEN="..."
   export OPENAI_API_KEY="..."
   export STORAGE_BACKEND="local"   # or 's3' or 'gcs'
   export MEDIA_DIR="/tmp/telegram_media"
   # For Postgres:
   export DATABASE_URL="postgresql://user:pass@host:5432/db"

3. Run:
   python telegram_gpt_bot.py

## Deploy (Render / Heroku)
- Push repo to GitHub.
- On Render, create a Web Service, connect repo.
- Set Environment Variables on Render (TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, DATABASE_URL if used).
- Start Command: python telegram_gpt_bot.py

## Storage options
- Local: files saved to MEDIA_DIR.
- S3: configure AWS credentials & S3 bucket, set STORAGE_BACKEND=s3.
- GCS: configure GOOGLE_APPLICATION_CREDENTIALS & bucket, set STORAGE_BACKEND=gcs.

## PDF generation
- Implemented with ReportLab. If ReportLab not installed, bot will fallback to text file.

## PDF parsing
- Placeholder for pdfminer.six parsing; customize extraction rules for CSGT forms.

## Database
- SQLAlchemy model provided (simple Case table). Requires DATABASE_URL.

## Security
- Do NOT commit secrets to GitHub.
- Use Render environment variables or similar to store keys.
