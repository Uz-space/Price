import asyncio
import websockets

clients = {}

# 🧠 CLIENT ULANISHI
async def handler(ws):
    user_id = None
    try:
        # 1️⃣ ID qabul qilinadi
        user_id = await ws.recv()
        clients[user_id] = ws
        print(f"[ CONNECTED ] {user_id}")

        # 2️⃣ xabarlar
        while True:
            data = await ws.recv()

            # format: target||message
            target, msg = data.split("||", 1)

            # yuborish
            if target in clients:
                await clients[target].send(msg)

    except:
        pass

    finally:
        # disconnect bo‘lsa o‘chiramiz
        if user_id and user_id in clients:
            del clients[user_id]
            print(f"[ DISCONNECTED ] {user_id}")

# 🚀 SERVER RUN
async def main():
    port = int(__import__("os").environ.get("PORT", 8765))

    async with websockets.serve(handler, "0.0.0.0", port):
        print("[ SERVER RUNNING ]")
        await asyncio.Future()

asyncio.run(main())
