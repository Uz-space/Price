import asyncio
import os
import zipfile
from telethon import TelegramClient
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import InputStickerSetShortName

api_id = 36092552          # <- o'zgartir
api_hash = "9d18a707a797f12f1c31587d3cc6e0d7"

client = TelegramClient("session", api_id, api_hash)


def extract_pack(link: str):
    return link.split("/")[-1].strip()


async def download_sticker_set(pack_name):
    result = await client(GetStickerSetRequest(
        stickerset=InputStickerSetShortName(short_name=pack_name),
        hash=0
    ))
    return result.documents


async def export_pack(link):
    pack = extract_pack(link)

    os.makedirs("output", exist_ok=True)

    docs = await download_sticker_set(pack)

    files = []

    for i, doc in enumerate(docs):
        path = await client.download_media(doc, file=f"output/{i}")

        emoji = ""
        if hasattr(doc, "attributes"):
            for attr in doc.attributes:
                if hasattr(attr, "alt"):
                    emoji = attr.alt

        new_name = f"{i}_{emoji}.webp"
        os.rename(path, f"output/{new_name}")
        files.append(f"output/{new_name}")

    zip_name = f"{pack}.zip"

    with zipfile.ZipFile(zip_name, "w") as z:
        for f in files:
            z.write(f)

    print(f"✅ Done: {zip_name}")


async def main():
    await client.start()
    link = input("Pack link: ")
    await export_pack(link)


client.loop.run_until_complete(main())
