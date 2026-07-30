@echo off
cd /d "%~dp0"
pyinstaller --onefile --windowed --name AbletonDiscordPresenceSetup ^
    --add-data "..\AbletonDiscordPresence;AbletonDiscordPresence" ^
    setup_wizard.py
