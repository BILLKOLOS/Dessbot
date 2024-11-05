import logging
import asyncio
import requests
from telethon import TelegramClient, events
import os
from dotenv import load_dotenv
from user_manager import save_chat_id, get_user_chat_ids

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()

# Twitter API setup
bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
oauth_token = os.getenv('TWITTER_OAUTH_TOKEN')

# Telegram bot setup
telegram_api_id = os.getenv('TELEGRAM_API_ID')
telegram_api_hash = os.getenv('TELEGRAM_API_HASH')
telegram_bot_token = os.getenv('TELEGRAM_ACCESS_TOKEN')

logging.debug(f"Telegram API ID: {telegram_api_id}")
logging.debug(f"Telegram API Hash: {telegram_api_hash}")
logging.debug(f"Telegram Bot Token: {telegram_bot_token}")

telegram_client = TelegramClient('bot', telegram_api_id, telegram_api_hash).start(bot_token=telegram_bot_token)

# Event handler for new messages
@telegram_client.on(events.NewMessage(pattern='/start'))
async def handler(event):
    save_chat_id(event.chat_id)
    await event.respond("Welcome! Send me a Twitter username to fetch their latest tweet.")
    print(f"Added chat ID: {event.chat_id}")

@telegram_client.on(events.NewMessage)
async def username_handler(event):
    username = event.message.message.strip().replace('@', '')
    latest_tweet = await fetch_latest_tweet(username)
    if latest_tweet:
        await event.respond(f"Latest tweet from @{username}: {latest_tweet}")
    else:
        await event.respond(f"Could not fetch tweets for @{username}. Please try again.")

# Send messages to all users
async def send_telegram_message(message):
    chat_ids = get_user_chat_ids()
    print(f"Broadcasting to chat IDs: {chat_ids}")
    for chat_id in list(chat_ids):  # Use a copy of the set
        await telegram_client.send_message(chat_id, message)

async def fetch_username(user_id):
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    url = f"https://api.twitter.com/2/users/{user_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        user_data = response.json().get('data', {})
        username = user_data.get('username', 'unknown_user')
        return username
    else:
        logging.error(f"Error fetching username: {response.status_code} {response.text}")
        return 'unknown_user'

async def fetch_latest_tweet(username):
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    user_url = f"https://api.twitter.com/2/users/by/username/{username}"
    user_response = requests.get(user_url, headers=headers)
    if user_response.status_code == 200:
        user_id = user_response.json().get('data', {}).get('id', None)
        if user_id:
            tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets?max_results=5"
            tweets_response = requests.get(tweets_url, headers=headers)
            if tweets_response.status_code == 200:
                tweets = tweets_response.json().get('data', [])
                if tweets:
                    return tweets[0]['text']
    return None

if __name__ == "__main__":
    telegram_client.run_until_disconnected()