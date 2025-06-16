import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from fastapi import FastAPI, Request
import telebot
from threading import Thread

TELEGRAM_BOT_TOKEN = "8117708405:AAElWMEFHdpvbLkH0XCNuBUMWbWKGIakWP4"
ADMIN_CHAT_ID = 5711313662

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = FastAPI()

# قائمة البروكسيات لاستخدامها بالتناوب
PROXIES = [
    "http://77.242.177.57:3128",     # بلجيكا
    "http://186.233.42.167:3128",    # البرازيل
    "http://103.67.16.26:3128",      # إندونيسيا
    "http://45.42.196.122:3128",     # الولايات المتحدة
    "http://164.163.42.17:10000",    # الأرجنتين
]

# متغير لتخزين رموز التحقق المرتبطة بالحسابات
verification_codes = {}

# تشغيل بوت تيليجرام في Thread منفصل حتى لا يوقف asyncio loop
def telegram_polling():
    bot.infinity_polling()

Thread(target=telegram_polling, daemon=True).start()

@bot.message_handler(commands=['code'])
def handle_code(message):
    """
    استقبال رمز التحقق عبر امر /code 123456
    """
    chat_id = message.chat.id
    if chat_id != ADMIN_CHAT_ID:
        return
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ الصيغة خاطئة، استخدم /code <الرمز>")
            return
        code = parts[1]
        # نفترض الحساب الذي ينتظر الكود هو الاخير في القائمة
        if len(tikreporter.accounts) == 0:
            bot.reply_to(message, "⚠️ لا يوجد حساب ينتظر رمز تحقق الآن.")
            return
        email = tikreporter.accounts[-1]['email']
        verification_codes[email] = code
        bot.reply_to(message, f"✅ تم تسجيل رمز التحقق للحساب {email}")
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ: {e}")

class TikTokReporter:
    def __init__(self):
        self.accounts = []  # قائمة حسابات تحتوي على info و page و context
        self.playwright = None
        self.browser = None
        self.telegram_bot = bot
        self.proxy_index = 0  # لعمل تناوب بين البروكسيات

    async def start_browser(self):
        self.playwright = await async_playwright().start()
        # تناوب البروكسي لكل مرة نفتح المتصفح
        proxy = PROXIES[self.proxy_index % len(PROXIES)]
        self.proxy_index += 1

        self.browser = await self.playwright.chromium.launch(
            headless=True,
            proxy={"server": proxy},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        self.telegram_bot.send_message(ADMIN_CHAT_ID, f"🚀 تم تشغيل المتصفح مع البروكسي: {proxy}")

    async def stop_browser(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def login_account(self, email, password):
        context = await self.browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.tiktok.com/login")

        try:
            await page.click("text='Use phone / email / username'")
            await page.wait_for_timeout(1000)
            
            await page.fill('input[name="username"]', email)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(1000)
            
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(3000)

            if await page.is_visible('input[name="verificationCode"]'):
                self.telegram_bot.send_message(ADMIN_CHAT_ID, f"⏳ حساب {email} طلب رمز تحقق. الرجاء إرسال الرمز عبر بوت التيليجرام باستخدام /code <الرمز>")

                # الانتظار حتى يتم إدخال رمز التحقق عبر البوت (مدة انتظار 120 ثانية)
                for _ in range(120):
                    await asyncio.sleep(1)
                    if email in verification_codes:
                        code = verification_codes[email]
                        await page.fill('input[name="verificationCode"]', code)
                        await page.click('button[type="submit"]')
                        await page.wait_for_timeout(3000)
                        break
                else:
                    self.telegram_bot.send_message(ADMIN_CHAT_ID, f"❌ لم يتم إدخال رمز التحقق في الوقت المناسب للحساب {email}")
                    await context.close()
                    return None

            if "login" not in page.url:
                self.telegram_bot.send_message(ADMIN_CHAT_ID, f"✅ تم تسجيل الدخول بنجاح للحساب {email}")
                self.accounts.append({'email': email, 'password': password, 'context': context, 'page': page})
                return True
            else:
                self.telegram_bot.send_message(ADMIN_CHAT_ID, f"❌ فشل تسجيل الدخول للحساب {email}")
                await context.close()
                return False

        except PlaywrightTimeout:
            self.telegram_bot.send_message(ADMIN_CHAT_ID, f"⚠️ مهلة انتهاء التسجيل للحساب {email}")
            await context.close()
            return False
        except Exception as e:
            self.telegram_bot.send_message(ADMIN_CHAT_ID, f"❌ خطأ أثناء تسجيل الدخول {email}:\n{e}")
            await context.close()
            return False

    async def collect_posts(self, page, user_url):
        await page.goto(user_url)
        await page.wait_for_timeout(5000)
        posts = set()
        try:
            videos = await page.query_selector_all('a[href*="/video/"]')
            for video in videos:
                href = await video.get_attribute('href')
                if href and href.startswith("/@"):
                    href = "https://www.tiktok.com" + href
                if href:
                    posts.add(href)
        except Exception:
            pass
        return list(posts)

    async def report_post(self, page, post_url):
        try:
            await page.goto(post_url)
            await page.wait_for_timeout(3000)
            await page.click('button[aria-label="More actions"]')
            await page.wait_for_timeout(1000)
            await page.click('text="Report"')
            await page.wait_for_timeout(1000)
            await page.click('text="Nudity or sexual activity"')
            await page.wait_for_timeout(1000)
            await page.click('text="Submit"')
            await page.wait_for_timeout(1000)
            return True
        except Exception as e:
            self.telegram_bot.send_message(ADMIN_CHAT_ID, f"⚠️ فشل الإبلاغ عن {post_url}:\n{e}")
            return False

    async def report_account(self, user_url):
        for idx, acc in enumerate(self.accounts):
            page = acc['page']
            self.telegram_bot.send_message(ADMIN_CHAT_ID, f"🚩 الحساب {idx+1} يبدأ الإبلاغ عن منشورات {user_url}")
            posts = await self.collect_posts(page, user_url)
            if not posts:
                self.telegram_bot.send_message(ADMIN_CHAT_ID, "⚠️ لم يتم العثور على منشورات للحساب.")
                return {"status": "no_posts"}
            results = []
            for post in posts:
                success = await self.report_post(page, post)
                if success:
                    self.telegram_bot.send_message(ADMIN_CHAT_ID, f"✅ تم الإبلاغ عن المنشور:\n{post}")
                    results.append({"post": post, "reported": True})
                else:
                    self.telegram_bot.send_message(ADMIN_CHAT_ID, f"❌ فشل الإبلاغ عن المنشور:\n{post}")
                    results.append({"post": post, "reported": False})
            return {"status": "done", "results": results}

tikreporter = TikTokReporter()

@app.on_event("startup")
async def startup_event():
    await tikreporter.start_browser()

@app.on_event("shutdown")
async def shutdown_event():
    await tikreporter.stop_browser()

@app.post("/login_and_report")
async def login_and_report(request: Request):
    """
    واجهة API لاستقبال بيانات الحسابات ورابط الحساب المخالف
    {"accounts": [{"email": "...", "password": "..."}, ...], "target_url": "..."}
    """
    data = await request.json()
    accounts_data = data.get("accounts", [])
    target_url = data.get("target_url")

    tikreporter.accounts.clear()
    verification_codes.clear()

    # تسجيل الدخول لكل الحسابات
    for acc in accounts_data:
        email = acc.get("email")
        password = acc.get("password")
        success = await tikreporter.login_account(email, password)
        if not success:
            return {"status": "error", "message": f"فشل تسجيل الدخول للحساب {email}"}

    # الإبلاغ عن الحساب المخالف
    report_result = await tikreporter.report_account(target_url)
    return report_result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
