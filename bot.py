import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode

TOKEN = "YOUR_BOT_TOKEN"

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


def pack_name(user_id):
    return f"clone_{user_id}_by_bot"


def pack_title(user_id):
    return f"Clone Pack {user_id}"


def extract_name(link: str):
    return link.split("/")[-1]


@dp.message(F.text)
async def clone_pack(message: Message):
    text = message.text.strip()

    if "t.me/addstickers/" not in text:
        await message.answer("❌ Sticker pack link yubor:\nhttps://t.me/addstickers/PackName")
        return

    old_pack_name = extract_name(text)
    user_id = message.from_user.id

    try:
        old_set = await bot.get_sticker_set(old_pack_name)
    except:
        await message.answer("❌ Pack topilmadi")
        return

    new_pack = pack_name(user_id)

    created = False

    for i, sticker in enumerate(old_set.stickers):
        file = await bot.get_file(sticker.file_id)
        data = await bot.download_file(file.file_path)

        ext = file.file_path.split(".")[-1]
        filename = f"temp_{i}.{ext}"

        with open(filename, "wb") as f:
            f.write(data.read())

        emoji = sticker.emoji or "😀"

        try:
            if not created:
                await bot.create_new_sticker_set(
                    user_id=user_id,
                    name=new_pack,
                    title=pack_title(user_id),
                    stickers=[{
                        "sticker": open(filename, "rb"),
                        "emoji_list": [emoji]
                    }]
                )
                created = True
            else:
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=new_pack,
                    sticker={
                        "sticker": open(filename, "rb"),
                        "emoji_list": [emoji]
                    }
                )
        except Exception as e:
            await message.answer(f"❌ Xatolik: {e}")
            os.remove(filename)
            return

        os.remove(filename)

    await message.answer(
        f"✅ Clone tayyor!\n"
        f"📦 Pack: {new_pack}\n"
        f"🔗 https://t.me/addstickers/{new_pack}"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
