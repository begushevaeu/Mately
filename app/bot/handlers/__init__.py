from aiogram import Router

from app.bot.handlers import onboarding, start

router = Router()
router.include_router(onboarding.router)
router.include_router(start.router)

__all__ = ["router"]
