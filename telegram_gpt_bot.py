#!/usr/bin/env python3
# Telegram GPT Bot - Extended for GIC Assistant (Mr.P)
# Features:
# - Telegram <-> OpenAI chat
# - save media and documents locally (or to S3/GCS)
# - generate PDF report (ReportLab)
# - parse uploaded PDF (pdfminer.six placeholder)
# - store case metadata in PostgreSQL via SQLAlchemy
#
# Configure via environment variables:
# TELEGRAM_BOT_TOKEN, OPENAI_API_KEY
# STORAGE_BACKEND = "local" | "s3" | "gcs"
# S3_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
# GCS_BUCKET, GOOGLE_APPLICATION_CREDENTIALS (path)
# DATABASE_URL (postgres, e.g., postgresql://user:pass@host:5432/dbname)
# MEDIA_DIR (default /tmp/telegram_media)

import os
import time
import logging
from collections import deque
from typing import Dict
import telebot
import openai

# Optional libs (import when available)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except Exception:
    reportlab = None

try:
    from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
except Exception:
    create_engine = None

# storage placeholders
USE_S3 = os.getenv("STORAGE_BACKEND", "local") == "s3"
USE_GCS = os.getenv("STORAGE_BACKEND", "local") == "gcs"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MEDIA_DIR = os.getenv("MEDIA_DIR", "/tmp/telegram_media")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("TELEGRAM_BOT_TOKEN and OPENAI_API_KEY must be set in env")

openai.api_key = OPENAI_API_KEY

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_gpt_bot_ext")

# Simple DB model (if SQLAlchemy available)
Base = None
SessionLocal = None
if create_engine:
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine)
        Base = declarative_base()
        class Case(Base):
            __tablename__ = "cases"
            id = Column(Integer, primary_key=True, index=True)
            tg_user = Column(String(64))
            title = Column(String(256))
            description = Column(Text)
            media_path = Column(String(1024))
            report_pdf = Column(String(1024))
            created_at = Column(DateTime)
        Base.metadata.create_all(bind=engine)
    else:
        logger.info("No DATABASE_URL provided; DB features disabled.")

# In-memory context
user_context: Dict[int, deque] = {}
def ensure_context(uid):
    if uid not in user_context:
        user_context[uid] = deque(maxlen=24)

def push_user(uid, text):
    ensure_context(uid)
    user_context[uid].append({"role":"user","content":text})

def push_assistant(uid, text):
    ensure_context(uid)
    user_context[uid].append({"role":"assistant","content":text})

SYSTEM_PROMPT = (
    "Bạn là trợ lý chuyên gia giám định bảo hiểm xe cơ giới cho Mr.P. "
    "Trả lời ngắn gọn, chính xác, hướng nghiệp vụ. Khi cần báo cáo, tạo PDF tóm tắt."
)

@bot.message_handler(commands=['start'])
def cmd_start(m):
    ensure_context(m.from_user.id)
    bot.reply_to(m, "Chào, tôi là trợ lý giám định. Gửi ảnh/biên bản để tôi phân tích.")

@bot.message_handler(commands=['newcase'])
def cmd_newcase(m):
    # create a simple case note
    uid = m.from_user.id
    text = " ".join(m.text.split()[1:]) if len(m.text.split())>1 else ""
    title = text or f"Vụ {int(time.time())}"
    # Save to DB if available
    if SessionLocal:
        db = SessionLocal()
        from datetime import datetime
        c = Case(tg_user=str(uid), title=title, description="", media_path="", report_pdf="", created_at=datetime.utcnow())
        db.add(c); db.commit(); db.refresh(c)
        bot.reply_to(m, f"Tạo vụ việc #{c.id} - {title}")
    else:
        bot.reply_to(m, f"Tạo vụ việc (local) - {title}")

@bot.message_handler(content_types=['photo'])
def handle_photo(m):
    uid = m.from_user.id
    file_id = m.photo[-1].file_id
    finfo = bot.get_file(file_id)
    path = finfo.file_path
    os.makedirs(MEDIA_DIR, exist_ok=True)
    local = os.path.join(MEDIA_DIR, f"{uid}_{file_id}.jpg")
    bot.download_file(path, local)
    bot.reply_to(m, "Ảnh đã lưu. Mô tả thêm hoàn cảnh để tôi phân tích.")
    # attach to context
    push_user(uid, f"[image:{local}]")

@bot.message_handler(content_types=['document'])
def handle_document(m):
    uid = m.from_user.id
    doc = m.document
    fname = doc.file_name
    finfo = bot.get_file(doc.file_id)
    os.makedirs(MEDIA_DIR, exist_ok=True)
    local = os.path.join(MEDIA_DIR, f"{uid}_{doc.file_id}_{fname}")
    bot.download_file(finfo.file_path, local)
    bot.reply_to(m, f"Tài liệu {fname} đã lưu.")
    # simple PDF parse placeholder
    if fname.lower().endswith(".pdf"):
        bot.reply_to(m, "Bắt đầu trích xuất nội dung PDF (nếu cấu hình).")
        # Here you can call pdfminer / pypdf to extract text and parse fields
        # For now we just note it in context
        push_user(uid, f"[pdf:{local}]")

@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_text(m):
    uid = m.from_user.id
    text = m.text.strip()
    push_user(uid, text)
    messages = [{"role":"system","content":SYSTEM_PROMPT}] + list(user_context[uid])
    try:
        resp = openai.ChatCompletion.create(model="gpt-5", messages=messages, temperature=0.2)
        assistant_text = resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.exception("OpenAI error")
        bot.reply_to(m, "Lỗi khi kết nối OpenAI.")
        return
    push_assistant(uid, assistant_text)
    # If user asked "tạo báo cáo" generate PDF
    if "tạo báo cáo" in text.lower() or "báo cáo" in text.lower():
        report_path = generate_pdf_report(uid, text, assistant_text)
        bot.reply_to(m, f"Báo cáo đã tạo: {report_path}")
    else:
        bot.reply_to(m, assistant_text)

def generate_pdf_report(uid, query_text, assistant_text):
    os.makedirs(MEDIA_DIR, exist_ok=True)
    pdf_path = os.path.join(MEDIA_DIR, f"report_{uid}_{int(time.time())}.pdf")
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(pdf_path, pagesize=A4)
        c.setFont("Helvetica", 12)
        c.drawString(50, 800, "Báo cáo giám định - GIC Assistant")
        c.drawString(50, 780, f"Người dùng: {uid}")
        c.drawString(50, 760, "Nội dung yêu cầu:")
        c.drawString(60, 740, query_text[:1000])
        c.drawString(50, 700, "Phân tích:")
        lines = assistant_text.splitlines()
        y = 680
        for line in lines:
            c.drawString(60, y, line[:120])
            y -= 14
            if y < 100:
                c.showPage(); y = 800
        c.showPage(); c.save()
    except Exception:
        # fallback to text file
        with open(pdf_path + ".txt", "w", encoding="utf-8") as f:
            f.write("Báo cáo giám định\\n\\n")
            f.write(f"Người dùng: {uid}\\n\\n")
            f.write("Yêu cầu:\\n")
            f.write(query_text + "\\n\\n")
            f.write("Phân tích:\\n")
            f.write(assistant_text + "\\n")
        pdf_path = pdf_path + ".txt"
    return pdf_path

if __name__ == "__main__":
    logger.info("Bot starting...")
    bot.infinity_polling()
