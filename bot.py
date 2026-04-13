import telebot
import os

TOKEN = "8788903625:AAFJynv6xVRU3nh4mSuqmHcIY2ZAwtkNUTk"
bot = telebot.TeleBot(TOKEN)


def pack_name(user_id):
    return f"clone_{user_id}_bot"


@bot.message_handler(func=lambda m: True)
def clone(message):
    text = message.text

    if "t.me/addstickers/" not in text:
        bot.reply_to(message, "❌ Pack link yubor")
        return

    pack = text.split("/")[-1]
    user_id = message.from_user.id

    stickerset = bot.get_sticker_set(pack)

    new_pack = pack_name(user_id)

    created = False

    for i, sticker in enumerate(stickerset.stickers):
        file_info = bot.get_file(sticker.file_id)
        file = bot.download_file(file_info.file_path)

        ext = file_info.file_path.split(".")[-1]
        filename = f"temp_{i}.{ext}"

        with open(filename, "wb") as f:
            f.write(file)

        emoji = sticker.emoji or "😀"

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

        os.remove(filename)

    bot.send_message(
        message.chat.id,
        f"✅ Tayyor!\nhttps://t.me/addstickers/{new_pack}"
    )


bot.infinity_polling()
