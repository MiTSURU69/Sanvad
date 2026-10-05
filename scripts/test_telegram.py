import asyncio

from app.services import telegram


async def main():
    if not telegram.enabled():
        print("Telegram not configured: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return
    ok = await telegram.send("<b>Sanvad test alert</b>\nConnection is working.")
    print("sent" if ok else "failed")


asyncio.run(main())