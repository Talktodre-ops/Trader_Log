# Trader Log Bot 📊

A Telegram bot for traders to log trades, analyze performance, and receive sentiment-based advice.

## Setup

1. **Clone the repo**:
   ```bash
   git clone https://github.com/Talktodre-ops/Trader_Log.git


2 **Install dependencies** :
  ```bash
    pip install -r requirements.txt

3 **Create a .env file** : 
    TELEGRAM_TOKEN=your_telegram_bot_token
    SUPABASE_URL=your_supabase_url
    SUPABASE_KEY=your_supabase_key
    HUGGINGFACE_TOKEN=your_huggingface_api_token

    Features
Log trades with TradingView links
Sentiment analysis of trade notes
Weekly performance reports
Risk/reward ratio analysis


#### **B. Secure Environment Variables**
- Never commit your `.env` file (it’s in `.gitignore`).
- If deploying to platforms like Render or Vercel, use their **Secrets/Environment Variables** feature to store keys securely.

#### **C. Deploy the Bot**
To keep the bot running 24/7, deploy it to a platform like:
- [**Render**](https://render.com) (free tier for small bots)
- [**Heroku**](https://heroku.com) (free dyno)
- [**PythonAnywhere**](https://www.pythonanywhere.com) (free tier)

#### **D. Improve the Code**
- Add error handling for edge cases (e.g., invalid TradingView links).
- Add more sentiment-based advice or visualizations.
- Implement a dashboard with Supabase’s dashboard tools.

---

### **4. Troubleshooting**
If you need to update the repo later:
```bash
git add .
git commit -m "Your message"
git push origin master

5. GitHub Workflow
You can now:

Make changes locally → git add . → git commit → git push.
Use GitHub’s web interface to edit files or manage issues.