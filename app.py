import os
import re
import time
import threading
import requests
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

# ==========================================
# 1. Configuration & Constants
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL", "YOUR_SUPABASE_POSTGRES_URL")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@your_channel_username")

# إعدادات بداية التتبع والمدى التنبؤي
START_CONTEST_ID = int(os.environ.get("START_CONTEST_ID", 870))
LOOKAHEAD_LIMIT = 20  # عدد المسابقات غير البدء المسموح بفحصها للأمام

# الكلمات المفتاحية للتحقق من عدم صلاحية أو انتهاء المسابقة
EXPIRED_KEYWORDS = [
    "expired", "closed", "ended", "not found", "invalid", 
    "انتهت", "مغلقة", "غير موجودة", "غير متاحة"
]

# الكلمات المفتاحية الإيجابية الواجب توفرها لاستيفاء الشروط
REQUIRED_KEYWORDS = [
    "contest", "reward", "giveaway", "مسابقة", "جائزة", "شروط"
]

BASE_CONTEST_URL = "https://example.com/contest/{id}" # قم بتعديل هذا الرابط حسب المنصة المستهدفة

app = Flask(__name__)

# ==========================================
# 2. Database Management
# ==========================================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """إنشاء الجدول وحفظ آخر رقم تم الوصول إليه إذا لم يكن موجوداً"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS contests (
                contest_id TEXT PRIMARY KEY,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.commit()
        
        # ضبط رقم البداية المرجعي إن لم يكن مسجلاً
        cur.execute("SELECT value FROM bot_state WHERE key = 'last_checked_id';")
        res = cur.fetchone()
        if not res:
            cur.execute("INSERT INTO bot_state (key, value) VALUES ('last_checked_id', %s);", (str(START_CONTEST_ID - 1),))
            conn.commit()
            
        cur.close()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database init error: {e}")

def get_last_checked_id():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM bot_state WHERE key = 'last_checked_id';")
        res = cur.fetchone()
        cur.close()
        conn.close()
        if res and res['value']:
            return int(res['value'])
    except Exception as e:
        print(f"Error fetching last_checked_id: {e}")
    return START_CONTEST_ID - 1

def update_last_checked_id(contest_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE bot_state SET value = %s WHERE key = 'last_checked_id';", (str(contest_id),))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error updating last_checked_id: {e}")

def is_contest_posted(contest_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT contest_id FROM contests WHERE contest_id = %s;", (str(contest_id),))
        res = cur.fetchone()
        cur.close()
        conn.close()
        return res is not None
    except Exception as e:
        print(f"Error checking contest status: {e}")
        return False

def save_posted_contest(contest_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO contests (contest_id, status) VALUES (%s, 'posted') ON CONFLICT DO NOTHING;", (str(contest_id),))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error saving contest: {e}")
# ==========================================
# 3. Contest Verification & Validation
# ==========================================
def verify_contest(contest_id):
    """
    يتفقد الرابط بنفسه، ويتحقق من الكلمات المفتاحية والاستجابة.
    إرجاع: (is_valid, is_future_not_ready)
    """
    url = BASE_CONTEST_URL.format(id=contest_id)
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        
        # إذا كان الرابط غير موجود كلياً بعد 404
        if response.status_code == 404:
            return False, True # غير متاح أو لم يبدأ بعد
            
        if response.status_code != 200:
            return False, False

        text_content = response.text.lower()

        # التحقق من علامات الانتهاء/الإغلاق
        for expired_word in EXPIRED_KEYWORDS:
            if expired_word in text_content:
                return False, False # مسابقة منتهية ومغلقة

        # التحقق من وجود الكلمات المفتاحية المطلوبة لتأكيد الصلاحية
        has_required = any(word in text_content for word in REQUIRED_KEYWORDS)
        
        if has_required:
            return True, False # مسابقة صالحة واستوفت الشروط
        else:
            return False, False
            
    except Exception as e:
        print(f"Error inspecting contest {contest_id}: {e}")
        return False, False
# ==========================================
# 4. Telegram Broadcaster
# ==========================================
def broadcast_contest(contest_id):
    """إرسال المسابقة المقبولة والاستوفاة للشروط إلى قناة التليجرام"""
    url = BASE_CONTEST_URL.format(id=contest_id)
    message = (
        f"🎉 **مسابقة جديدة متاحة الآن!**\n\n"
        f"🔗 **رابط المسابقة:** {url}\n"
        f"🆔 **معرف المسابقة:** `{contest_id}`\n\n"
        f"✨ استكشف التفاصيل وشارك الآن قبل الانتهاء!"
    )
    
    telegram_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    
    try:
        res = requests.post(telegram_api, json=payload, timeout=10)
        if res.status_code == 200:
            save_posted_contest(contest_id)
            print(f"Successfully broadcasted contest {contest_id}")
            return True
        else:
            print(f"Failed to send broadcast for {contest_id}: {res.text}")
            return False
    except Exception as e:
        print(f"Broadcast exception for {contest_id}: {e}")
        return False
# ==========================================
# 5. Continuous Loop Engine (Lookahead & Progression)
# ==========================================
def auto_checker_loop():
    """حلقة مستمرة تبحث انطلاقاً من الرقم المحدد ولا تتوقف وتلتزم بحد الـ 20 مسابقة مستقبلية"""
    time.sleep(5)  # انتظار التشغيل
    init_db()

    while True:
        try:
            current_base_id = get_last_checked_id() + 1
            if current_base_id < START_CONTEST_ID:
                current_base_id = START_CONTEST_ID

            future_unready_count = 0
            check_id = current_base_id

            while future_unready_count < LOOKAHEAD_LIMIT:
                if is_contest_posted(check_id):
                    check_id += 1
                    continue

                is_valid, is_future = verify_contest(check_id)

                if is_valid:
                    # تم العثور على مسابقة استوفت الشروط -> يتم نشرها فوراً
                    if broadcast_contest(check_id):
                        update_last_checked_id(check_id)
                        # الاستمرار من الرقم التالي مباشرة
                        check_id += 1
                        future_unready_count = 0
                        time.sleep(2)
                        continue

                if is_future:
                    future_unready_count += 1
                else:
                    # مسابقة منتهية أو مغلقة -> نحدث المعرف الأخير ونتجاوزها
                    if check_id == get_last_checked_id() + 1:
                        update_last_checked_id(check_id)

                check_id += 1
                time.sleep(1) # تفادي الحظر من السيرفرات

            # في حال الوصول إلى 20 مسابقة غير متاحة، ننتظر فترة قبل إعادة التتبع من نفس النقطة
            print(f"Reached lookahead limit of {LOOKAHEAD_LIMIT} at contest {check_id}. Waiting for new contests...")
            time.sleep(30)

        except Exception as e:
            print(f"Error in auto_checker_loop: {e}")
            time.sleep(10)

# تشغيل الخيط الخلفي للفحص المباشر
threading.Thread(target=auto_checker_loop, daemon=True).start()
# ==========================================
# 6. Flask Endpoints & Server Entry
# ==========================================
@app.route("/", methods=["GET"])
def health_check():
    """مسار الاستجابة لمنع السيرفر من النوم عبر الخوادم الخارجية"""
    return jsonify({
        "status": "online",
        "last_checked_id": get_last_checked_id()
    }), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    """استقبال تحديثات تليجرام العادية"""
    data = request.get_json(silent=True)
    if data and "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")
        
        if text == "/start":
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": "🤖 **بوت تتبع وبث المسابقات يعمل بنجاح!**"}
            )
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))