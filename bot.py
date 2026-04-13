"""
Telegram Custom Emoji Pack Downloader Bot
==========================================
Pack link formati: https://t.me/addemoji/PackNomi
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
#  SOZLAMA
# ─────────────────────────────────────────────
BOT_TOKEN = "8788903625:AAGKSrz2F1yYMILfKi0uusIM2oCrhN1jW_k"
# ─────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def extract_pack_name(text: str) -> str | None:
    text = text.strip()
    for prefix in (
        "https://t.me/addemoji/",
        "http://t.me/addemoji/",
        "t.me/addemoji/",
    ):
        if text.lower().startswith(prefix.lower()):
            return text[len(prefix):].split("?")[0].strip("/")

    if " " not in text and "/" not in text and text:
        return text

    return None


async def pack_to_zip(pack_name: str, bot) -> tuple:
    try:
        sticker_set = await bot.get_sticker_set(pack_name)
    except Exception as e:
        return None, f"❌ Pack topilmadi: `{pack_name}`\n\nXato: {e}", 0, 0

    emojis = sticker_set.stickers
    pack_title = sticker_set.title
    is_animated = sticker_set.is_animated
    is_video = sticker_set.is_video

    if is_animated:
        ext = "tgs"
    elif is_video:
        ext = "webm"
    else:
        ext = "webp"

    zip_buffer = io.BytesIO()
    failed = 0

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i, emoji in enumerate(emojis, start=1):
            try:
                file_obj = await bot.get_file(emoji.file_id)
                file_url = file_obj.file_path

                resp = requests.get(file_url, timeout=30)
                resp.raise_for_status()

                safe_emoji = "".join(
                    c if (c.isascii() and c not in r'\/:*?"<>|') else "_"
                    for c in (emoji.emoji or "emoji")
                )
                filename = f"{i:03d}_{safe_emoji}.{ext}"
                zf.writestr(filename, resp.content)
                logger.info("OK %d/%d — %s", i, len(emojis), filename)

            except Exception as e:
                logger.warning("SKIP emoji %d: %s", i, e)
                failed += 1

    # MUHIM: buffer boshiga qaytish
    zip_buffer.seek(0)
    return zip_buffer, pack_title, len(emojis), failed


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
        "1️⃣ Telegram'da emoji packni oching\n"
        "2️⃣ Pack havolasini nusxalang:\n"
        "   `https://t.me/addemoji/PackNomi`\n"
        "3️⃣ Shu botga yuboring\n"
        "4️⃣ Men barcha emojilarni ZIP qilib beraman ✅\n\n"
        "💡 *Fayl turlari:*\n"
        "• Static emoji → `.webp`\n"
        "• Animated emoji → `.tgs`\n"
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
        f"⏳ `{pack_name}` yuklanmoqda... Biroz kuting.",
        parse_mode="Markdown",
    )

    zip_buffer, pack_title_or_err, total, failed = await pack_to_zip(
        pack_name, context.bot
    )

    if zip_buffer is None:
        await msg.edit_text(pack_title_or_err, parse_mode="Markdown")
        return

    pack_title = pack_title_or_err
    success = total - failed

    await msg.edit_text(
        f"📤 Yuborilmoqda... ({success} ta emoji)",
        parse_mode="Markdown",
    )

    try:
        caption = f"📦 *{pack_title}*\n✅ {success} ta emoji yuklandi"
        if failed:
            caption += f"\n⚠️ {failed} ta yuklanmadi"

        await update.message.reply_document(
            document=zip_buffer,
            filename=f"{pack_name}.zip",
            caption=caption,
            parse_mode="Markdown",
        )
        await msg.delete()

    except Exception as e:
        logger.error("Yuborishda xato: %s", e)
        await msg.edit_text(
            f"❌ Faylni yuborishda xato:\n`{e}`\n\n"
            "Pack juda katta bo'lishi mumkin (50MB limit).",
            parse_mode="Markdown",
        )


def main() -> None:
    if BOT_TOKEN == "BU_YERGA_BOT_TOKENINGIZNI_KIRITING":
        print("❌ XATO: BOT_TOKEN ni o'zgartiring!")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot ishga tushdi! To'xtatish uchun Ctrl+C bosing.")
    app.run_polling()


if __name__ == "__main__":
    main()
