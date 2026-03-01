#!/bin/bash
cd /home/ukhan/tankpit-bot-legacy
source venv/bin/activate
exec python bot.py >> bot.log 2>&1
