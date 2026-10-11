إليك التعديل على قالب الرسالة ليطابق النموذج الذي طلبته تماماً وبصياغة عربية جذابة وواضحة:
💻 الكود المحدث بالكامل مع صيغة الرسالة الجديدة:
import os
import time
import asyncio
import requests
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from supabase import create_client, Client
import threading

# إعدادات البوت والاتصال
TOKEN = os.getenv("BOT_TOKEN", "8938116145:AAHkVV0geUtkdOh04pZgdzQpxL0qVchO6Io")
CHANNEL_ID = "@neoearnboot"
REF_LINK = os.getenv("REF_LINK", "https://t.me/DRAGON_STONE_BOT?start=ref_8557464787")

# إعداد قاعدة بيانات Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

app = Flask(__name__)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

# الكلمات المفتاحية للحالات المختلفة
ENDED_KEYWORDS = [
    "Raffle results", "Results are in", "Winners", "Revealed seed",
    "No prize this time", "Credited", "1 participant"
]

UPCOMING_KEYWORDS = [
    "Starts in", "Coming soon", "Opening soon", "Starts on"
]

ACTIVE_KEYWORDS = [
    "Free raffle", "Results in", "You have joined", "Invite a friend"
]

NOT_FOUND_KEYWORDS = [
    "Raffle not found", "The link may be outdated", "raffle was removed"
]

def check_contest_status(page_text):
    if not page_text:
        return "NOT_FOUND"
    text_lower = page_text.lower()
    
    for kw in NOT_FOUND_KEYWORDS:
        if kw.lower() in text_lower:
            return "NOT_FOUND"
    for kw in ENDED_KEYWORDS:
        if kw.lower() in text_lower:
            return "ENDED"
    for kw in UPCOMING_KEYWORDS:
        if kw.lower() in text_lower:
            return "UPCOMING"
    for kw in ACTIVE_KEYWORDS:
        if kw.lower() in text_lower:
            return "ACTIVE"
            
    return "UNKNOWN"

def fetch_page_content(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
    return None

def save_to_database(contest_id, status):
    if not supabase:
        print(f"[Mock DB] Contest #{contest_id} saved with status: {status}")
        return
    try:
        supabase.table("contests").upsert({
            "contest_id": contest_id,
            "status": status
        }).execute()
    except Exception as e:
        print(f"Supabase save error: {e}")

async def publish_to_channel(contest_id, time_left="قريباً"):
    """نشر المسابقة بالقالب الجديد المطلوب"""
    text = (
        f"🎁 **مسابقة جديدة قيد انتضارك**\n\n"
        f"⏳ تبقى **{time_left}** على نهاية المسابقة\n\n"
        f"👇 **شارك في السحب من هنا**"
    )
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🚀 شارك في السحب الآن", url=REF_LINK)]
    ])
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=text, reply_markup=keyboard)
        print(f"Successfully published contest #{contest_id}")
    except Exception as e:
        print(f"Error publishing to channel: {e}")

def background_scanner():
    current_id = 870
    upcoming_queue = []
    
    while True:
        try:
            # 1. فحص المسابقة بالرقم الرئيسي الحالي
            url = f"https://t.me/Randombot?start=raffle_{current_id}"
            html_content = fetch_page_content(url)
            status = check_contest_status(html_content)
            
            if status == "ACTIVE":
                asyncio.run(publish_to_channel(current_id))
                save_to_database(current_id, "ACTIVE")
                current_id += 1
                
            elif status in ["ENDED", "NOT_FOUND"]:
                save_to_database(current_id, status)
                current_id += 1
                
            elif status == "UPCOMING":
                if not any(item['id'] == current_id for item in upcoming_queue) and len(upcoming_queue) < 10:
                    upcoming_queue.append({"id": current_id, "url": url})
                current_id += 1
                
            # 2. فحص طابور المراقبة (الـ 10 روابط) وتحديث حالاتها
            for item in list(upcoming_queue):
                item_content = fetch_page_content(item['url'])
                item_status = check_contest_status(item_content)
                
                if item_status == "ACTIVE":
                    asyncio.run(publish_to_channel(item['id']))
                    save_to_database(item['id'], "ACTIVE")
                    upcoming_queue.remove(item)
                    
                elif item_status in ["ENDED", "NOT_FOUND"]:
                    save_to_database(item['id'], item_status)
                    upcoming_queue.remove(item)
                    
            # 3. تعويض الروابط المنتهية أو المحذوفة للحفاظ على 10 روابط في الطابور
            while len(upcoming_queue) < 10:
                new_url = f"https://t.me/Randombot?start=raffle_{current_id}"
                new_content = fetch_page_content(new_url)
                new_status = check_contest_status(new_content)
                
                if new_status == "ACTIVE":
                    asyncio.run(publish_to_channel(current_id))
                    save_to_database(current_id, "ACTIVE")
                    current_id += 1
                elif new_status in ["ENDED", "NOT_FOUND"]:
                    save_to_database(current_id, new_status)
                    current_id += 1
                elif new_status == "UPCOMING":
                    upcoming_queue.append({"id": current_id, "url": new_url})
                    current_id += 1
                else:
                    current_id += 1
                    
            # الانتظار لمدة دقيقة كاملة (60 ثانية) قبل الدورة التالية
            time.sleep(60)
            
        except Exception as e:
            print(f"Scanner loop error: {e}")
            time.sleep(60)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_data = request.get_json()
        update = types.Update.de_json(json_data)
        asyncio.run(dp.feed_update(bot=bot, update=update))
        return '', 200
    return 'OK', 200

@app.route('/')
def index():
    return "🤖 بوت تتبع وبث المسابقات يعمل بنجاح!"

if __name__ == '__main__':
    scanner_thread = threading.Thread(target=background_scanner, daemon=True)
    scanner_thread.start()
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))
