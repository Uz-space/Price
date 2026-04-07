import telebot
import requests
import time
from datetime import datetime
import threading

TOKEN = "8134986426:AAF_Np2hSvspbrBfcsjsr9Szd77yb0WiIBI"
DEFAULT_INTERVAL = 10

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

coins = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "SOL": "SOLUSDT",
    "LTC": "LTCUSDT",
    "TON": "TONUSDT",
    "TRX": "TRXUSDT",
    "DOGE": "DOGEUSDT",
}

emoji_id = {
    "BTC": "5215277894456089919",
    "ETH": "5215469686220688535",
    "BNB": "5215501052366852398",
    "SOL": "5215644439850028163",
    "LTC": "5215397251597243962",
    "TON": "5215541953340410399",
    "TRX": "5215676493190960888",
    "DOGE": "5215580724010193095",
}

users = {}
lock = threading.Lock()

# ✅ API (24h qaytdi + fallback)
def get_prices():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/24hr", timeout=5)
        data = r.json()
        result = {}

        for item in data:
            for coin, symbol in coins.items():
                if item["symbol"] == symbol:
                    result[coin] = {
                        "price": float(item["lastPrice"]),
                        "change": float(item["priceChangePercent"]),
                        "high": float(item["highPrice"]),
                        "low": float(item["lowPrice"]),
                        "volume": float(item["quoteVolume"]),
                    }
        return result
    except Exception as e:
        print("API ERROR:", e)
        return {}

def fmt_coin(c):
    return f"<tg-emoji emoji-id='{emoji_id[c]}'>🪙</tg-emoji> <b>{c}</b>"

def build_prices(prices, prev, interval):
    t = datetime.now().strftime("%H:%M:%S")
    text = "<b>💰 Kripto Narxlar</b>\n\n"

    for c, i in prices.items():
        p = i["price"]
        pp = prev.get(c, {}).get("price", p)

        arrow = "🟢" if p > pp else ("🔴" if p < pp else "⚪")
        ch = i["change"]
        chs = f"{'🟢 +' if ch>0 else '🔴 '}{ch:.2f}%"

        text += f"{fmt_coin(c)} {arrow} <code>${p:,.4f}</code> {chs}\n"

    text += f"\n🕐 {t} | 🔄 {interval}s"
    return text

def build_stats(prices):
    text = "<b>📊 24h Statistika</b>\n\n"
    for c, i in prices.items():
        text += (
            f"{fmt_coin(c)}\n"
            f"💵 <code>${i['price']:,.4f}</code>\n"
            f"📈 {i['high']:,.2f}\n"
            f"📉 {i['low']:,.2f}\n"
            f"🔄 {i['change']:.2f}%\n\n"
        )
    return text

# ✅ ALERT
def check_alerts(chat_id, prices, user):
    for c, a in user["alerts"].items():
        if c not in prices:
            continue
        p = prices[c]["price"]

        if a["above"] and p >= a["above"]:
            bot.send_message(chat_id, f"🔔 {c} ${p} dan yuqoriga chiqdi!")
            user["alerts"][c]["above"] = None

        if a["below"] and p <= a["below"]:
            bot.send_message(chat_id, f"🔔 {c} ${p} dan pastga tushdi!")
            user["alerts"][c]["below"] = None

# ✅ THREAD
def updater(chat_id):
    while True:
        with lock:
            if chat_id not in users:
                return
            u = users[chat_id]

        if not u["active"]:
            time.sleep(1)
            continue

        prices = get_prices()
        if not prices:
            time.sleep(u["interval"])
            continue

        check_alerts(chat_id, prices, u)

        if u["section"] == "prices":
            txt = build_prices(prices, u["prev"], u["interval"])
            try:
                bot.edit_message_text(txt, chat_id, u["msg_id"])
            except:
                pass

        with lock:
            users[chat_id]["prev"] = prices

        time.sleep(u["interval"])

# ✅ START
@bot.message_handler(commands=["start"])
def start(m):
    chat_id = m.chat.id
    prices = get_prices()
    txt = build_prices(prices, {}, DEFAULT_INTERVAL)

    msg = bot.send_message(chat_id, txt)

    with lock:
        users[chat_id] = {
            "msg_id": msg.message_id,
            "interval": DEFAULT_INTERVAL,
            "active": True,
            "prev": prices,
            "section": "prices",
            "alerts": {c: {"above": None, "below": None} for c in coins}
        }

    threading.Thread(target=updater, args=(chat_id,), daemon=True).start()

# ✅ ALERT COMMAND
@bot.message_handler(commands=["alert"])
def alert(m):
    try:
        _, c, d, v = m.text.split()
        c = c.upper()
        v = float(v)

        with lock:
            users[m.chat.id]["alerts"][c][d] = v

        bot.reply_to(m, "✅ Signal qo‘shildi")
    except:
        bot.reply_to(m, "⚠️ /alert BTC above 70000")

# ✅ DELETE ALERT
@bot.message_handler(commands=["delalert"])
def delalert(m):
    c = m.text.split()[1].upper()
    with lock:
        users[m.chat.id]["alerts"][c] = {"above": None, "below": None}
    bot.reply_to(m, "🗑 O‘chirildi")

# ✅ MENYU
@bot.message_handler(func=lambda m: m.text == "💰 Narxlar")
def prices_menu(m):
    with lock:
        users[m.chat.id]["section"] = "prices"
    bot.send_message(m.chat.id, "📡 Yangilanmoqda...")

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def stats_menu(m):
    prices = get_prices()
    bot.send_message(m.chat.id, build_stats(prices))

# ✅ RUN
if __name__ == "__main__":
    print("FULL BOT ISHGA TUSHDI")
    bot.infinity_polling()
