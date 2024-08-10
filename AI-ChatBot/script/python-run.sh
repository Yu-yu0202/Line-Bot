#!/bin/bash

cd ~
rm -rf Line-Bot
git clone -b main https://github.com/Yu-yu0202/Line-Bot.git
cd ~\Line-Bot\AI-ChatBot

sudo apt update
sudo apt install python3.12.2
sudo apt install --only-upgrade python3*

python -m venv venv
source venv/bin/activate

pip install -r requiments.txt

python main.py