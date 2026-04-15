#!/usr/bin/env python3
import os
import io
import re
import json
import gzip
import zipfile
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_TGS_SIZE = 64 * 1024
TARGET_WIDTH = 512
TARGET_HEIGHT = 512

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("svg-bot")

# ---------------- SVG PARSER ----------------
class SVGToLottieConverter:

    def parse_svg(self, content: str):
        try:
            return ET.fromstring(content)
        except Exception:
            raise ValueError("Invalid SVG")

    def extract_size(self, root):
        w = root.get("width", str(TARGET_WIDTH))
        h = root.get("height", str(TARGET_HEIGHT))

        vb = root.get("viewBox")
        if vb:
            parts = vb.split()
            if len(parts) == 4:
                w, h = parts[2], parts[3]

        return int(float(w)), int(float(h))

    def parse_color(self, c):
        if not c or c == "none":
            return [0, 0, 0, 1]

        if c.startswith("#"):
            c = c.lstrip("#")
            if len(c) == 3:
                r = int(c[0]*2, 16)/255
                g = int(c[1]*2, 16)/255
                b = int(c[2]*2, 16)/255
            else:
                r = int(c[0:2], 16)/255
                g = int(c[2:4], 16)/255
                b = int(c[4:6], 16)/255
            return [r, g, b, 1]

        return [0, 0, 0, 1]

    def convert(self, svg):
        root = self.parse_svg(svg)
        w, h = self.extract_size(root)

        lottie = {
            "v": "5.5.7",
            "fr": 30,
            "ip": 0,
            "op": 90,
            "w": TARGET_WIDTH,
            "h": TARGET_HEIGHT,
            "layers": []
        }

        shapes = []

        # PATHS
        for p in root.iter():
            if p.tag.endswith("path"):
                d = p.get("d")
                if not d:
                    continue

                fill = self.parse_color(p.get("fill", "#000000"))

                shapes.append({
                    "ty": "gr",
                    "it": [{
                        "ty": "fl",
                        "c": {"a": 0, "k": fill},
                        "o": {"a": 0, "k": 100}
                    }]
                })

        if not shapes:
            return None

        lottie["layers"].append({
            "ty": 4,
            "nm": "layer",
            "ks": {},
            "shapes": shapes
        })

        return lottie


# ---------------- TGS ----------------
class TGS:
    @staticmethod
    def build(lottie):
        data = json.dumps(lottie, separators=(",", ":")).encode()
        return gzip.compress(data, compresslevel=9)


# ---------------- HANDLER ----------------
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document

    if not doc.file_name.endswith(".svg"):
        await update.message.reply_text("Faqat SVG yubor")
        return

    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()

    svg = None
    for enc in ["utf-8", "latin-1"]:
        try:
            svg = data.decode(enc)
            break
        except:
            pass

    if not svg:
        await update.message.reply_text("SVG o‘qilmadi")
        return

    converter = SVGToLottieConverter()
    lottie = converter.convert(svg)

    if not lottie:
        await update.message.reply_text("SVG ichida shape yo‘q")
        return

    tgs = TGS.build(lottie)

    if len(tgs) > MAX_TGS_SIZE:
        await update.message.reply_text("64KB limitdan oshdi")
        return

    zipbuf = io.BytesIO()
    with zipfile.ZipFile(zipbuf, "w") as z:
        z.writestr("sticker.tgs", tgs)
        z.writestr("sticker.json", json.dumps(lottie, indent=2))

    zipbuf.seek(0)

    await update.message.reply_document(
        document=zipbuf,
        filename="sticker.zip",
        caption="Done"
    )


# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send SVG")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.COMMAND, start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
