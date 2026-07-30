@echo off
cd /d "%~dp0"
pyinstaller --onefile --windowed --name AbletonDiscordPresenceSetup ^
    --icon "assets\icon.ico" ^
    --add-data "..\AbletonDiscordPresence;AbletonDiscordPresence" ^
    --add-data "assets;assets" ^
    setup_wizard.py
