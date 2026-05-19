import asyncio

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.bot.middlewares.database import DatabaseSessionMiddleware
from app.core.config import get_settings
from app.core.database import async_session_maker
from app.core.logger import configure_logging
from app.schedulers.shopping import setup_shopping_cleanup_scheduler


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    bot = Bot(token=settings.bot_token.get_secret_value())
    dispatcher = Dispatcher()
    dispatcher.update.middleware(DatabaseSessionMiddleware(async_session_maker))
    dispatcher.include_router(router)

    scheduler = setup_shopping_cleanup_scheduler(async_session_maker)
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
