from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from supabase import create_client
from dotenv import load_dotenv
import os
import requests
from word2number import w2n
from telegram import Update
from telegram.ext import CommandHandler
from telegram.ext import Application

load_dotenv()

# Initialize Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

# User states management
user_states = {}

# Sentiment mapping for trader context
SENTIMENT_MAP = {
    "joy": "confident",
    "fear": "uncertain",
    "anger": "frustrated",
    "sadness": "disappointed",
    "surprise": "surprised",
    "neutral": "neutral",
    "disgust": "disgusted"
}

# Trading-specific advice
SENTIMENT_ADVICE = {
    "confident": "🚀 Confidence is key! Remember to always protect profits with a trailing stop.",
    "frustrated": "🔥 Frustration is normal. Take a break and revisit your strategy with fresh eyes.",
    "disappointed": "😞 Don't let this shake your confidence. Every trader has off days.",
    "uncertain": "🤔 Uncertainty means you need clearer rules. Review your trading plan."
}

async def start(update: Update, context):
    await update.message.reply_text(
        "Hey there, trader! 📊 Let's track your progress.\n\n"
        "Use /logtrade [TradingView link] to start logging.\n"
        "Need help? Just ask: 'How do I log a trade?'"
    )

async def log_trade(update: Update, context):
    try:
        tradingview_link = context.args[0]
        if "tradingview.com" not in tradingview_link:
            raise ValueError
        
        user_id = update.message.from_user.id
        context.user_data["tradingview_link"] = tradingview_link
        user_states[user_id] = "awaiting_outcome"
        
        await update.message.reply_text(
            "Alright, let's break this down 🧠\n"
            "What was the outcome? You can say:\n"
            "  '+500' or 'I profited 500'\n"
            "  '-200' or 'Lost two hundred'"
        )
    except:
        await update.message.reply_text(
            "⚠️ Oops! Please share a valid TradingView link.\n"
            "Example: /logtrade https://tradingview.com/chart/xyz123"
        )

def parse_outcome(text):
    text = text.lower().replace("hundred", "00").replace("thousand", "000")
    
    try:
        # Handle word numbers like "three hundred"
        return w2n.word_to_num(text)
    except:
        # Handle mixed formats like "3 hundred" or "500 bucks"
        numbers = [int(s) for s in text.split() if s.lstrip('-+').isdigit()]
        return numbers[0] if numbers else None

async def analyze_sentiment(text):
    API_URL = "https://api-inference.huggingface.co/models/bhadresh-savani/distilbert-base-uncased-emotion"
    headers = {"Authorization": f"Bearer {os.getenv('HUGGINGFACE_TOKEN')}"}
    
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": text})
        if response.status_code == 200:
            result = response.json()[0]
            raw_sentiment = max(result, key=lambda x: x['score'])['label']
            sentiment = SENTIMENT_MAP.get(raw_sentiment, "neutral")
            
            # Context-specific advice
            if "stop-loss" in text.lower():
                advice = "🛑 You mentioned stop-loss - did you stick to your plan? Adjust if needed!"
            elif "overleveraged" in text.lower():
                advice = "⚠️ Overleveraged? Reduce position size to stay calm."
            else:
                advice = SENTIMENT_ADVICE.get(sentiment, "")
            
            return sentiment, advice
        else:
            return "neutral", "My sentiment analysis is having a moment 🙃 Let's log it anyway!"
    except:
        return "neutral", "Hmm, my brain glitched! Let's focus on the numbers for now."

async def handle_message(update: Update, context):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    # Handle outcome input
    if user_states.get(user_id) == "awaiting_outcome":
        outcome = parse_outcome(text)
        
        if outcome is None:
            await update.message.reply_text(
                "🤔 I didn't quite get that. Try:\n"
                "  '+500', '-200'\n"
                "  'I made three hundred'\n"
                "  'Lost 2 hundred'"
            )
            return
        
        context.user_data["outcome"] = outcome
        user_states[user_id] = "awaiting_sentiment"
        
        await update.message.reply_text(
            "How did this trade make you feel? 😊/😟/😐\n"
            "Tell me anything - 'I was nervous', 'Felt like a pro', etc."
        )
    
    # Handle sentiment input
    elif user_states.get(user_id) == "awaiting_sentiment":
        sentiment, advice = await analyze_sentiment(text)
        
        trade_data = {
            "user_id": user_id,
            "tradingview_link": context.user_data["tradingview_link"],
            "outcome": context.user_data["outcome"],
            "sentiment": sentiment,
            "notes": text
        }
        
        supabase.table("trades").insert(trade_data).execute()
        
        # Human-like response
        response = f"Logged! Detected: {sentiment.upper()} sentiment\n\n"
        if advice:
            response += f"💡 Advice: {advice}"
        
        await update.message.reply_text(response)
        user_states[user_id] = None

    # Handle general messages
    else:
        if text.lower() in ["help", "how to use"]:
            await update.message.reply_text(
                "COMMANDS:\n"
                "/logtrade [link] - Log new trade\n"
                "/stats - View performance\n"
                "Talk to me like a human - I'll understand!"
            )
        else:
            await update.message.reply_text(
                "Let's log some trades! Use /logtrade [TradingView link] "
                "or ask for help if you're stuck 🤝"
            )

async def show_stats(update: Update, context):
    user_id = update.message.from_user.id
    response = supabase.rpc(
        "calculate_metrics", 
        {"input_user_id": user_id}
    ).execute()
    
    metrics = response.data[0] if response.data else None
    if not metrics or metrics.get("total_trades", 0) == 0:
        await update.message.reply_text("📊 No trades logged yet! Use /logtrade to get started.")
        return
    
    message = "📊 **Your Trading Metrics**:\n\n"
    message += f"• Total Trades: {metrics.get('total_trades', 0)} 📉\n"
    message += f"• Win Rate: {metrics.get('win_rate', 0)}% 🏆\n"
    message += f"• Avg Win: ${metrics.get('avg_win', 0)} 🟢\n"
    message += f"• Avg Loss: ${metrics.get('avg_loss', 0)} 🔴\n"
    message += f"• Risk-Reward Ratio: {metrics.get('risk_reward_ratio', 0)}:1 ⚖️\n\n"
    
    if metrics.get("risk_reward_ratio", 0) < 1:
        message += "⚠️ Your risk-reward ratio is below 1. Consider larger profit targets!"
    elif metrics.get("win_rate", 0) < 50:
        message += "💡 Low win rate? Focus on refining your entry/exit criteria."
    
    await update.message.reply_text(message)

async def weekly_report(context):
    try:
        # Get distinct user IDs using Python
        response = supabase.table("trades").select("user_id").execute()
        users = list({user["user_id"] for user in response.data})
        
        for user in users:
            user_id = user["user_id"]
            
            # Use correct parameter name for stored procedure
            response_metrics = supabase.rpc(
                "calculate_metrics", 
                {"input_user_id": user_id}  # Match your stored procedure's parameter
            ).execute()
            
            metrics = response_metrics.data[0] if response_metrics.data else None
            
            if not metrics:
                continue
            
            message = f"🗓️ **Weekly Report for User {user_id}**:\n"
            message += f"• Total Trades: {metrics.get('total_trades', 0)}\n"
            message += f"• Win Rate: {metrics.get('win_rate', 0)}%\n"
            message += f"• Risk-Reward: {metrics.get('risk_reward_ratio', 0)}:1\n"
            
            await context.bot.send_message(chat_id=user_id, text=message)
            
    except Exception as e:
        print(f"Error in weekly_report: {str(e)}")

# At the bottom of bot.py
if __name__ == "__main__":
    # Initialize the job queue with the application
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    # Schedule weekly reports
    job_queue = app.job_queue
    job_queue.run_repeating(weekly_report, interval=604800, first=10)  # 1 week
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("logtrade", log_trade))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Trader Bot is online!")
    app.run_polling()