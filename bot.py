import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8134986426:AAF_Np2hSvspbrBfcsjsr9Szd77yb0WiIBI"
bot = telebot.TeleBot(TOKEN)

# Emoji ID’lar
confirm_emoji_id = "5323765959444435759"
cancel_emoji_id = "5325998693898293667"

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id

    # Avval premium emojili xabar yuboramiz (tugma uchun emas)
    emoji_text = f"""
<b>Premium Emoji Test</b>

✅ Tasdiqlash: <tg-emoji emoji-id='{confirm_emoji_id}'>✅</tg-emoji>
❌ Bekor qilish: <tg-emoji emoji-id='{cancel_emoji_id}'>❌</tg-emoji>
"""

    bot.send_message(chat_id, emoji_text, parse_mode="HTML")

    # Oddiy matnli tugmalar (HTML ishlatib bo'lmaydi)
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")
    )

    bot.send_message(chat_id, "Quyidagi tugmalardan birini bosing:", reply_markup=kb)

# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == "confirm":
        bot.answer_callback_query(call.id, "✅ Tasdiqladingiz!")
        bot.send_message(call.message.chat.id, "Siz tasdiqladingiz!")
    elif call.data == "cancel":
        bot.answer_callback_query(call.id, "❌ Bekor qildingiz!")
        bot.send_message(call.message.chat.id, "Siz bekor qildingiz!")

print("✅ Bot ishga tushdi!")
bot.infinity_polling()
