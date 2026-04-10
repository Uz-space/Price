import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8134986426:AAF_Np2hSvspbrBfcsjsr9Szd77yb0WiIBI"

bot = Bot(token=TOKEN)
dp = Dispatcher()

confirm_emoji = "5323765959444435759"
cancel_emoji = "5325998693898293667"


@dp.message(commands=["start"])
async def start(message: types.Message):

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"<tg-emoji emoji-id='{confirm_emoji}'></tg-emoji> Tasdiqlash",
                callback_data="confirm"
            ),
            InlineKeyboardButton(
                text=f"<tg-emoji emoji-id='{cancel_emoji}'></tg-emoji> Bekor qilish",
                callback_data="cancel"
            )
        ]
    ])

    await message.answer(
        "Emoji tugmalar bilan xabar:",
        reply_markup=kb,
        parse_mode="HTML"
    )


@dp.callback_query()
async def callback(call: types.CallbackQuery):

    if call.data == "confirm":
        await call.answer("Tasdiqlandi!")
        await call.message.answer("Siz tasdiqladingiz!")

    elif call.data == "cancel":
        await call.answer("Bekor qilindi!")
        await call.message.answer("Siz bekor qildingiz!")


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
