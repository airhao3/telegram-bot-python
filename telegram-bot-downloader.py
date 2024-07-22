import logging
import re
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import yt_dlp
from dotenv import load_dotenv

#加载.env文件中的环境变量
load_dotenv()

#将环境变量中的token赋值给TOKEN
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! Send me a video URL to download.",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Send me a video URL, and I'll download it for you!")

def is_url(text):
    """Check if the given text is a URL."""
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    return bool(url_pattern.match(text))

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download the video from the provided URL."""
    message_text = update.message.text
    if is_url(message_text):
        await update.message.reply_text("Starting download. Please wait...")
        try:
            ydl_opts = {
                'outtmpl': '%(title)s.%(ext)s',
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(message_text, download=True)
                filename = ydl.prepare_filename(info)
                filename = os.path.splitext(filename)[0] + '.mp3'  # Change extension to mp3
            
            # Send the downloaded file
            await update.message.reply_document(document=open(filename, 'rb'))
            
            # Delete the file after sending
            os.remove(filename)
            
            await update.message.reply_text("Download completed and file sent!")
        except Exception as e:
            await update.message.reply_text(f"An error occurred: {str(e)}")
    else:
        await update.message.reply_text("This is not a valid URL. Please send a video URL.")

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()