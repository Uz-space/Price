import telebot
import requests
import time
from datetime import datetime
import threading

TOKEN = "8134986426:AAF_Np2hSvspbrBfcsjsr9Szd77yb0WiIBI"
bot = telebot.TeleBot(TOKEN)

interval = 5

coins = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "SOL": "SOLUSDT",
    "LTC": "LTCUSDT",
    "TON": "TONUSDT",
    "TRX": "TRXUSDT",
    "DOGE": "DOGEUSDT"
}

# SIZNING PREMIUM EMOJI ID LARINGIZ
custom_emoji_ids = {
    "BTC": "5323765959444435759",   # Siz berdingiz
    "ETH": "5325998693898293667",   # Siz berdingiz
    "BNB": "5215501052366852398",   # Standart (o'zgartirishingiz mumkin)
    "SOL": "5215644439850028163",   # Standart
    "LTC": "5215397251597243962",   # Standart
    "TON": "5215541953340410399",   # Standart
    "TRX": "5215676493190960888",   # Standart
    "DOGE": "5215580724010193095"   # Standart
}

user_messages = {}

def get_prices():
    prices = {}
    for coin, symbol in coins.items():
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                prices[coin] = float(data['price'])
                print(f"{coin}: ${prices[coin]}")
            else:
                prices[coin] = 0
        except Exception as e:
            print(f"{coin} xato: {e}")
            prices[coin] = 0
        time.sleep(0.1)
    return prices

def build_message(prices):
    t = datetime.now().strftime("%H:%M:%S")
    text = "<b>💰 AlphaCryptoPrice PRO</b>\n\n"
    
    for coin in coins:
        price = prices.get(coin, 0)
        emoji_id = custom_emoji_ids.get(coin, "")
        
        # Premium emoji
        icon = f"<tg-emoji emoji-id='{emoji_id}'>💎</tg-emoji>"
        
        if price > 0:
            text += f"{icon} {coin} | ${price:,.2f} | {t}\n\n"
        else:
            text += f"{icon} {coin} | ⚠️ Ma'lumot yo'q | {t}\n\n"
    
    text += f"🔄 Auto Update: {interval} sec\n"
    text += f"👥 Users: {len(user_messages)}"
    return text

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    
    msg1 = bot.send_message(chat_id, "🟢 Yuklanmoqda...")
    prices = get_prices()
    msg = build_message(prices)
    
    try:
        bot.delete_message(chat_id, msg1.message_id)
    except:
        pass
    
    sent = bot.send_message(chat_id, msg, parse_mode="HTML")
    user_messages[chat_id] = sent.message_id

    def updater():
        while True:
            prices = get_prices()
            msg = build_message(prices)
            try:
                bot.edit_message_text(msg, chat_id, user_messages[chat_id], parse_mode="HTML")
            except Exception as e:
                print(f"Edit xato: {e}")
            time.sleep(interval)

    threading.Thread(target=updater, daemon=True).start()

@bot.message_handler(commands=['test_emoji'])
def test_emoji(message):
    """Premium emoji test"""
    text = f"""
<b>Premium Emoji Test</b>

BTC ID: {custom_emoji_ids['BTC']}
<tg-emoji emoji-id='{custom_emoji_ids['BTC']}'>💰</tg-emoji> BTC

ETH ID: {custom_emoji_ids['ETH']}
<tg-emoji emoji-id='{custom_emoji_ids['ETH']}'>💰</tg-emoji> ETH

<i>Agar bu emojilar ko'rinmasa, sizda Telegram Premium yo'q yoki ID noto'g'ri</i>
"""
    bot.send_message(message.chat.id, text, parse_mode="HTML")

print("✅ Bot ishga tushdi!")
print(f"BTC ID: {custom_emoji_ids['BTC']}")
print(f"ETH ID: {custom_emoji_ids['ETH']}")
bot.infinity_polling()
