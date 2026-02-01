## tg_engagement_bot

### Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env
# edit .env and set BOT_TOKEN
python -m bot.main
