from aiogram import Router

from bot.handlers.admin.panel import router as panel_router
from bot.handlers.admin.quiz_admin import router as quiz_admin_router
from bot.handlers.admin.weekly_winners import router as weekly_winners_router
from bot.handlers.admin.screenshot_admin import router as screenshot_admin_router
from bot.handlers.admin.screenshot_queue import router as screenshot_queue_router
from bot.handlers.admin.settings_admin import router as settings_admin_router
from bot.handlers.admin.poll import router as admin_poll_router
from bot.handlers.admin.poll_now import router as admin_poll_now_router
from bot.handlers.admin.poll_set import router as poll_set_router
from bot.handlers.admin.poll_cancel import router as poll_cancel_router
from bot.handlers.admin.poll_status import router as poll_status_router

router = Router()

router.include_router(panel_router)
router.include_router(quiz_admin_router)
router.include_router(weekly_winners_router)
router.include_router(screenshot_admin_router)
router.include_router(screenshot_queue_router)
router.include_router(settings_admin_router)
router.include_router(admin_poll_router)
router.include_router(admin_poll_now_router)
router.include_router(poll_set_router)
router.include_router(poll_cancel_router)
router.include_router(poll_status_router)