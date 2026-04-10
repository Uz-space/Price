import telebot
import requests
import time
from datetime import datetime

TOKEN = "8134986426:AAF_Np2hSvspbrBfcsjsr9Szd77yb0WiIBI"  # O'zgartiring
bot = telebot.TeleBot(TOKEN)

interval = 15  # sekund

coins = {
    "BTC":"BTCUSDT",
    "ETH":"ETHUSDT",
    "BNB":"BNBUSDT",
    "SOL":"SOLUSDT",
    "LTC":"LTCUSDT",
    "TON":"TONUSDT",
    "TRX":"TRXUSDT",
    "DOGE":"DOGEUSDT"
}

# Custom emoji ID (Premium foydalanuvchi bo'lsa ko'rinadi)
emoji_id = {
    "BTC":"5215277894456089919",
    "ETH":"5215469686220688535",
    "BNB":"5215501052366852398",
    "SOL":"5215644439850028163",
    "LTC":"5215397251597243962",
    "TON":"5215541953340410399",
    "TRX":"5215676493190960888",
    "DOGE":"5215580724010193095"
}

user_messages = {}  # chat_id: message_id

def get_prices():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=5)
        data = r.json()
        prices = {}
        for item in data:
            for coin,symbol in coins.items():
                if item["symbol"] == symbol:
                    prices[coin] = float(item["price"])
        return prices
    except:
        return {}

def build_message(prices):
    t = datetime.now().strftime("%H:%M:%S")
    text = "<b>💰 AlphaCryptoPrice</b>\n\n"
    for coin in coins:
        price = prices.get(coin,0)
        icon = f"<tg-emoji emoji-id='{emoji_id[coin]}'>🙂</tg-emoji>"
        text += f"{icon} {coin} | ${price:,.2f} | {t}\n"
    text += f"\n🔄 Auto Update: {interval} sec"
    return text

# /start komandasi
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    prices = get_prices()
    msg = build_message(prices)
    sent = bot.send_message(chat_id, msg, parse_mode="HTML")
    user_messages[chat_id] = sent.message_id

    # Auto update
    def updater():
        while True:
            prices = get_prices()
            msg = build_message(prices)
            try:
                bot.edit_message_text(msg, chat_id, user_messages[chat_id], parse_mode="HTML")
            except:
                pass
            time.sleep(interval)
    
    import threading
    threading.Thread(target=updater).start()

# Botni ishga tushurish
bot.infinity_polling()
