from aiogram import Router

from app.bot.handlers import main_menu, onboarding, partner_aliases, start, tasks

router = Router()
router.include_router(onboarding.router)
router.include_router(partner_aliases.router)
router.include_router(start.router)
router.include_router(tasks.router)
router.include_router(main_menu.router)

__all__ = ["router"]
