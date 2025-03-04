import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from yt_dlp import YoutubeDL

# Constants
MAX_REQUESTS_PER_MINUTE = 5
user_requests = {}
users_data = set()

# Logging
logging.basicConfig(level=logging.INFO)

def check_rate_limit(user_id):
    now = datetime.now()
    if user_id in user_requests:
        user_requests[user_id] = [req for req in user_requests[user_id] if now - req < timedelta(minutes=1)]
        if len(user_requests[user_id]) >= MAX_REQUESTS_PER_MINUTE:
            return False
        user_requests[user_id].append(now)
    else:
        user_requests[user_id] = [now]
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users_data.add(user_id)
    await update.message.reply_text("Send me a video link to download.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users = len(users_data)
    await update.message.reply_text(f"Total users: {total_users}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    url = update.message.text
    context.user_data['url'] = url

    if not check_rate_limit(user_id):
        await update.message.reply_text("Rate limit exceeded. Try again later.")
        return

    # Check if the URL is a YouTube link
    if "youtube.com" in url or "youtu.be" in url:
        keyboard = [
            [InlineKeyboardButton("Video", callback_data='video')],
            [InlineKeyboardButton("Audio", callback_data='audio')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Do you want to download video or audio?", reply_markup=reply_markup)
    else:
        await process_download(update, context, url, 'video')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data['url']
    choice = query.data

    # Edit the message to remove buttons
    await query.edit_message_text(text=f"Downloading {choice}... Please wait.")

    await process_download(update, context, url, choice)

async def process_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url, choice):
    user_id = update.effective_user.id
    output_path = f"downloads/{user_id}"
    os.makedirs(output_path, exist_ok=True)

    # Send "Processing..." message
    loading_message = await update.effective_chat.send_message("Processing your request... Please wait.")

    try:
        file_path = download_video(url, output_path, choice)
        if os.path.exists(file_path):
            with open(file_path, "rb") as file:
                await context.bot.send_video(chat_id=update.effective_chat.id, video=file, caption=f"Here is your {choice} file!")
            os.remove(file_path)
        else:
            await update.message.reply_text("Failed to download video.")
    except Exception as e:
        logging.error(f"Download error: {e}")
        await update.message.reply_text("Error processing your request.")
    finally:
        # Remove "Processing..." message
        await loading_message.delete()

def download_video(url, output_path, choice):
    ydl_opts = {
        'format': 'best' if choice == 'video' else 'bestaudio/best',
        'outtmpl': f"{output_path}/%(title)s.%(ext)s",
        'quiet': True
    }
    with YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info_dict)

def main():
    application = ApplicationBuilder().token("YOUR_BOT_TOKEN").build() #add your bot token here...
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling()

if __name__ == '__main__':
    main()
