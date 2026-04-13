import telebot
import os
import zipfile
import asyncio
from telethon import TelegramClient
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import InputStickerSetShortName

# ===== BOT =====
TOKEN = "8788903625:AAFJynv6xVRU3nh4mSuqmHcIY2ZAwtkNUTk"
bot = telebot.TeleBot(TOKEN)

# ===== TELETHON =====
api_id = 36092552
api_hash = "9d18a707a797f12f1c31587d3cc6e0d7"
client = TelegramClient("session", api_id, api_hash)


def extract_pack(link: str):
    return link.split("/")[-1].strip()


async def download_pack(pack_name: str):
    result = await client(GetStickerSetRequest(
        stickerset=InputStickerSetShortName(short_name=pack_name),
        hash=0
    ))
    return result.documents


def process_pack(link, chat_id):
    pack = extract_pack(link)

    async def run():
        docs = await download_pack(pack)

        os.makedirs("tmp", exist_ok=True)

        files = []

        for i, doc in enumerate(docs):
            path = await client.download_media(doc, file=f"tmp/{i}")

            emoji = ""
            if hasattr(doc, "attributes"):
                for a in doc.attributes:
                    if hasattr(a, "alt"):
                        emoji = a.alt

            ext = "webp"
            new_name = f"tmp/{i}_{emoji}.{ext}"

            os.rename(path, new_name)
            files.append(new_name)

        zip_name = f"{pack}.zip"

        with zipfile.ZipFile(zip_name, "w") as z:
            for f in files:
                z.write(f)

        bot.send_document(chat_id, open(zip_name, "rb"), caption="✅ Pack export tayyor")

        # cleanup
        for f in files:
            os.remove(f)
        os.remove(zip_name)

    asyncio.run(run())


@bot.message_handler(func=lambda m: True)
def handler(message):
    text = message.text.strip()

    if "t.me/add" not in text:
        bot.reply_to(message, "❌ Link yubor:\nhttps://t.me/addstickers/...")
        return

    bot.send_message(message.chat.id, "⏳ Yuklanmoqda...")

    try:
        process_pack(text, message.chat.id)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xatolik: {e}")


client.start()
bot.infinity_polling()
