import requests
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file

def analyze_sentiment(text):
    API_URL = "https://api-inference.huggingface.co/models/distilbert-base-uncased-emotion"
    HEADERS = {
        "Authorization": f"Bearer {os.getenv('HUGGINGFACE_TOKEN')}"
    }
    response = requests.post(API_URL, headers=HEADERS, json={"inputs": text})
    
    if response.status_code == 200:
        # Parse the response (returns a list of sentiment labels and scores)
        result = response.json()[0]
        sentiment = max(result, key=lambda x: x['score'])['label']
        return sentiment
    else:
        print(f"Error: {response.status_code}")
        return "neutral"  # Default if API fails