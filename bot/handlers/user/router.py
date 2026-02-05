# bot/handlers/user/router.py
from aiogram import Router

from bot.handlers.user.start import router as start_router
from bot.handlers.user.whoami import router as whoami_router
from bot.handlers.user.checkin import router as checkin_router
from bot.handlers.user.status import router as status_router
from bot.handlers.user.quiz import router as quiz_router
from bot.handlers.user.menu_stub import router as menu_stub_router
from bot.handlers.user.leaderboard import router as leaderboard_router
from bot.handlers.user.screenshot import router as screenshot_router
from .spin import router as spin_router
from bot.handlers.user.poll import router as poll_user_router


router = Router(name="user")

router.include_router(start_router)
router.include_router(whoami_router)
router.include_router(checkin_router)
router.include_router(status_router)
router.include_router(quiz_router)       
router.include_router(menu_stub_router)
router.include_router(leaderboard_router)
router.include_router(screenshot_router)
router.include_router(spin_router)
router.include_router(poll_user_router)
