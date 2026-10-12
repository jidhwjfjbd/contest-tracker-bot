import os
import sqlite3
import logging
from flask import Flask, request
import requests

TOKEN = os.getenv("BOT_TOKEN", "8938116145:AAHkVV0geUtkdOh04pZgdzQpxL0qVchO6Io")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@neoearnboot")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8557464787"))

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

DB_FILE = "bot_database.db"

# ----------------- قاعدة البيانات ----------------- #

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings 
                 (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('contest_id', '893')")
    conn.commit()
    conn.close()

def get_setting(key, default=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def add_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

init_db()

user_steps = {}

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return requests.post(url, json=payload).json()

def send_telegram_video(chat_id, video, caption, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendVideo"
    payload = {"chat_id": chat_id, "video": video, "caption": caption, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return requests.post(url, json=payload).json()

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        data = request.get_json()
        
        user_id = None
        if "message" in data:
            user_id = data["message"]["from"]["id"]
        elif "callback_query" in data:
            user_id = data["callback_query"]["from"]["id"]
            
        if user_id:
            add_user(user_id)

        # 1. لوحة التحكم للأدمن
        if "callback_query" in data:
            cq = data["callback_query"]
            chat_id = cq["message"]["chat"]["id"]
            from_id = cq["from"]["id"]
            message_id = cq["message"]["message_id"]
            data_action = cq["data"]
            
            if from_id != ADMIN_ID:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", json={
                    "callback_query_id": cq["id"], "text": "⛔ غير مسموح لك بإستخدام هذه اللوحة!", "show_alert": True
                })
                return '', 200

            admin_current_id = int(get_setting("contest_id", "893"))

            if data_action == 'next_id':
                admin_current_id += 1
                set_setting("contest_id", admin_current_id)
            elif data_action == 'prev_id':
                admin_current_id -= 1
                set_setting("contest_id", admin_current_id)
            elif data_action == 'edit_id':
                user_steps[chat_id] = {"step": "waiting_for_custom_id"}
                send_telegram_message(chat_id, "✏️ أرسل الرقم الجديد الذي تريد البدء منه الآن:")
                return '', 200
            elif data_action == 'approve_contest':
                user_steps[chat_id] = {"step": "waiting_for_video", "contest_id": admin_current_id}
                send_telegram_message(chat_id, "🎬 أرسل الآن **الفيديو** الذي تريد أن يظهر على المنشور:")
                return '', 200
            elif data_action == 'broadcast_menu':
                user_steps[chat_id] = {"step": "waiting_for_broadcast"}
                send_telegram_message(chat_id, "📢 أرسل الآن الرسالة التي تريد بثها كرسالة جماعية:")
                return '', 200

            link = f"https://t.me/Randomalbot?startapp=contest_{admin_current_id}__r8557464787"
            text = (
                f"🤖 **لوحة التحكم بالبوت**\n\n"
                f"📌 **رقم المسابقة الحالي:** `{admin_current_id}`\n"
                f"🔗 **الرابط المعتمد:**\n`{link}`"
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "⬅️ السابق", "callback_data": "prev_id"}, {"text": "التالي ➡️", "callback_data": "next_id"}],
                    [{"text": "✏️ تعديل الرقم يدوياً", "callback_data": "edit_id"}],
                    [{"text": "✅ الرابط سليم (ابدأ النشر)", "callback_data": "approve_contest"}],
                    [{"text": "📢 رسالة جماعية", "callback_data": "broadcast_menu"}]
                ]
            }
            requests.post(f"https://api.telegram.org/bot{TOKEN}/editMessageText", json={
                "chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown", "reply_markup": markup
            })

        # 2. معالجة الرسائل
        elif "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            from_id = msg["from"]["id"]
            text = msg.get("text", "")
            
            # رد المستخدم العادي عند الضغط على /start
            if from_id != ADMIN_ID:
                welcome_text = "أهلاً بك! 👋 استخدم البوت للوصول للمسابقات والمشاركة.\n\nإنضم لقناة البوت لتتابع جميع المسابقات:"
                welcome_keyboard = {
                    "inline_keyboard": [
                        [{"text": "📢 قناة البوت الرسمية", "url": f"https://t.me/{CHANNEL_ID.replace('@', '')}"}]
                    ]
                }
                send_telegram_message(chat_id, welcome_text, welcome_keyboard)
                return '', 200

            admin_current_id = int(get_setting("contest_id", "893"))

            # رد الأدمن
            if text == "/start" or text == "/admin":
                user_steps[chat_id] = {}
                link = f"https://t.me/Randomalbot?startapp=contest_{admin_current_id}__r8557464787"
                text_msg = (
                    f"🤖 **مرحباً بك في لوحة تحكم البوت**\n\n"
                    f"📌 **رقم المسابقة الحالي:** `{admin_current_id}`\n"
                    f"🔗 **الرابط المعتمد:**\n`{link}`\n\n"
                    f"👇 اختر الإجراء المناسب:"
                )
                markup = {
                    "inline_keyboard": [
                        [{"text": "⬅️ السابق", "callback_data": "prev_id"}, {"text": "التالي ➡️", "callback_data": "next_id"}],
                        [{"text": "✏️ تعديل الرقم يدوياً", "callback_data": "edit_id"}],
                        [{"text": "📢 رسالة جماعية", "callback_data": "broadcast_menu"}]
                    ]
                }
                send_telegram_message(chat_id, text_msg, markup)
                
            elif chat_id in user_steps and user_steps[chat_id]:
                current_state = user_steps[chat_id].get("step")

                if current_state == "waiting_for_broadcast":
                    user_steps[chat_id] = {}
                    users = get_all_users()
                    send_telegram_message(chat_id, f"⏳ جاري بث الرسالة لـ {len(users)} مستخدمين...")
                    count = 0
                    for u_id in users:
                        try:
                            send_telegram_message(u_id, text)
                            count += 1
                        except Exception:
                            pass
                    send_telegram_message(chat_id, f"✅ تم إرسال البث لـ {count} مستخدم بنجاح!")

                elif current_state == "waiting_for_custom_id":
                    try:
                        new_id = int(text.strip())
                        set_setting("contest_id", new_id)
                        user_steps[chat_id] = {}
                        link = f"https://t.me/Randomalbot?startapp=contest_{new_id}__r8557464787"
                        send_telegram_message(chat_id, f"💾 **تم حفظ الرقم الجديد:** `{new_id}`\n🔗 الرابط:\n`{link}`")
                    except ValueError:
                        send_telegram_message(chat_id, "❌ أرسل رقماً صحيحاً فقط!")
                        
                elif current_state == "waiting_for_video":
                    if "video" in msg:
                        user_steps[chat_id]["video_id"] = msg["video"]["file_id"]
                        user_steps[chat_id]["step"] = "waiting_for_title"
                        send_telegram_message(chat_id, "🆓 أدخل **نوع التوزيع / العنوان** (مثال: `توزيع النجوم`):")
                    else:
                        send_telegram_message(chat_id, "❌ يرجى إرسال فيديو صحيح!")

                elif current_state == "waiting_for_title":
                    user_steps[chat_id]["title"] = text.strip()
                    user_steps[chat_id]["step"] = "waiting_for_prizes_detail"
                    send_telegram_message(chat_id, "🎁 أدخل **عدد الفائزين والجوائز** (مثال: `4 فائزين . لكل منهم 50 نجمة`):")
                    
                elif current_state == "waiting_for_prizes_detail":
                    user_steps[chat_id]["prizes_detail"] = text.strip()
                    user_steps[chat_id]["step"] = "waiting_for_time"
                    send_telegram_message(chat_id, "⏰ أدخل **الوقت المتبقي** (مثال: `4 ساعات و 57 دقيقة`):")
                    
                elif current_state == "waiting_for_time":
                    time_left = text.strip()
                    state_data = user_steps[chat_id]
                    contest_id = state_data.get("contest_id")
                    video_id = state_data.get("video_id")
                    title = state_data.get("title")
                    prizes_detail = state_data.get("prizes_detail")
                    
                    user_steps[chat_id] = {}
                    
                    approved_contest_link = f"https://t.me/Randomalbot?startapp=contest_{contest_id}__r8557464787"
                    
                    caption = (
                        f"🆓 {title}\n\n"
                        f"🎁 الجوائز:\n"
                        f"🏆 {prizes_detail} ⭐\n\n"
                        f"⏰ الوقت المتبقي: {time_left}\n\n"
                        f"👇 لا تفوت فرصة المشاركة!"
                    )
                    
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "🚀 شارك في السحب الآن", "url": approved_contest_link}]
                        ]
                    }
                    
                    # 1. النشر في القناة الأساسية
                    send_telegram_video(CHANNEL_ID, video_id, caption, keyboard)
                    
                    # 2. تنبيه للمستخدمين في المحادثة الخاصة داخل البوت مع رابط القناة
                    alert_text = "🚨 تنبيه مسابقة جديدة في قناة البوت!"
                    alert_keyboard = {
                        "inline_keyboard": [
                            [{"text": "📢 قناة البوت الرسمية", "url": f"https://t.me/{CHANNEL_ID.replace('@', '')}"}]
                        ]
                    }
                    
                    all_u = get_all_users()
                    for u_id in all_u:
                        try:
                            send_telegram_message(u_id, alert_text, alert_keyboard)
                        except Exception:
                            pass

                    send_telegram_message(chat_id, "✅ **تم نشر المسابقة في القناة وإرسال تنبيه المسابقة الجديدة لجميع المستخدمين بنجاح!**\n\nاكتب /admin للعودة.")

        return '', 200
    return 'OK', 200

@app.route('/')
def index():
    return "🤖 البوت يعمل بكفاءة!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))