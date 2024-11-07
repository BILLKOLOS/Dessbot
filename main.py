import logging
import asyncio
import requests
from telethon import TelegramClient, events, Button
import os
from dotenv import load_dotenv
from user_manager import save_chat_id, get_user_chat_ids
import time
from datetime import datetime, timedelta
import queue
import threading

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

# Define admin user IDs
admin_user_ids = [7443937029, 7104246753]  # Replace with actual admin user IDs

# Dictionary to keep track of each user's monitoring state
user_monitoring_states = {}
user_permissions = {}

# Function to get user IDs (temporary function)
@telegram_client.on(events.NewMessage(pattern='/getid'))
async def get_user_id(event):
    user_id = event.sender_id
    await event.respond(f"Your User ID is: {user_id}")
    print(f"User ID: {user_id}")

# Handler for /start command
@telegram_client.on(events.NewMessage(pattern='/start'))
async def handler(event):
    save_chat_id(event.chat_id)
    user_monitoring_states[event.chat_id] = False  # Initialize monitoring state for the user
    user_permissions[event.chat_id] = event.chat_id in admin_user_ids  # Grant permission if the user is admin
    await event.respond(
        "Welcome! Please choose an option from the menu below.",
        buttons=[
            [Button.text('🌟 Monitor Twitter Accounts'), Button.text('🚫 Stop Monitoring')],
            [Button.text('ℹ️ Help'), Button.text('⚙️ Settings')]
        ]
    )
    print(f"Added chat ID: {event.chat_id}")

# Handler for Monitor Twitter Accounts button
@telegram_client.on(events.NewMessage(pattern='🌟 Monitor Twitter Accounts'))
async def monitor_handler(event):
    if event.chat_id in admin_user_ids:
        for user_id in user_permissions.keys():
            user_monitoring_states[user_id] = True  # Set monitoring state to True for all users with permission
        await event.respond("Enter Twitter usernames to monitor (comma-separated):")
    else:
        await event.respond("You don't have permission to start monitoring. Please contact an admin.")

# Handler for Stop Monitoring button
@telegram_client.on(events.NewMessage(pattern='🚫 Stop Monitoring'))
async def stop_monitoring_handler(event):
    if event.chat_id in admin_user_ids:
        for user_id in user_permissions.keys():
            user_monitoring_states[user_id] = False  # Set monitoring state to False for all users with permission
        await event.respond("Stopping monitoring...")
        print(f"Monitoring stopped by admin: {event.chat_id}")
    else:
        await event.respond("You don't have permission to stop monitoring. Please contact an admin.")

# Handler for Help button
@telegram_client.on(events.NewMessage(pattern='ℹ️ Help'))
async def help_handler(event):
    await event.respond("Help Information: \n1. To monitor Twitter accounts, click 'Monitor Twitter Accounts'. \n2. To stop monitoring, click 'Stop Monitoring'. \n3. For settings, click 'Settings'.")

# Handler for Settings button
@telegram_client.on(events.NewMessage(pattern='⚙️ Settings'))
async def settings_handler(event):
    await event.respond("Settings: Here you can configure your preferences.")

# Handler for other messages (e.g., Twitter usernames input)
@telegram_client.on(events.NewMessage)
async def username_handler(event):
    if user_monitoring_states.get(event.chat_id, False) and user_permissions.get(event.chat_id, False):
        usernames = event.message.message.strip().replace('@', '').split(',')
        await event.respond(f"Monitoring accounts: {', '.join(usernames)}...")
        asyncio.create_task(monitor_accounts(usernames, event))
    else:
        await event.respond("Monitoring is currently stopped or you don't have permission. Please contact an admin.")

# Function for admins to grant permission to other users
async def grant_permission(admin_id, user_id):
    if admin_id in admin_user_ids:
        user_permissions[user_id] = True
        return f"Permission granted to user {user_id}."
    else:
        return "You don't have permission to grant access."

# Example usage of granting permission (this would be part of your bot's command handlers)
@telegram_client.on(events.NewMessage(pattern='/grant (.+)'))
async def grant_permission_handler(event):
    if event.chat_id in admin_user_ids:
        user_id = int(event.pattern_match.group(1).strip())
        message = await grant_permission(event.chat_id, user_id)
        await event.respond(message)
    else:
        await event.respond("You don't have permission to grant access.")


# Initialize cache and message queue
tweet_cache = {}
cache_duration = timedelta(minutes=15)  # Cache duration
tweet_queue = queue.Queue()

# Worker function to process queue
def tweet_worker():
    while True:
        item = tweet_queue.get()
        if item is None:
            break
        asyncio.run(process_queue_item(item))
        tweet_queue.task_done()

async def process_queue_item(item):
    await item[0](*item[1:])

# Start worker thread
worker_thread = threading.Thread(target=tweet_worker)
worker_thread.start()

# Add tasks to queue
def add_task_to_queue(task, *args):
    tweet_queue.put((task, *args))

# Stop the worker thread gracefully
def stop_worker_thread():
    tweet_queue.put(None)
    worker_thread.join()

# Monitor multiple accounts for tweets, replies, and likes
async def monitor_accounts(usernames, event):
    last_tweet_ids = {username: None for username in usernames}
    last_reply_ids = {username: None for username in usernames}
    last_like_ids = {username: None for username in usernames}
    while True:
        for username in usernames:
            add_task_to_queue(monitor_account, username, last_tweet_ids, last_reply_ids, last_like_ids, event)
        await asyncio.sleep(30)  # Check for updates every 1 seconds

async def monitor_account(username, last_tweet_ids, last_reply_ids, last_like_ids, event):
    user_id = await fetch_user_id(username)
    if user_id:
        add_task_to_queue(fetch_tweets, user_id, username, last_tweet_ids, event)
        add_task_to_queue(fetch_replies, user_id, username, last_reply_ids, event)
        add_task_to_queue(fetch_likes, user_id, username, last_like_ids, event)

async def fetch_user_id(username):
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    user_url = f"https://api.twitter.com/2/users/by/username/{username}"
    backoff_time = 10
    while True:
        user_response = requests.get(user_url, headers=headers)
        
        logging.debug(f"Twitter API response status code: {user_response.status_code}")
        logging.debug(f"Twitter API response headers: {user_response.headers}")
        
        if user_response.status_code == 429:
            reset_time = int(user_response.headers["x-rate-limit-reset"])
            current_time = time.time()
            sleep_time = reset_time - current_time
            logging.info(f"Rate limit hit. Sleeping for {sleep_time} seconds.")
            await asyncio.sleep(sleep_time)
        elif user_response.status_code == 404:
            logging.error(f"Username '{username}' not found.")
            return None
        elif user_response.status_code == 200:
            try:
                user_id = user_response.json().get('data', {}).get('id', None)
                return user_id
            except ValueError:
                logging.error("Failed to decode JSON response.")
                return None
        else:
            logging.error(f"Failed to fetch user ID: {user_response.text}")
            await asyncio.sleep(backoff_time)
            backoff_time = min(backoff_time * 2, 320)  # Exponential backoff

    return None

# Function to shorten text to 4 lines
def shorten_text(text, max_lines=4):
    lines = text.split('\n')
    if len(lines) <= max_lines:
        return text
    return '\n'.join(lines[:max_lines]) + '…'

# Fetch tweets and send them to Telegram with shortened text
async def fetch_tweets(user_id, username, last_tweet_ids, event):
    now = datetime.now()
    if username in tweet_cache and now - tweet_cache[username]['timestamp'] < cache_duration:
        tweets = tweet_cache[username]['data']
    else:
        headers = {
            "Authorization": f"Bearer {bearer_token}"
        }
        params = {
            "since_id": last_tweet_ids[username],
            "max_results": 10
        } if last_tweet_ids[username] else {"max_results": 10}
        tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
        tweets_response = requests.get(tweets_url, headers=headers, params=params)
        
        if tweets_response.status_code == 200:
            tweets = tweets_response.json().get('data', [])
            tweet_cache[username] = {'data': tweets, 'timestamp': now}
        else:
            logging.error(f"Failed to fetch tweets: {tweets_response.json()}")
            return
    
    if tweets:
        for tweet in tweets:
            text = shorten_text(tweet['text'])
            tweet_link = f"https://twitter.com/{username}/status/{tweet['id']}"
            timestamp = time.strftime("%I:%M %p", time.localtime(time.time()))

            await event.respond(f"Tweet | {username} | [Post Link]({tweet_link})\n\n"
                                f"{text}\n\n"
                                f"X (formerly Twitter)\n"
                                f"@{username} on X\n"
                                f"Read more: [View on X]({tweet_link})\n"
                                f"{timestamp}")
            
        last_tweet_ids[username] = tweets[0]['id']
async def fetch_replies(user_id, username, last_reply_ids, event):
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    params = {
        "since_id": last_reply_ids[username],
        "max_results": 10
    } if last_reply_ids[username] else {"max_results": 10}
    replies_url = f"https://api.twitter.com/2/tweets/search/recent?query=from:{user_id}&tweet.fields=conversation_id,author_id,in_reply_to_user_id"
    replies_response = requests.get(replies_url, headers=headers, params=params)
    if replies_response.status_code == 200:
        replies = replies_response.json().get('data', [])
        if replies:
            for reply in replies:
                in_reply_to_user_id = reply.get('in_reply_to_user_id')
                tweet_link = f"https://twitter.com/{username}/status/{reply['id']}"
                timestamp = time.strftime("%I:%M %p", time.localtime(time.time()))
                if in_reply_to_user_id:
                    post_owner = await fetch_username(in_reply_to_user_id)
                    await event.respond(f"Reply | {username} | [Post Link]({tweet_link})\n\n"
                                        f"{reply['text']}\n\n"
                                        f"Reply to @{post_owner}\n"
                                        f"Read more: [View on X]({tweet_link})\n"
                                        f"{timestamp}")
                else:
                    await event.respond(f"Reply | @{username} | [Post Link]({tweet_link})\n\n"
                                        f"{reply['text']}\n"
                                        f"Read more: [View on X]({tweet_link})\n"
                                        f"{timestamp}")
            last_reply_ids[username] = replies[0]['id']


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
    return 'unknown_user'

async def fetch_likes(user_id, username, last_like_ids, event):
    headers = {
        "Authorization": f"Bearer {oauth_token}"
    }
    params = {
        "since_id": last_like_ids[username],
        "max_results": 10
    } if last_like_ids[username] else {"max_results": 10}
    likes_url = f"https://api.twitter.com/2/users/{user_id}/liked_tweets"
    likes_response = requests.get(likes_url, headers=headers, params=params)
    if likes_response.status_code == 200:
        likes = likes_response.json().get('data', [])
        if likes:
            for like in likes:
                tweet_link = f"https://twitter.com/{username}/status/{like['id']}"
                timestamp = time.strftime("%I:%M %p", time.localtime(time.time()))
                await event.respond(f"Like | @{username} | [Post Link]({tweet_link})\n\n"
                                    f"{like['text']}\n"
                                    f"Read more: [View on X]({tweet_link})\n"
                                    f"{timestamp}")
            last_like_ids[username] = likes[0]['id']

if __name__ == "__main__":
    telegram_client.run_until_disconnected()

    # Gracefully stop the worker thread
    stop_worker_thread()
