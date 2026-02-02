from aiogram import Router

from bot.handlers.admin.router import router as admin_router
from bot.handlers.user.router import router as user_router
from bot.handlers.common import router as common_router

router = Router()

router.include_router(admin_router)   # ✅ admin commands first
router.include_router(user_router)
router.include_router(common_router)  # ✅ LAST = fallback only
