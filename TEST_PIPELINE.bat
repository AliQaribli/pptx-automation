@echo off
cd /d "C:\Users\Ali\presentation-agent"
echo ============================================
echo   Beautiful Deck Agent - PIPELINE TEST
echo ============================================
echo.
echo [1/3] Building the sample deck offline...
python scripts\demo.py
echo.
echo [2/3] Running Telegram bot tests...
python -m pytest tests\test_telegram_bot.py -q
echo.
echo [3/3] Offline Telegram self-test...
python scripts\telegram_bot.py --self-test
echo.
echo DONE. Opening the folder with your deck...
start "" "output\brief"
pause
