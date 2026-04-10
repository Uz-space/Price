import telebot
import requests

TOKEN = "8134986426:AAF_Np2hSvspbrBfcsjsr9Szd77yb0WiIBI"  # O'z tokeningizni yozing
bot = telebot.TeleBot(TOKEN)

# Premium emoji ID lar (sizdagilar)
emoji_id_test = {
    "BTC": "5323765959444435759",
    "ETH": "5325998693898293667"
}

# Oddiy emojilar
normal_emoji = {
    "BTC": "🟠",
    "ETH": "💙"
}

@bot.message_handler(commands=['test'])
def test(message):
    chat_id = message.chat.id
    
    # 1-test: Oddiy matn
    bot.send_message(chat_id, "1-test: Oddiy matn ishlayapti ✅")
    
    # 2-test: Oddiy emoji
    bot.send_message(chat_id, f"2-test: Oddiy emoji {normal_emoji['BTC']} BTC")
    
    # 3-test: Premium emoji (ID bilan)
    try:
        premium_msg = f"3-test: Premium emoji <tg-emoji emoji-id='{emoji_id_test['BTC']}'>🙂</tg-emoji> BTC"
        bot.send_message(chat_id, premium_msg, parse_mode="HTML")
    except Exception as e:
        bot.send_message(chat_id, f"3-test: Premium emoji xato - {e}")
    
    # 4-test: Binance API
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
        data = r.json()
        price = data['price']
        bot.send_message(chat_id, f"4-test: BTC narxi = ${price} ✅")
    except Exception as e:
        bot.send_message(chat_id, f"4-test: API xato - {e}")
    
    # 5-test: Sizning ID laringiz bilan
    for coin, emoji_id in emoji_id_test.items():
        test_msg = f"5-test: {coin} emoji ID: {emoji_id}\n<tg-emoji emoji-id='{emoji_id}'>🔵</tg-emoji> Bu emoji ko'rinadimi?"
        bot.send_message(chat_id, test_msg, parse_mode="HTML")

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 /test yozing - hamma narsani tekshiramiz")

print("Test bot ishga tushdi...")
bot.infinity_polling()
