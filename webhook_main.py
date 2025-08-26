import os
from aiohttp import web
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from bot_core import (
    start, help_cmd, today, next_cmd, subscribe, setgroup, text_router,
    tomorrow, week, announce
)

if __name__ == "__main__":
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    webhook_url = os.environ["WEBHOOK_URL"]  # e.g. https://your-bot.onrender.com/webhook
    port = int(os.environ.get("PORT", "10000"))  # Render sets PORT

    app = ApplicationBuilder().token(token).build()

    # Register handlers
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

    # Healthcheck
    async def root(_request):
        return web.Response(text="OK", status=200)
    app.web_app.add_routes([web.get("/", root)])

    # Start aiohttp server + set Telegram webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=webhook_url,
        drop_pending_updates=True,
    )
