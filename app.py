import os
import sqlite3
import logging
import json
from flask import Flask, request, jsonify, render_template_string
import requests

TOKEN = os.getenv("BOT_TOKEN", "8938116145:AAHkVV0geUtkdOh04pZgdzQpxL0qVchO6Io")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8557464787"))
BASE_URL = os.getenv("BASE_URL", "https://contest-tracker-bot.onrender.com")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

DB_FILE = "/var/data/bot_database.db" if os.path.exists("/var/data") else "bot_database.db"

# ----------------- Database Setup ----------------- #

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance REAL DEFAULT 0.0,
                    referred_by INTEGER,
                    verified INTEGER DEFAULT 0,
                    device_fingerprint TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS channels (
                    channel_id TEXT PRIMARY KEY,
                    invite_link TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    binance_id TEXT,
                    status TEXT DEFAULT 'pending'
                )''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

init_db()
user_steps = {}

# ----------------- Helper Functions ----------------- #

def send_telegram_request(method, payload):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        logging.error(f"Telegram Request Error ({method}): {e}")
        return None

def send_message(chat_id, text, reply_markup=None):
    return send_telegram_request("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    })

def send_photo(chat_id, photo, caption="", reply_markup=None):
    return send_telegram_request("sendPhoto", {
        "chat_id": chat_id,
        "photo": photo,
        "caption": caption,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    })

def check_forced_subscriptions(user_id):
    conn = get_db()
    channels = conn.execute("SELECT channel_id, invite_link FROM channels").fetchall()
    conn.close()
    unsubscribed = []
    for ch in channels:
        res = send_telegram_request("getChatMember", {"chat_id": ch["channel_id"], "user_id": user_id})
        if res and res.get("ok"):
            status = res["result"].get("status")
            if status not in ["member", "administrator", "creator"]:
                unsubscribed.append(ch)
        else:
            unsubscribed.append(ch)
    return unsubscribed

# ----------------- Texts & Translations (Arabic Only) ----------------- #

TASKS_TEXT = """🎯 **مهمة الربح المجاني المميزة**

⚠️ **للحصول على مكافأة المهمة، يجب إكمال الشروط التالية بدقة:**

1️⃣ **الشرط الأول:**
الانضمام للقناة عبر هذا الرابط الخاص:
👉 https://t.me/+4jDGJ8ZM2XI2NzQ0
ثم أخذ لقطة شاشة (Screenshot) تُثبت الانضمام، وإرسالها إلى الحساب: @tawsiatKE

2️⃣ **الشرط الثاني:**
أخذ لقطة شاشة (Screenshot) لملفك الشخصي (Profile) يظهر فيه **ID حسابك** وأنه **موثق**، وإرسالها أيضاً للحساب: @tawsiatKE
*(هذا الإجراء لمنع الحسابات الوهمية أو كشف تعديلات الفوتوشوب)*.

3️⃣ **الشرط الثالث (بينك وبين الله وهو أهم شرط):**
لا تخرج من القناة بعد حصولك على الجائزة؛ لأنك بذلك تكون قد انتهكت الشروط كلها، وسيكون ربحك **غير مباح شرعاً** حتى لو كان 0.05$.

📩 **لإرسال الإثباتات والاستفسار:** @tawsiatKE"""

TEXT_WELCOME = "👋 **أهلاً بك في بوت الربح المجاني!**\n\nقم بزيادة رصيدك من خلال الإحالات وإكمال المهام اليومية."
TEXT_VERIFY_REQ = "⚠️ **عذراً، يجب إكمال عملية التحقق من الجهاز لمنع الحسابات المكررة أولاً:**"
TEXT_MUST_SUB = "⚠️ **يجب عليك الاشتراك في القنوات التالية لاستخدام البوت:**"
BTN_CHECK_SUB = "🔄 تحقق من الاشتراك"

BTN_TASKS = "🎯 مهام ربح مجانية"
BTN_REF = "🔗 رابط الإحالة"
BTN_WITHDRAW = "💸 طلب السحب"

def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": BTN_TASKS}, {"text": BTN_REF}],
            [{"text": BTN_WITHDRAW}]
        ],
        "resize_keyboard": True
    }

# ----------------- Web Application for Verification (ZORO Fingerprint) ----------------- #

ZORO_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZORO Security Verification</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: Arial, sans-serif; background: #121212; color: #fff; text-align: center; padding: 40px 20px; }
        .card { background: #1e1e1e; border-radius: 12px; padding: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .btn { background: #0088cc; color: white; border: none; padding: 14px 28px; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 20px; }
        .loader { display: none; margin: 20px auto; border: 4px solid #333; border-top: 4px solid #0088cc; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="card">
        <h2>🛡️ نظام التحقق الأمني ZORO</h2>
        <p>اضغط أدناه للتحقق من بصمة جهازك وتأمين حسابك.</p>
        <div class="loader" id="loader"></div>
        <button class="btn" id="verifyBtn" onclick="verifyDevice()">التحقق من الجهاز الآن</button>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        function getFingerprint() {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            ctx.textBaseline = "top";
            ctx.font = "14px 'Arial'";
            ctx.fillStyle = "#f60";
            ctx.fillRect(125,1,62,20);
            ctx.fillStyle = "#069";
            ctx.fillText("ZORO_FP", 2, 15);
            return canvas.toDataURL().slice(-50) + screen.width + "x" + screen.height + navigator.hardwareConcurrency;
        }

        function verifyDevice() {
            document.getElementById('verifyBtn').style.display = 'none';
            document.getElementById('loader').style.display = 'block';

            const user = tg.initDataUnsafe.user;
            if (!user) {
                alert("الرجاء فتح هذه الصفحة داخل تطبيق تليجرام!");
                return;
            }

            fetch('/api/verify-device', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: user.id, fingerprint: getFingerprint() })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    tg.close();
                } else {
                    alert(data.message || "فشل التحقق!");
                    document.getElementById('verifyBtn').style.display = 'inline-block';
                    document.getElementById('loader').style.display = 'none';
                }
            })
            .catch(err => {
                alert("خطأ في الاتصال بالشبكة!");
                document.getElementById('verifyBtn').style.display = 'inline-block';
                document.getElementById('loader').style.display = 'none';
            });
        }
    </script>
</body>
</html>
"""
@app.route('/verify')
def verify_page():
    return render_template_string(ZORO_HTML)

@app.route('/api/verify-device', methods=['POST'])
def api_verify_device():
    data = request.get_json() or {}
    user_id = data.get("user_id")
    fp = data.get("fingerprint")

    if not user_id or not fp:
        return jsonify({"status": "error", "message": "معلمات غير صالحة"}), 400

    conn = get_db()
    existing = conn.execute("SELECT user_id FROM users WHERE device_fingerprint=? AND user_id!=?", (fp, user_id)).fetchone()
    
    if existing:
        conn.close()
        return jsonify({"status": "error", "message": "⛔ تم كشف حساب مكرر! يُسمح بحساب واحد فقط لكل جهاز."}), 403

    conn.execute('''
        INSERT INTO users (user_id, verified, device_fingerprint) 
        VALUES (?, 1, ?) 
        ON CONFLICT(user_id) DO UPDATE SET verified=1, device_fingerprint=excluded.device_fingerprint
    ''', (user_id, fp))
    conn.commit()
    conn.close()

    send_message(user_id, "✅ **تم التحقق من جهازك بنجاح وحفظ بصمتك! يمكنك الآن استخدام البوت بكامل ميزاته.**", get_main_keyboard())
    return jsonify({"status": "success"})

# ----------------- Webhook Handling ----------------- #

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') != 'application/json':
        return 'OK', 200

    data = request.get_json()
    msg = data.get("message")
    cq = data.get("callback_query")

    if cq:
        handle_callback(cq)
        return '', 200

    if not msg:
        return '', 200

    chat_id = msg["chat"]["id"]
    from_id = msg["from"]["id"]
    text = msg.get("text", "").strip()

    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (from_id,)).fetchone()
    
    # معالجة رابط الإحالة
    if not u:
        ref_id = None
        if text.startswith("/start") and " " in text:
            parts = text.split(" ")
            if len(parts) > 1 and parts[1].isdigit():
                ref_id = int(parts[1])
        
        if ref_id and ref_id != from_id:
            conn.execute("INSERT OR IGNORE INTO users (user_id, referred_by, verified) VALUES (?, ?, 0)", (from_id, ref_id))
        else:
            conn.execute("INSERT OR IGNORE INTO users (user_id, verified) VALUES (?, 0)", (from_id,))
        conn.commit()
        u = conn.execute("SELECT * FROM users WHERE user_id=?", (from_id,)).fetchone()

    is_verified = u["verified"] if u else 0
    conn.close()

    # لوحة تحكم الأدمن
    if from_id == ADMIN_ID and handle_admin_messages(chat_id, text, msg):
        return '', 200

    # 1. بوابَة التحقق من الجهاز (ZORO System)
    if not is_verified:
        verify_markup = {
            "inline_keyboard": [[
                {"text": "🛡️ التحقق من الجهاز (Verify Device)", "web_app": {"url": f"{BASE_URL}/verify"}}
            ]]
        }
        send_message(chat_id, TEXT_VERIFY_REQ, verify_markup)
        return '', 200

    # 2. فحص الاشتراك الإجباري
    unsub = check_forced_subscriptions(from_id)
    if unsub:
        buttons = []
        for index, ch in enumerate(unsub, 1):
            buttons.append([{"text": f"📢 القناة {index}", "url": ch["invite_link"]}])
        buttons.append([{"text": BTN_CHECK_SUB, "callback_data": "check_sub"}])
        send_message(chat_id, TEXT_MUST_SUB, {"inline_keyboard": buttons})
        return '', 200

    # 3. معالجة خطوات طلب السحب
    state = user_steps.get(from_id)
    
    if isinstance(state, str) and state == "waiting_withdraw_amount":
        try:
            amount = float(text)
            conn = get_db()
            bal = conn.execute("SELECT balance FROM users WHERE user_id=?", (from_id,)).fetchone()["balance"]
            conn.close()

            if amount < 0.10:
                send_message(chat_id, f"❌ **المبلغ المكتوب (${amount:.2f}) أقل من الحد الأدنى للسحب (0.10$)!**\nقم بجمع المزيد من الإحالات والعودة مجدداً.")
                user_steps[from_id] = None
            elif amount > bal:
                send_message(chat_id, f"❌ **المبلغ المطلوب (${amount:.2f}) أكثر من رصيدك الحالي (${bal:.2f})!**")
                user_steps[from_id] = None
            else:
                user_steps[from_id] = {"step": "waiting_binance_id", "amount": amount}
                send_message(chat_id, f"💳 **المبلغ المراد سحبه:** ${amount:.2f}\n\nالرجاء إرسال **Binance ID** الخاص بك الآن لاستلام السحب:")
        except ValueError:
            send_message(chat_id, "❌ **الرجاء كتابة رقم صحيح فقط!** (مثال: `0.15`)")
        return '', 200

    elif isinstance(state, dict) and state.get("step") == "waiting_binance_id":
        amount = state.get("amount", 0.0)
        binance_id = text
        user_steps[from_id] = None

        conn = get_db()
        bal = conn.execute("SELECT balance FROM users WHERE user_id=?", (from_id,)).fetchone()["balance"]
        if bal >= amount and amount >= 0.10:
            conn.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, from_id))
            conn.execute("INSERT INTO withdrawals (user_id, amount, binance_id) VALUES (?, ?, ?)", (from_id, amount, binance_id))
            conn.commit()
            send_message(chat_id, f"✅ **تم تسجيل طلب السحب بنجاح!**\n💰 المبلغ: ${amount:.2f}\n🆔 Binance ID: `{binance_id}`\nسيتم مراجعته وإرسال المبلغ قريباً.")
            send_message(ADMIN_ID, f"📥 **طلب سحب جديد:**\n👤 المستخدم: `{from_id}`\n💰 المبلغ: ${amount:.2f}\n🆔 Binance ID: `{binance_id}`")
        else:
            send_message(chat_id, f"❌ **المبلغ المكتوب (${amount:.2f}) أقل من الحد الأدنى للسحب (0.10$)!**")
        conn.close()
        return '', 200

    # 4. معالجة الأزرار الرئيسية
    if text in ["/start", "الرئيسية"]:
        user_steps[from_id] = None
        send_message(chat_id, TEXT_WELCOME, get_main_keyboard())

    elif "مهام" in text:
        user_steps[from_id] = None
        send_message(chat_id, TASKS_TEXT)

    elif "إحالة" in text:
        user_steps[from_id] = None
        conn = get_db()
        cnt = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (from_id,)).fetchone()[0]
        conn.close()
        bot_res = send_telegram_request('getMe', {}) or {}
        bot_username = bot_res.get('result', {}).get('username', '')
        ref_link = f"https://t.me/{bot_username}?start={from_id}"
        send_message(chat_id, f"🔗 **رابط الإحالة الخاص بك:**\n`{ref_link}`\n\n🎁 **مكافأة كل إحالة:** 0.01$\n👥 **عدد إحالاتك:** {cnt}")

    elif "سحب" in text:
        conn = get_db()
        bal = conn.execute("SELECT balance FROM users WHERE user_id=?", (from_id,)).fetchone()["balance"]
        conn.close()
        user_steps[from_id] = "waiting_withdraw_amount"
        send_message(chat_id, f"💰 **رصيدك الحالي:** ${bal:.2f}\n\nالحد الأدنى للسحب هو **0.10$**.\nالرجاء كتابة المبلغ الذي تريد سحبه الآن:")

    return '', 200

# ----------------- Callbacks & Admin Control ----------------- #

def handle_callback(cq):
    from_id = cq["from"]["id"]
    chat_id = cq["message"]["chat"]["id"]
    data = cq["data"]

    if data == "check_sub":
        unsub = check_forced_subscriptions(from_id)
        if not unsub:
            conn = get_db()
            u = conn.execute("SELECT referred_by FROM users WHERE user_id=?", (from_id,)).fetchone()
            if u and u["referred_by"]:
                ref_user = conn.execute("SELECT user_id FROM users WHERE user_id=?", (u["referred_by"],)).fetchone()
                if ref_user:
                    conn.execute("UPDATE users SET balance = balance + 0.01 WHERE user_id=?", (u["referred_by"],))
                    send_message(u["referred_by"], "🎉 **لقد حصلت على 0.01$ لإحالة مستخدم جديد!**")
                    conn.execute("UPDATE users SET referred_by=NULL WHERE user_id=?", (from_id,))
                    conn.commit()
            conn.close()
            send_message(chat_id, TEXT_WELCOME, get_main_keyboard())
        else:
            send_message(chat_id, "❌ لم تقم بالاشتراك في جميع القنوات بعد!")

def handle_admin_messages(chat_id, text, msg):
    if text in ["/admin", "لوحة الأدمن"]:
        admin_kb = {
            "inline_keyboard": [
                [{"text": "➕ إضافة قناة اشتراك", "callback_data": "adm_add_ch"}, {"text": "➖ حذف قناة اشتراك", "callback_data": "adm_del_ch"}],
                [{"text": "📢 إذاعة جماعية (متطورة)", "callback_data": "adm_broadcast"}]
            ]
        }
        send_message(chat_id, "🛠️ **لوحة تحكم الأدمن:**", admin_kb)
        return True

    state = user_steps.get(chat_id)
    if state == "waiting_add_ch":
        user_steps[chat_id] = None
        parts = text.split()
        if len(parts) >= 2:
            ch_id, ch_link = parts[0], parts[1]
            conn = get_db()
            conn.execute("INSERT OR REPLACE INTO channels (channel_id, invite_link) VALUES (?, ?)", (ch_id, ch_link))
            conn.commit()
            conn.close()
            send_message(chat_id, f"✅ تم إضافة القناة `{ch_id}` بنجاح!")
        else:
            send_message(chat_id, "❌ صيغة غير صحيحة! قم بإرسال: `@ChannelUsername https://t.me/...`")
        return True

    elif state == "waiting_del_ch":
        user_steps[chat_id] = None
        conn = get_db()
        conn.execute("DELETE FROM channels WHERE channel_id=?", (text.strip(),))
        conn.commit()
        conn.close()
        send_message(chat_id, f"🗑️ تم حذف القناة `{text}` إن وجدت!")
        return True

    elif state == "waiting_broadcast":
        user_steps[chat_id] = None
        conn = get_db()
        all_u = conn.execute("SELECT user_id FROM users").fetchall()
        conn.close()

        count = 0
        photo = msg.get("photo", [{}])[-1].get("file_id") if "photo" in msg else None
        caption = msg.get("caption") or text

        for row in all_u:
            u_id = row["user_id"]
            try:
                if photo:
                    send_photo(u_id, photo, caption)
                else:
                    send_message(u_id, caption)
                count += 1
            except Exception:
                pass
        send_message(chat_id, f"✅ تم إرسال الإذاعة لـ {count} مستخدم بنجاح!")
        return True

    return False

@app.route('/')
def index():
    return "🤖 البوت يعمل بكفاءة باللغة العربية ونظام التحقق ZORO!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))