import os
import subprocess
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)

# States
ASK_START, ASK_END, ASK_DURATION, ASK_NAME = range(4)

video_path = "input.mp4"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Please upload your video file (MP4 format).")
    return

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("❌ This is not a valid video.")
        return

    await update.message.reply_text("📥 Downloading video...")
    file = await video.get_file()
    await file.download_to_drive(video_path)
    await update.message.reply_text("✅ Video downloaded!\n\n🕐 Now send the START time (e.g., 00:10:00):")
    return ASK_START

async def ask_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['start_time'] = update.message.text.strip()
    await update.message.reply_text("🕐 Now send the END time (e.g., 00:45:00):")
    return ASK_END

async def ask_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['end_time'] = update.message.text.strip()
    await update.message.reply_text("⏱️ Now send the duration (in seconds) for each clip (e.g., 60 for 1 minute):")
    return ASK_DURATION

async def ask_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['duration'] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Send duration in seconds, like 60.")
        return ASK_DURATION
    await update.message.reply_text("📛 Now send the base name for your videos (e.g., Squid Game):")
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['base_name'] = update.message.text.strip()

    await update.message.reply_text("🎬 Processing your request. Please wait...")

    # Get data
    start = context.user_data['start_time']
    end = context.user_data['end_time']
    duration = context.user_data['duration']
    base_name = context.user_data['base_name']

    os.makedirs("clips", exist_ok=True)
    trimmed_video = "trimmed.mp4"

    # Step 1: Trim the video
    trim_command = f'ffmpeg -ss {start} -to {end} -i "{video_path}" -c copy "{trimmed_video}" -y'
    subprocess.call(trim_command, shell=True)

    # Step 2: Split it into clips
    split_command = f'ffmpeg -i "{trimmed_video}" -c copy -map 0 -segment_time {duration} -f segment clips/output%03d.mp4 -y'
    subprocess.call(split_command, shell=True)

    # Step 3: Rename and send each clip
    files = sorted(os.listdir("clips"))
    for idx, filename in enumerate(files, start=1):
        new_name = f"{base_name} {idx}.mp4"
        old_path = f"clips/{filename}"
        new_path = f"clips/{new_name}"
        os.rename(old_path, new_path)

        await update.message.reply_video(video=InputFile(new_path), caption=new_name)

    await update.message.reply_text("✅ Done! All clips sent.")

    # Cleanup
    os.remove(video_path)
    os.remove(trimmed_video)
    for f in os.listdir("clips"):
        os.remove(f"clips/{f}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Process cancelled.")
    return ConversationHandler.END

# Build bot
app = ApplicationBuilder().token("8118607834:AAHucoXtSK6qbkenGxmjR8igzFJc-4fV7nI").build()

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video)],
    states={
        ASK_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_start)],
        ASK_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_end)],
        ASK_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_duration)],
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

app.add_handler(CommandHandler("start", start))
app.add_handler(conv_handler)

app.run_polling()
