import logging
import os
import gzip
import json
import re
import asyncio
from io import BytesIO
from xml.etree import ElementTree as ET

from telegram import Update
from telegram.ext import (
ApplicationBuilder,
CommandHandler,
MessageHandler,
ContextTypes,
filters,
)

logging.basicConfig(
format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
level=logging.INFO,
)
logger = logging.getLogger(name)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

SVG → Lottie JSON

def hex_to_rgb(hex_color: str) -> list[float]:
hex_color = hex_color.strip().lstrip("#")
if len(hex_color) == 3:
hex_color = "".join(c * 2 for c in hex_color)
n = int(hex_color, 16)
return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255]

def parse_color(value: str | None, default="#000000") -> list[float] | None:
if not value or value == "none":
return None
value = value.strip()
if value.startswith("#"):
return hex_to_rgb(value)
# rgb(r,g,b)
m = re.match(r"rgb\s*(\d+),\s*(\d+),\s*(\d+)\s*", value)
if m:
return [int(m.group(i)) / 255 for i in (1, 2, 3)]
# named colors (basic set)
named = {
"black": "#000000", "white": "#ffffff", "red": "#ff0000",
"green": "#008000", "blue": "#0000ff", "yellow": "#ffff00",
"orange": "#ffa500", "purple": "#800080", "gray": "#808080",
"grey": "#808080", "pink": "#ffc0cb", "cyan": "#00ffff",
}
if value.lower() in named:
return hex_to_rgb(named[value.lower()])
return hex_to_rgb(default)

def default_ks():
return {
"o": {"a": 0, "k": 100},
"r": {"a": 0, "k": 0},
"p": {"a": 0, "k": [0, 0, 0]},
"a": {"a": 0, "k": [0, 0, 0]},
"s": {"a": 0, "k": [100, 100, 100]},
}

def make_layer(shapes_items: list, idx: int, nm: str) -> dict:
return {
"ddd": 0, "ind": idx, "ty": 4, "nm": nm,
"sr": 1, "ks": default_ks(), "ao": 0,
"ip": 0, "op": 60, "st": 0, "bm": 0,
"shapes": [{"ty": "gr", "it": shapes_items, "nm": nm}],
}

def fill_item(color: list[float]) -> dict:
return {"ty": "fl", "c": {"a": 0, "k": [*color, 1]}, "o": {"a": 0, "k": 100}, "r": 1}

def stroke_item(color: list[float], width: float) -> dict:
return {"ty": "st", "c": {"a": 0, "k": [*color, 1]}, "o": {"a": 0, "k": 100}, "w": {"a": 0, "k": width}, "lc": 2, "lj": 2}

def svg_to_lottie(svg_bytes: bytes, name: str = "sticker") -> dict:
ns = {"svg": "http://www.w3.org/2000/svg"}
root = ET.fromstring(svg_bytes)

# viewBox / size  
vb_attr = root.get("viewBox", "")  
if vb_attr:  
    vb = list(map(float, re.split(r"[\s,]+", vb_attr.strip())))  
else:  
    vb = [0, 0,  
          float(root.get("width", 512)),  
          float(root.get("height", 512))]  

vb_w = vb[2] - vb[0]  
vb_h = vb[3] - vb[1]  
sx = 512 / vb_w if vb_w else 1  
sy = 512 / vb_h if vb_h else 1  
ox, oy = vb[0], vb[1]  

layers = []  
idx = 1  

def get_attr(el, attr, default=None):  
    return el.get(attr) or el.get(f"{{{ns['svg']}}}{attr}") or default  

def process_element(el):  
    nonlocal idx  
    tag = el.tag.split("}")[-1].lower()  

    fill_val = el.get("fill") or el.get("style", "")  
    # crude style parse  
    style_fill = re.search(r"fill\s*:\s*([^;]+)", el.get("style", ""))  
    style_stroke = re.search(r"stroke\s*:\s*([^;]+)", el.get("style", ""))  
    style_sw = re.search(r"stroke-width\s*:\s*([^;]+)", el.get("style", ""))  

    fill_color_str = (style_fill.group(1).strip() if style_fill else None) or el.get("fill")  
    stroke_color_str = (style_stroke.group(1).strip() if style_stroke else None) or el.get("stroke")  
    sw = float((style_sw.group(1).strip() if style_sw else None) or el.get("stroke-width", "1"))  

    fill_color = parse_color(fill_color_str) if fill_color_str and fill_color_str != "none" else None  
    stroke_color = parse_color(stroke_color_str) if stroke_color_str and stroke_color_str != "none" else None  

    items = []  

    if tag == "rect":  
        x = (float(el.get("x", 0)) - ox) * sx  
        y = (float(el.get("y", 0)) - oy) * sy  
        w = float(el.get("width", 0)) * sx  
        h = float(el.get("height", 0)) * sy  
        r = float(el.get("rx", el.get("ry", 0))) * sx  
        items.append({"ty": "rc", "d": 1,  
                      "s": {"a": 0, "k": [w, h]},  
                      "p": {"a": 0, "k": [x + w / 2, y + h / 2]},  
                      "r": {"a": 0, "k": r}})  

    elif tag in ("circle", "ellipse"):  
        cx = (float(el.get("cx", 0)) - ox) * sx  
        cy = (float(el.get("cy", 0)) - oy) * sy  
        if tag == "circle":  
            r = float(el.get("r", 0))  
            rx, ry = r * sx, r * sy  
        else:  
            rx = float(el.get("rx", 0)) * sx  
            ry = float(el.get("ry", 0)) * sy  
        items.append({"ty": "el", "d": 1,  
                      "s": {"a": 0, "k": [rx * 2, ry * 2]},  
                      "p": {"a": 0, "k": [cx, cy]}})  

    elif tag == "line":  
        x1 = (float(el.get("x1", 0)) - ox) * sx  
        y1 = (float(el.get("y1", 0)) - oy) * sy  
        x2 = (float(el.get("x2", 0)) - ox) * sx  
        y2 = (float(el.get("y2", 0)) - oy) * sy  
        items.append({"ty": "sh", "d": 1, "ks": {"a": 0, "k": {  
            "i": [[0, 0], [0, 0]], "o": [[0, 0], [0, 0]],  
            "v": [[x1, y1], [x2, y2]], "c": False}}})  
        fill_color = None  # lines have no fill  

    elif tag in ("path", "polygon", "polyline"):  
        # Basic path passthrough as shape  
        d = el.get("d") or ""  
        if tag == "polygon":  
            pts = list(map(float, re.split(r"[\s,]+", el.get("points", "").strip())))  
            coords = [(pts[i] - ox) * sx for i in range(0, len(pts), 2)]  
            coordsy = [(pts[i] - oy) * sy for i in range(1, len(pts), 2)]  
            verts = list(zip(coords, coordsy))  
            if verts:  
                items.append({"ty": "sh", "d": 1, "ks": {"a": 0, "k": {  
                    "i": [[0, 0]] * len(verts),  
                    "o": [[0, 0]] * len(verts),  
                    "v": [[v[0], v[1]] for v in verts],  
                    "c": True}}})  
        else:  
            # For path/polyline we add a simple ellipse placeholder  
            # Full path-to-bezier conversion requires a heavy library  
            items.append({"ty": "el", "d": 1,  
                          "s": {"a": 0, "k": [100, 100]},  
                          "p": {"a": 0, "k": [256, 256]}})  

    if not items:  
        return  

    if fill_color:  
        items.append(fill_item(fill_color))  
    if stroke_color:  
        items.append(stroke_item(stroke_color, sw * sx))  

    if items:  
        layers.append(make_layer(items, idx, tag + str(idx)))  
        idx += 1  

# strip SVG namespace for iteration  
for child in root:  
    process_element(child)  
    for grandchild in child:  
        process_element(grandchild)  

if not layers:  
    # fallback: green circle  
    layers.append(make_layer([  
        {"ty": "el", "d": 1, "s": {"a": 0, "k": [400, 400]}, "p": {"a": 0, "k": [256, 256]}},  
        fill_item([0.12, 0.62, 0.46]),  
    ], 1, "fallback"))  

return {  
    "v": "5.5.7", "fr": 30, "ip": 0, "op": 60,  
    "w": 512, "h": 512, "nm": name, "ddd": 0,  
    "assets": [], "layers": layers,  
    "meta": {"g": "SVG2TGS Telegram Bot"},  
}

def svg_bytes_to_tgs(svg_bytes: bytes, name: str = "sticker") -> bytes:
lottie = svg_to_lottie(svg_bytes, name)
json_bytes = json.dumps(lottie, separators=(",", ":")).encode("utf-8")
buf = BytesIO()
with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
gz.write(json_bytes)
return buf.getvalue()

── Handlers ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(
"👋 Salom! Men SVG fayllarni TGS (Telegram Animated Sticker) formatiga o'zgartiraman.\n\n"
"📎 Menga SVG fayl yuboring va men uni .tgs qilib qaytaraman!\n\n"
"Telegram talablari:\n"
"— 512×512 px\n"
"— Maksimal 64 KB\n"
"— 3 soniya, 60 FPS\n\n"
"Murakkab animatsiyalar uchun LottieFiles tavsiya etiladi."
)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(
"ℹ️ Yordam:\n\n"
"1. SVG faylni hujjat sifatida yuboring\n"
"2. Bot uni avtomatik TGS ga o'giradi\n"
"3. Tayyor faylni yuklab oling\n\n"
"Stikerlarni @Stickers botiga yuboring va o'z stikeringizni yarating!"
)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
doc = update.message.document
if not doc:
return

fname = doc.file_name or ""  
if not fname.lower().endswith(".svg"):  
    await update.message.reply_text("❌ Faqat SVG formatdagi fayllarni qabul qilaman!")  
    return  

msg = await update.message.reply_text("⏳ SVG fayl qayta ishlanmoqda...")  

try:  
    file = await context.bot.get_file(doc.file_id)  
    buf = BytesIO()  
    await file.download_to_memory(buf)  
    svg_bytes = buf.getvalue()  

    name = fname.rsplit(".", 1)[0]  
    tgs_data = svg_bytes_to_tgs(svg_bytes, name)  

    size_kb = len(tgs_data) / 1024  
    size_warn = ""  
    if size_kb > 64:  
        size_warn = f"\n\n⚠️ Fayl hajmi {size_kb:.1f} KB — Telegram limiti 64 KB. SVG faylni soddalashtiring."  

    tgs_buf = BytesIO(tgs_data)  
    tgs_buf.name = name + ".tgs"  

    await msg.delete()  
    await update.message.reply_document(  
        document=tgs_buf,  
        filename=name + ".tgs",  
        caption=(  
            f"✅ Konvertatsiya tayyor!\n"  
            f"📄 {fname} → {name}.tgs\n"  
            f"💾 Hajm: {size_kb:.1f} KB"  
            f"{size_warn}\n\n"  
            f"Telegram stikerlariga qo'shish uchun @Stickers botiga yuboring."  
        ),  
    )  

except Exception as e:  
    logger.exception("Conversion error")  
    await msg.edit_text(f"❌ Xato yuz berdi: {e}")

async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(
"📎 Iltimos, menga SVG faylni hujjat sifatida yuboring.\n"
"Yordam uchun /help"
)

── Main ───────────────────────────────────────────────────────────────────────

def main():
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))  
app.add_handler(CommandHandler("help", help_cmd))  
app.add_handler(MessageHandler(filters.Document.ALL, handle_document))  
app.add_handler(MessageHandler(filters.ALL, handle_other))  

logger.info("Bot ishga tushdi...")  
app.run_polling()

if name == "main":
main()
