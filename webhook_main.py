# webhook_main.py
import os
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from bot_core import (
    start, help_cmd, today, next_cmd, subscribe, setgroup, text_router,
    tomorrow, week, announce
)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]  # e.g. https://<service>.onrender.com/webhook
PORT = int(os.environ.get("PORT", "10000"))  # Render provides PORT

async def build_ptb_app():
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("tomorrow", tomorrow))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("next", next_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("setgroup", setgroup))
    app.add_handler(CommandHandler("announce", announce))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    return app

async def main():
    # 1) Build PTB application and start it (this starts JobQueue too)
    ptb = await build_ptb_app()
    await ptb.initialize()
    await ptb.start()

    # 2) Set Telegram webhook to our public URL
    await ptb.bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

    # 3) Build aiohttp web server
    async def health(_req):
        return web.Response(text="OK", status=200)

    async def telegram_webhook(req: web.Request):
        data = await req.json()
        update = Update.de_json(data, ptb.bot)
        await ptb.process_update(update)
        return web.Response(text="OK")

    app = web.Application()
    app.add_routes([
        web.get("/", health),                 # Render health check
        web.post("/webhook", telegram_webhook)
    ])

    # Clean shutdown PTB when server stops
    async def on_cleanup(_app):
        await ptb.stop()
        await ptb.shutdown()

    app.on_cleanup.append(on_cleanup)

    # 4) Run the web server (blocks here)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    # Sleep forever
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
