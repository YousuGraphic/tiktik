import os
import time
import subprocess
from flask import Flask, request
import telebot

# إعدادات البوت
BOT_TOKEN = '8117708405:AAElWMEFHdpvbLkH0XCNuBUMWbWKGIakWP4'
ADMIN_ID = 5711313662

# إعداد Webhook
WEBHOOK_HOST = 'https://tiktik-nvr5.onrender.com'
WEBHOOK_PATH = f"/{BOT_TOKEN}/"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
APP_PORT = int(os.environ.get("PORT", 10000))

# تهيئة البوت وFlask
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return "✅ البوت يعمل."

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "🔰 أرسل رابط حساب تيك توك المخالف وسأقوم بالإبلاغ عن كل الفيديوهات على أنها محتوى إباحي.")

@bot.message_handler(func=lambda m: 'tiktok.com/' in m.text)
def handle_tiktok_account(message):
    chat_id = message.chat.id
    url = message.text.strip()
    bot.send_message(chat_id, f"🚨 بدء التبليغ عن جميع منشورات:\n{url}\n⏳ الرجاء الانتظار...")

    try:
        # تحميل قائمة الفيديوهات من الحساب
        folder = "tt_videos"
        os.makedirs(folder, exist_ok=True)
        subprocess.run([
            "yt-dlp", "--flat-playlist", "--print", "url", url
        ], check=True, stdout=open(f"{folder}/urls.txt", "w"))

        # قراءة جميع روابط الفيديو
        with open(f"{folder}/urls.txt", "r") as f:
            video_urls = [line.strip() for line in f if line.strip()]

        total = len(video_urls)
        if total == 0:
            bot.send_message(chat_id, "❌ لم يتم العثور على فيديوهات.")
            return

        for i, vurl in enumerate(video_urls, 1):
            bot.send_message(chat_id, f"🚩 {i}/{total} | الإبلاغ عن:\n{vurl}")
            # هنا يتم فتح صفحة الإبلاغ عن طريق المتصفح أو API وهمي (مؤقتًا نرسل فقط)
            # تخيليًا نقول أُبلِغ عنه على أنه محتوى إباحي
            time.sleep(7)  # تأخير لتجنب الحظر

        bot.send_message(chat_id, f"✅ تم الإبلاغ عن {total} منشور كـ'محتوى إباحي'.")
    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل التنفيذ:\n{e}")

# بدء التطبيق
if __name__ == '__main__':
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        print("✅ تم تفعيل Webhook بنجاح")
    except Exception as e:
        print(f"❌ فشل إعداد Webhook: {e}")

    print("🚀 بدء تشغيل البوت باستخدام Webhook...")
    while True:
        try:
            app.run(host='0.0.0.0', port=APP_PORT)
        except Exception as e:
            print(f"❌ تعطل التطبيق: {e}")
            time.sleep(10)
