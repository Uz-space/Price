"""
Telegram Custom Emoji Pack Downloader Bot
==========================================
Bu bot custom emoji pack linkini qabul qilib,
barcha emojilarni ZIP fayl qilib yuboradi.

O'rnatish:
    pip install python-telegram-bot requests

Ishlatish:
    1. @BotFather dan bot yarating va TOKEN oling
    2. BOT_TOKEN ni o'zingiznikiga almashtiring
    3. python emoji_bot.py

Pack link formati:
    https://t.me/addemoji/PackNomi
"""

from __future__ import annotations

import io
import zipfile
import logging
import requests

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ─────────────────────────────────────────────
#  SOZLAMA — faqat shu qatorni o'zgartiring!
# ─────────────────────────────────────────────
BOT_TOKEN = "8788903625:AAGKSrz2F1yYMILfKi0uusIM2oCrhN1jW_k"
# ─────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  YORDAMCHI FUNKSIYALAR
# ──────────────────────────────────────────────

def extract_pack_name(text: str) -> str | None:
    """
    Custom emoji pack linkidan nom chiqaradi.

    Qo'llab-quvvatlangan formatlar:
      https://t.me/addemoji/PackNomi
      t.me/addemoji/PackNomi
      PackNomi  (faqat ism)
    """
    text = text.strip()
    for prefix in (
        "https://t.me/addemoji/",
        "http://t.me/addemoji/",
        "t.me/addemoji/",
    ):
        if text.lower().startswith(prefix.lower()):
            return text[len(prefix):].split("?")[0].strip("/")

    # Faqat ism berilsa
    if " " not in text and "/" not in text and text:
        return text

    return None


async def pack_to_zip(pack_name: str, bot) -> tuple:
    """
    Custom emoji packni yuklab ZIP bytes qaytaradi.
    Qaytadi: (zip_bytes, pack_title, jami, xato_soni) yoki (None, xato_msg, 0, 0)
    """
    try:
        # Custom emoji pack olish
        sticker_set = await bot.get_sticker_set(pack_name)
    except Exception as e:
        return None, f"❌ Pack topilmadi: `{pack_name}`\n\nXato: {e}", 0, 0

    emojis = sticker_set.stickers
    pack_title = sticker_set.title
    is_animated = sticker_set.is_animated
    is_video = sticker_set.is_video

    # Fayl kengaytmasi aniqlash
    if is_animated:
        ext = "tgs"       # Animated emoji (Lottie)
    elif is_video:
        ext = "webm"      # Video emoji
    else:
        ext = "webp"      # Static emoji

    zip_buffer = io.BytesIO()
    failed = 0

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, emoji in enumerate(emojis, start=1):
            try:
                file_obj = await bot.get_file(emoji.file_id)
                file_url = file_obj.file_path

                resp = requests.get(file_url, timeout=30)
                resp.raise_for_status()

                # Fayl nomi — emoji belgisi + raqam
                safe_emoji = "".join(
                    c if (c.isascii() and c not in r'\/:*?"<>|') else "_"
                    for c in (emoji.emoji or "emoji")
                )
                filename = f"{i:03d}_{safe_emoji}.{ext}"
                zf.writestr(filename, resp.content)

            except Exception as e:
                logger.warning("Emoji %d yuklanmadi: %s", i, e)
                failed += 1

    return zip_buffer.getvalue(), pack_title, len(emojis), failed


# ──────────────────────────────────────────────
#  HANDLERLAR
# ──────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Salom! Men *Custom Emoji Pack Yuklovchi Bot* man.\n\n"
        "📎 Menga emoji pack linkini yuboring:\n"
        "`https://t.me/addemoji/PackNomi`\n\n"
        "Men butun packni *ZIP fayl* qilib beraman! 🗂\n\n"
        "/help — ko'proq ma'lumot",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 *Yordam*\n\n"
        "1️⃣ Telegram'da istalgan custom emoji packni oching\n"
        "2️⃣ Pack havolasini nusxalang:\n"
        "   `https://t.me/addemoji/PackNomi`\n"
        "3️⃣ Shu botga yuboring\n"
        "4️⃣ Men barcha emojilarni ZIP qilib beraman ✅\n\n"
        "💡 *Fayl turlari:*\n"
        "• Static emoji → `.webp`\n"
        "• Animated emoji → `.tgs` (Lottie)\n"
        "• Video emoji → `.webm`",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    pack_name = extract_pack_name(text)

    if not pack_name:
        await update.message.reply_text(
            "⚠️ Noto'g'ri format!\n\n"
            "Pack linkini yuboring:\n"
            "`https://t.me/addemoji/PackNomi`",
            parse_mode="Markdown",
        )
        return

    msg = await update.message.reply_text(
        f"⏳ `{pack_name}` pack yuklanmoqda... Biroz kuting.",
        parse_mode="Markdown",
    )

    zip_bytes, pack_title_or_err, total, failed = await pack_to_zip(
        pack_name, context.bot
    )

    if zip_bytes is None:
        await msg.edit_text(pack_title_or_err, parse_mode="Markdown")
        return

    pack_title = pack_title_or_err
    success = total - failed

    await msg.edit_text(
        f"✅ Tayyor! `{pack_title}` — {success}/{total} emoji yuklandi.\n"
        f"📦 ZIP fayl tayyorlanmoqda...",
        parse_mode="Markdown",
    )

    zip_file = io.BytesIO(zip_bytes)
    zip_file.name = f"{pack_name}.zip"

    await update.message.reply_document(
        document=zip_file,
        filename=f"{pack_name}.zip",
        caption=(
            f"📦 *{pack_title}*\n"
            f"✅ {success} ta emoji\n"
            f"{'⚠️ ' + str(failed) + ' ta yuklanmadi' if failed else ''}"
        ),
        parse_mode="Markdown",
    )

    await msg.delete()


# ──────────────────────────────────────────────
#  BOTNI ISHGA TUSHIRISH
# ──────────────────────────────────────────────

def main() -> None:
    if BOT_TOKEN == "BU_YERGA_BOT_TOKENINGIZNI_KIRITING":
        print("❌ XATO: BOT_TOKEN ni o'zgartiring!")
        print("   emoji_bot.py faylini oching va BOT_TOKEN ga tokeningizni kiriting.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot ishga tushdi! To'xtatish uchun Ctrl+C bosing.")
    app.run_polling()


if __name__ == "__main__":
    main()
