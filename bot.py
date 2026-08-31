import os
import json
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
BOT_TOKEN = "8682783383:AAE3VwXtQKduoqwDkXW4IAaVLUufCwp_q8Y"
ADMIN_ID = 7540000713
CONNECTED_DEVICES = {}
ACTIVITY_LOG = []

# Initialize Telegram Bot Application
application = Application.builder().token(BOT_TOKEN).build()

# Store connected devices
def save_device(device_id, user_id, username):
    CONNECTED_DEVICES[device_id] = {
        'user_id': user_id,
        'username': username,
        'timestamp': __import__('datetime').datetime.now().isoformat(),
        'status': 'online'
    }

def remove_device(device_id):
    if device_id in CONNECTED_DEVICES:
        del CONNECTED_DEVICES[device_id]

def log_activity(action, device_id=None):
    ACTIVITY_LOG.append({
        'time': __import__('datetime').datetime.now().isoformat(),
        'action': action,
        'device': device_id
    })
    # Keep only last 100 logs
    if len(ACTIVITY_LOG) > 100:
        ACTIVITY_LOG.pop(0)

# Telegram Bot Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - Send welcome message"""
    await update.message.reply_text(
        "🎮 **Mobile Control System**\n\n"
        "Commands:\n"
        "/allow - दिन के लिए access दो\n"
        "/deny - Access revoke करो\n"
        "/status - Device status देखो\n"
        "/dashboard - Admin dashboard\n",
        parse_mode="Markdown"
    )

async def allow_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow access command"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    device_id = f"DEV-{user_id}-{__import__('time').time()}"
    
    save_device(device_id, user_id, username)
    log_activity(f"✅ Device Connected - {username}", device_id)
    
    # Send to admin
    admin_app = application
    try:
        await admin_app.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🟢 **नया Device Connected!**\n\n"
                 f"👤 User: @{username}\n"
                 f"🆔 ID: {user_id}\n"
                 f"📱 Device: {device_id}\n"
                 f"⏰ Time: {CONNECTED_DEVICES[device_id]['timestamp']}\n\n"
                 f"अब तुम इस device को control कर सकते हो!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send message to admin: {e}")
    
    await update.message.reply_text(
        f"✅ **Access Granted!**\n\n"
        f"🆔 Device ID: `{device_id}`\n"
        f"अपना mobile सामान्य तरीके से use कर सकते हो।\n"
        f"Controller को तुम्हारा device दिख रहा है।",
        parse_mode="Markdown"
    )

async def deny_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deny access command"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    # Remove all devices for this user
    devices_to_remove = [d for d, info in CONNECTED_DEVICES.items() if info['user_id'] == user_id]
    for device in devices_to_remove:
        remove_device(device)
        log_activity(f"❌ Device Disconnected - {username}", device)
    
    # Notify admin
    try:
        await application.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ **Device Disconnected**\n\n"
                 f"👤 User: @{username}\n"
                 f"🆔 ID: {user_id}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send message to admin: {e}")
    
    await update.message.reply_text(
        "❌ Access revoked!\n"
        "Device अब नियंत्रण के लिए उपलब्ध नहीं है।"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show device status"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    user_devices = [d for d, info in CONNECTED_DEVICES.items() if info['user_id'] == user_id]
    
    if not user_devices:
        await update.message.reply_text("❌ कोई device connected नहीं है।")
        return
    
    message = f"📱 **तुम्हारे Devices:** ({len(user_devices)})\n\n"
    for device in user_devices:
        info = CONNECTED_DEVICES[device]
        message += f"🆔 {device}\n"
        message += f"⏰ Connected: {info['timestamp']}\n"
        message += f"🟢 Status: {info['status']}\n\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin dashboard"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access only!")
        return
    
    total_devices = len(CONNECTED_DEVICES)
    
    message = f"📊 **Dashboard**\n\n"
    message += f"🟢 Total Connected Devices: {total_devices}\n\n"
    
    if CONNECTED_DEVICES:
        message += "**Connected Devices:**\n"
        for device, info in CONNECTED_DEVICES.items():
            message += f"  • {device} - @{info['username']}\n"
    
    message += f"\n\n**Recent Activity:**\n"
    for log in ACTIVITY_LOG[-5:]:
        message += f"  • {log['action']}\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

# Flask Routes for Web Integration
@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Get all connected devices"""
    return jsonify({
        'devices': CONNECTED_DEVICES,
        'count': len(CONNECTED_DEVICES)
    })

@app.route('/api/device/<device_id>', methods=['GET'])
def get_device(device_id):
    """Get specific device info"""
    if device_id in CONNECTED_DEVICES:
        return jsonify(CONNECTED_DEVICES[device_id])
    return jsonify({'error': 'Device not found'}), 404

@app.route('/api/activity', methods=['GET'])
def get_activity():
    """Get activity log"""
    return jsonify({'activity': ACTIVITY_LOG})

@app.route('/api/control/<device_id>', methods=['POST'])
def control_device(device_id):
    """Execute control command"""
    data = request.get_json()
    command = data.get('command')
    
    if device_id not in CONNECTED_DEVICES:
        return jsonify({'error': 'Device not found'}), 404
    
    log_activity(f"🎮 Command: {command}", device_id)
    
    return jsonify({
        'status': 'success',
        'command': command,
        'device': device_id
    })

@app.route('/', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'running',
        'devices': len(CONNECTED_DEVICES),
        'bot_token': BOT_TOKEN[:20] + '...'
    })

# Setup bot handlers
async def setup_handlers():
    """Setup all handlers"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("allow", allow_access))
    application.add_handler(CommandHandler("deny", deny_access))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("dashboard", dashboard))

if __name__ == '__main__':
    import asyncio
    
    # Setup handlers
    asyncio.run(setup_handlers())
    
    # Run Flask app
    app.run(debug=False, port=5000)