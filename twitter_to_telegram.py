import logging
import asyncio
import requests
from telethon import TelegramClient
import os
from dotenv import load_dotenv
import schedule
import time

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()

# Twitter API setup
bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

# Telegram bot setup
telegram_api_id = os.getenv('TELEGRAM_API_ID')
telegram_api_hash = os.getenv('TELEGRAM_API_HASH')
telegram_bot_token = os.getenv('TELEGRAM_ACCESS_TOKEN')
telegram_chat_id = int(os.getenv('TELEGRAM_CHAT_ID'))  # Ensure it is an integer

logging.debug(f"Telegram API ID: {telegram_api_id}")
logging.debug(f"Telegram API Hash: {telegram_api_hash}")
logging.debug(f"Telegram Bot Token: {telegram_bot_token}")
logging.debug(f"Telegram Chat ID: {telegram_chat_id}")

telegram_client = TelegramClient('bot', telegram_api_id, telegram_api_hash).start(bot_token=telegram_bot_token)

async def send_telegram_message(message):
    await telegram_client.send_message(telegram_chat_id, message)

async def fetch_and_send_tweets():
    logging.debug("Fetching tweets")
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    query = "from:Christo16784414 OR to:Christo16784414"
    url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        logging.debug(f"Response Data: {response.json()}")
        tweets = response.json().get('data', [])
        if not tweets:
            logging.debug("No tweets found.")
        for tweet in tweets:
            message = f'Tweet ID: {tweet["id"]}: {tweet["text"]}'
            logging.debug(f"Sending message: {message}")
            await send_telegram_message(message)
    else:
        logging.error(f"Error fetching tweets: {response.status_code} {response.text}")

async def schedule_tweets():
    schedule.every(1).minutes.do(fetch_and_send_tweets_wrapper)
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

def fetch_and_send_tweets_wrapper():
    asyncio.create_task(fetch_and_send_tweets())

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(schedule_tweets())
    telegram_client.run_until_disconnected()
