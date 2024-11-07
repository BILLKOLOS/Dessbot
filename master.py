import requests
import json
import time
from config import Config  # Ensure your config contains valid tokens and keys
from telegram import Bot
from flask import Flask
from oauth import app as oauth_app  # Import your OAuth app

# Initialize your Telegram bot
bot = Bot(token=Config.TELEGRAM_TOKEN)

# Initialize Flask app
app = Flask(__name__)
app.register_blueprint(oauth_app)  # Register the OAuth routes

# Function to add rules for filtering tweets
def add_rules():
    url = "https://api.twitter.com/2/tweets/search/stream/rules"
    headers = {
        "Authorization": f"Bearer {Config.TWITTER_BEARER_TOKEN}",
        "Content-Type": "application/json"
    }
    rules = {
        "add": [
            {"value": "from:actual_account_name has:links"}  # Adjust this rule with actual account name
        ]
    }
    response = requests.post(url, headers=headers, json=rules)
    
    if response.status_code != 201:
        print("Error adding rules:", response.status_code, response.text)
    else:
        print("Rules added successfully.")

# Function to stream tweets
def stream_tweets():
    url = "https://api.twitter.com/2/tweets/search/stream"
    headers = {
        "Authorization": f"Bearer {Config.TWITTER_BEARER_TOKEN}"
    }
    response = requests.get(url, headers=headers, stream=True)

    if response.status_code != 200:
        print("Error connecting to stream:", response.status_code)
        return

    for line in response.iter_lines():
        if line:
            tweet = json.loads(line)
            process_tweet(tweet)

# Function to process each tweet
def process_tweet(tweet):
    # Adjust the path to access tweet text based on actual response structure
    tweet_text = tweet.get('data', {}).get('text', 'No text available')
    print("New tweet:", tweet_text)

    if tweet_text:
        bot.send_message(chat_id=Config.CHAT_ID, text=tweet_text)

if __name__ == "__main__":
    # Run the Flask app in a separate thread (optional)
    from threading import Thread
    Thread(target=lambda: app.run(port=5000)).start()

    add_rules()  # Add rules to filter tweets
    time.sleep(2)  # Allow time for rules to take effect
    stream_tweets()  # Start streaming tweets
