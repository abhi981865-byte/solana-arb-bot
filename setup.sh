#!/bin/bash
mkdir -p data logs data/backups
pip install -r requirements.txt
python db_init.py
python test_bot.py
echo 'Setup complete'
