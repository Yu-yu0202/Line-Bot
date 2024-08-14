#!/bin/bash

cd ~
rm -rf ~/Line-Bot
git clone -b "AI-ChatBot/develop" https://github.com/Yu-yu0202/Line-Bot.git
cd ~/Line-Bot/AI-ChatBot

pyenv local 3.12.2

python -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requiments.txt

python main.py