import os
import re
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from supabase import create_client
from dotenv import load_dotenv
import requests
from word2number import w2n
import telegram.error

# Initialize logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
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

SENTIMENT_ADVICE = {
    "confident": "🚀 Confidence is key! Remember to always protect profits with a trailing stop.",
    "frustrated": "🔥 Frustration is normal. Take a break and revisit your strategy with fresh eyes.",
    "disappointed": "😞 Don't let this shake your confidence. Every trader has off days.",
    "uncertain": "🤔 Uncertainty means you need clearer rules. Review your trading plan."
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "Hey there, trader! 📊 Let's track your progress.\n\n"
            "Use /logtrade [TradingView link] to start logging.\n"
            "Need help? Just ask: 'How do I log a trade?'"
        )
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}")

async def log_trade(update: Update, context):
    try:
        if not context.args:
            raise ValueError("No TradingView link provided")
        
        tradingview_link = context.args[0].strip()
        
        # Basic validation: Must contain "tradingview.com" and start with "https://"
        if "tradingview.com" not in tradingview_link.lower() or not tradingview_link.startswith("https://"):
            raise ValueError("Invalid TradingView link format")
        
        user_id = update.message.from_user.id
        context.user_data["tradingview_link"] = tradingview_link
        user_states[user_id] = "awaiting_outcome"
        
        await update.message.reply_text(
            "Alright, let's break this down 🧠\n"
            "What was the outcome? You can say:\n"
            "  '+500' or 'I profited 500'\n"
            "  '-200' or 'Lost two hundred'"
        )
    except Exception as e:
        logger.error(f"Error in log_trade: {str(e)}")
        await update.message.reply_text(
            "⚠️ Oops! Please share a valid TradingView link.\n"
            "Example: /logtrade https://www.tradingview.com/x/your_id_here/"
        )

def parse_outcome(text):
    try:
        text = text.lower()
        replacements = {
            "hundred": "00",
            "thousand": "000",
            "k": "000",
            "m": "000000"
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        
        # Try word-to-number first
        try:
            return w2n.word_to_num(text)
        except:
            # Fallback to extracting numbers
            numbers = re.findall(r"[-+]?\d+", text)
            return int(numbers[0]) if numbers else None
    except Exception as e:
        logger.error(f"Error parsing outcome: {str(e)}")
        return None

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
                advice = "🛑 You mentioned stop-loss. Did you stick to your plan? Adjust if needed!"
            elif "overleveraged" in text.lower():
                advice = "⚠️ Overleveraged? Reduce position size to stay calm."
            else:
                advice = SENTIMENT_ADVICE.get(sentiment, "")
            
            return sentiment, advice
        else:
            logger.error(f"HuggingFace API error: {response.text}")
            return "neutral", "My sentiment analysis is having a moment 🙃 Let's log it anyway!"
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {str(e)}")
        return "neutral", "Hmm, my brain glitched! Focus on the numbers for now."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        text = update.message.text.strip()

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
        
        elif user_states.get(user_id) == "awaiting_sentiment":
            sentiment, advice = await analyze_sentiment(text)
            
            trade_data = {
                "user_id": user_id,
                "tradingview_link": context.user_data["tradingview_link"],
                "outcome": context.user_data["outcome"],
                "sentiment": sentiment,
                "notes": text,
                "timestamp": "now()"  # Let Supabase handle timestamp
            }
            
            try:
                supabase.table("trades").insert(trade_data).execute()
                response = f"✅ Trade logged! Detected: {sentiment.upper()} sentiment\n\n"
                if advice:
                    response += f"💡 Advice: {advice}"
            except Exception as e:
                logger.error(f"Supabase insert failed: {str(e)}")
                response = "❌ Failed to save trade. Please try again later."
            
            await update.message.reply_text(response)
            user_states[user_id] = None

        else:
            if text.lower() in ["help", "how to use"]:
                await update.message.reply_text(
                    "📌 COMMANDS:\n"
                    "/logtrade [link] - Log new trade\n"
                    "/stats - View performance\n"
                    "Talk to me like a human - I'll understand!"
                )
            else:
                await update.message.reply_text(
                    "Let's log some trades! Use /logtrade [TradingView link] "
                    "or ask for help if you're stuck 🤝"
                )
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        await update.message.reply_text("⚠️ Something went wrong. Please try again.")

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        response = supabase.rpc(
            "calculate_metrics",
            {"input_user_id": user_id}
        ).execute()
        
        if not response.data:
            await update.message.reply_text("📊 No trades logged yet! Use /logtrade to get started.")
            return
        
        metrics = response.data[0]
        message = "📊 **Your Trading Metrics**:\n\n"
        message += f"• Total Trades: {metrics.get('total_trades', 0)} 📉\n"
        message += f"• Win Rate: {metrics.get('win_rate', 0)}% 🏆\n"
        message += f"• Avg Win: ${metrics.get('avg_win', 0):.2f} 🟢\n"
        message += f"• Avg Loss: ${metrics.get('avg_loss', 0):.2f} 🔴\n"
        message += f"• Risk-Reward Ratio: {metrics.get('risk_reward_ratio', 0):.2f}:1 ⚖️\n\n"
        
        if metrics.get("risk_reward_ratio", 0) < 1:
            message += "⚠️ Your risk-reward ratio is too low. Focus on larger profit targets!"
        elif metrics.get("win_rate", 0) < 50:
            message += "💡 Low win rate? Review your entry/exit rules."
        
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in show_stats: {str(e)}")
        await update.message.reply_text("⚠️ Error fetching stats. Please try again later.")

async def weekly_report(context):
    try:
        # Fetch distinct user IDs correctly
        response = supabase.table("trades").select("user_id").distinct().execute()
        users = response.data  # Returns [{'user_id': 123}, ...]
        
        for user in users:
            user_id = user["user_id"]
            
            # Fetch metrics using the renamed parameter "input_user_id"
            response_metrics = supabase.rpc(
                "calculate_metrics",
                {"input_user_id": user_id}  # Use the correct parameter name
            ).execute()
            metrics = response_metrics.data[0] if response_metrics.data else None
            
            if not metrics:
                continue
            
            message = f"🗓️ **Weekly Report for User {user_id}**:\n"
            message += f"• Total Trades: {metrics.get('total_trades', 0)}\n"
            message += f"• Win Rate: {metrics.get('win_rate', 0)}%\n"
            message += f"• Risk-Reward: {metrics.get('risk_reward_ratio', 0):.2f}:1\n"
            
            await context.bot.send_message(chat_id=user_id, text=message)
            
    except Exception as e:
        print(f"Error in weekly_report: {str(e)}")

def main():
    # Verify environment variables
    required_env_vars = ["TELEGRAM_TOKEN", "SUPABASE_URL", "SUPABASE_KEY"]
    for var in required_env_vars:
        if not os.getenv(var):
            raise ValueError(f"Missing required environment variable: {var}")

    # Initialize bot
    application = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("logtrade", log_trade))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Schedule weekly reports (use 86400 for daily testing)
    job_queue = application.job_queue
    job_queue.run_repeating(weekly_report, interval=604800, first=10)  # 1 week
    
    # Start the bot
    logger.info("🤖 Trader Bot is online!")
    application.run_polling()

if __name__ == "__main__":
    main()