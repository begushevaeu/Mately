from aiogram import Router

from app.bot.handlers import content, main_menu, onboarding, partner_aliases, shopping, start, tasks

router = Router()
router.include_router(onboarding.router)
router.include_router(partner_aliases.router)
router.include_router(start.router)
router.include_router(tasks.router)
router.include_router(shopping.router)
router.include_router(content.router)
router.include_router(main_menu.router)

__all__ = ["router"]
