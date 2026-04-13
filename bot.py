import telebot
import os

TOKEN = "8788903625:AAFJynv6xVRU3nh4mSuqmHcIY2ZAwtkNUTk"
bot = telebot.TeleBot(TOKEN)


def extract_pack(text: str):
    text = text.strip()
    if "t.me/addstickers/" not in text:
        return None

    pack = text.split("t.me/addstickers/")[-1]
    pack = pack.split("?")[0]
    return pack.strip()


def pack_name(user_id):
    return f"clone_{user_id}_bot"


@bot.message_handler(func=lambda m: True)
def clone(message):
    text = message.text

    pack = extract_pack(text)

    if not pack:
        bot.reply_to(message, "❌ Sticker pack link yubor:\nhttps://t.me/addstickers/PackName")
        return

    user_id = message.from_user.id

    try:
        stickerset = bot.get_sticker_set(pack)
    except:
        bot.reply_to(message, "❌ Pack topilmadi")
        return

    new_pack = pack_name(user_id)

    created = False

    bot.send_message(message.chat.id, "⏳ Clone boshlandi...")

    for i, sticker in enumerate(stickerset.stickers):
        file_info = bot.get_file(sticker.file_id)
        file_bytes = bot.download_file(file_info.file_path)

        ext = file_info.file_path.split(".")[-1]
        filename = f"temp_{i}.{ext}"

        with open(filename, "wb") as f:
            f.write(file_bytes)

        emoji = sticker.emoji or "😀"

        try:
            with open(filename, "rb") as f:
                if not created:
                    bot.create_new_sticker_set(
                        user_id,
                        new_pack,
                        f"Clone Pack {user_id}",
                        stickers=[telebot.types.InputSticker(f, emoji)]
                    )
                    created = True
                else:
                    bot.add_sticker_to_set(
                        user_id,
                        new_pack,
                        telebot.types.InputSticker(f, emoji)
                    )
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {e}")
            os.remove(filename)
            return

        os.remove(filename)

    bot.send_message(
        message.chat.id,
        f"✅ Done!\nhttps://t.me/addstickers/{new_pack}"
    )


bot.infinity_polling()
