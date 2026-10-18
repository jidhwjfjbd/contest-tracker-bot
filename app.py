import os
import logging
from flask import Flask, request, jsonify, render_template_string
import requests
import pg8000.native

TOKEN = os.getenv("BOT_TOKEN", "8938116145:AAHkVV0geUtkdOh04pZgdzQpxL0qVchO6Io")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8557464787"))
BASE_URL = os.getenv("BASE_URL", "https://contest-tracker-bot.onrender.com")

# إعدادات الاتصال بـ Supabase باستخدام pg8000 (تتجنب مشاكل C-libraries)
DB_HOST = "aws-1-eu-central-1.pooler.supabase.com"
DB_PORT = 6543
DB_USER = "postgres"
DB_PASS = "Iae7UdzXxVaRSRVA"
DB_NAME = "postgres"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ----------------- Database Setup (Supabase / PostgreSQL) ----------------- #

def get_db():
    return pg8000.native.Connection(
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME
    )

def init_db():
    try:
        conn = get_db()
        conn.run('''CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        balance REAL DEFAULT 0.0,
                        referred_by BIGINT,
                        verified INT DEFAULT 0,
                        device_fingerprint TEXT
                    )''')
        conn.run('''CREATE TABLE IF NOT EXISTS channels (
                        channel_id TEXT PRIMARY KEY,
                        invite_link TEXT
                    )''')
        conn.run('''CREATE TABLE IF NOT EXISTS withdrawals (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        amount REAL,
                        binance_id TEXT,
                        status TEXT DEFAULT 'pending'
                    )''')
        conn.close()
        logging.info("Connected to Supabase DB successfully via pg8000!")
    except Exception as e:
        logging.error(f"Database Init Error: {e}")

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

def check_forced_subscriptions(user_id):
    try:
        conn = get_db()
        channels = conn.run("SELECT channel_id, invite_link FROM channels")
        conn.close()
    except Exception:
        channels = []
    
    unsubscribed = []
    for ch in channels:
        ch_id = ch[0]
        inv_link = ch[1]
        res = send_telegram_request("getChatMember", {"chat_id": ch_id, "user_id": user_id})
        if res and res.get("ok"):
            status = res["result"].get("status")
            if status not in ["member", "administrator", "creator"]:
                unsubscribed.append({"channel_id": ch_id, "invite_link": inv_link})
        else:
            unsubscribed.append({"channel_id": ch_id, "invite_link": inv_link})
    return unsubscribed

# ----------------- النصوص العربية ----------------- #

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
    existing = conn.run("SELECT user_id FROM users WHERE device_fingerprint = :fp AND user_id != :uid", fp=fp, uid=user_id)
    
    if existing:
        conn.close()
        return jsonify({"status": "error", "message": "⛔ تم كشف حساب مكرر! يُسمح بحساب واحد فقط لكل جهاز."}), 403

    conn.run('''
        INSERT INTO users (user_id, verified, device_fingerprint) 
        VALUES (:uid, 1, :fp) 
        ON CONFLICT(user_id) DO UPDATE SET verified=1, device_fingerprint=EXCLUDED.device_fingerprint
    ''', uid=user_id, fp=fp)
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
    u_rows = conn.run("SELECT verified FROM users WHERE user_id = :uid", uid=from_id)
    
    if not u_rows:
        ref_id = None
        if text.startswith("/start") and " " in text:
            parts = text.split(" ")
            if len(parts) > 1 and parts[1].isdigit():
                ref_id = int(parts[1])
        
        if ref_id and ref_id != from_id:
            conn.run("INSERT INTO users (user_id, referred_by, verified) VALUES (:uid, :ref, 0) ON CONFLICT DO NOTHING", uid=from_id, ref=ref_id)
        else:
            conn.run("INSERT INTO users (user_id, verified) VALUES (:uid, 0) ON CONFLICT DO NOTHING", uid=from_id)
        u_rows = conn.run("SELECT verified FROM users WHERE user_id = :uid", uid=from_id)

    is_verified = u_rows[0][0] if u_rows else 0
    conn.close()

    if from_id == ADMIN_ID and handle_admin_messages(chat_id, text, msg):
        return '', 200

    # 1. بوابة التحقق من الجهاز (ZORO System)
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

    # 3. معالجة خطوات طلب السحب (الحد الأدنى 0.05$)
    state = user_steps.get(from_id)
    if isinstance(state, str) and state == "waiting_withdraw_amount":
        try:
            amount = float(text)
            conn = get_db()
            bal_rows = conn.run("SELECT balance FROM users WHERE user_id = :uid", uid=from_id)
            bal = bal_rows[0][0] if bal_rows else 0.0
            conn.close()

            if amount < 0.05:
                send_message(chat_id, f"❌ **المبلغ المكتوب (${amount:.3f}) أقل من الحد الأدنى للسحب (0.05$)!**")
                user_steps[from_id] = None
            elif amount > bal:
                send_message(chat_id, f"❌ **المبلغ المطلوب (${amount:.3f}) أكثر من رصيدك الحالي (${bal:.3f})!**")
                user_steps[from_id] = None
            else:
                user_steps[from_id] = {"step": "waiting_binance_id", "amount": amount}
                send_message(chat_id, f"💳 **المبلغ المراد سحبه:** ${amount:.3f}\n\nالرجاء إرسال **Binance ID** الخاص بك الآن لاستلام السحب:")
        except ValueError:
            send_message(chat_id, "❌ **الرجاء كتابة رقم صحيح فقط!** (مثال: `0.05`)")
        return '', 200

    elif isinstance(state, dict) and state.get("step") == "waiting_binance_id":
        amount = state.get("amount", 0.0)
        binance_id = text
        user_steps[from_id] = None

        conn = get_db()
        bal_rows = conn.run("SELECT balance FROM users WHERE user_id = :uid", uid=from_id)
        bal = bal_rows[0][0] if bal_rows else 0.0
        if bal >= amount and amount >= 0.05:
            conn.run("UPDATE users SET balance = balance - :amt WHERE user_id = :uid", amt=amount, uid=from_id)
            conn.run("INSERT INTO withdrawals (user_id, amount, binance_id) VALUES (:uid, :amt, :bid)", uid=from_id, amt=amount, bid=binance_id)
            send_message(chat_id, f"✅ **تم تسجيل طلب السحب بنجاح!**\n💰 المبلغ: ${amount:.3f}\n🆔 Binance ID: `{binance_id}`")
            send_message(ADMIN_ID, f"📥 **طلب سحب جديد:**\n👤 المستخدم: `{from_id}`\n💰 المبلغ: ${amount:.3f}\n🆔 Binance ID: `{binance_id}`")
        else:
            send_message(chat_id, f"❌ **المبلغ المكتوب (${amount:.3f}) أقل من الحد الأدنى للسحب (0.05$)!**")
        conn.close()
        return '', 200

    # 4. الأزرار الرئيسية
    if text in ["/start", "الرئيسية"]:
        user_steps[from_id] = None
        send_message(chat_id, TEXT_WELCOME, get_main_keyboard())

    elif "مهام" in text:
        user_steps[from_id] = None
        send_message(chat_id, TASKS_TEXT)

    elif "إحالة" in text:
        user_steps[from_id] = None
        conn = get_db()
        cnt_rows = conn.run("SELECT COUNT(*) FROM users WHERE referred_by = :uid", uid=from_id)
        cnt = cnt_rows[0][0] if cnt_rows else 0
        conn.close()
        bot_res = send_telegram_request('getMe', {}) or {}
        bot_username = bot_res.get('result', {}).get('username', '')
        ref_link = f"https://t.me/{bot_username}?start={from_id}"
        send_message(chat_id, f"🔗 **رابط الإحالة الخاص بك:**\n`{ref_link}`\n\n🎁 **مكافأة كل إحالة ناجحة:** 0.025$\n👥 **عدد إحالاتك:** {cnt}")

    elif "سحب" in text:
        conn = get_db()
        bal_rows = conn.run("SELECT balance FROM users WHERE user_id = :uid", uid=from_id)
        bal = bal_rows[0][0] if bal_rows else 0.0
        conn.close()
        user_steps[from_id] = "waiting_withdraw_amount"
        send_message(chat_id, f"💰 **رصيدك الحالي:** ${bal:.3f}\n\nالحد الأدنى للسحب هو **0.05$**.\nالرجاء كتابة المبلغ الذي تريد سحبه الآن:")

    return '', 200

def handle_callback(cq):
    from_id = cq["from"]["id"]
    chat_id = cq["message"]["chat"]["id"]
    data = cq["data"]

    if data == "check_sub":
        unsub = check_forced_subscriptions(from_id)
        if not unsub:
            conn = get_db()
            ref_rows = conn.run("SELECT referred_by FROM users WHERE user_id = :uid", uid=from_id)
            if ref_rows and ref_rows[0][0]:
                ref_by = ref_rows[0][0]
                # إعطاء مكافأة 0.025$ للشخص الذي قام بالدعوة
                conn.run("UPDATE users SET balance = balance + 0.025 WHERE user_id = :ruid", ruid=ref_by)
                send_message(ref_by, "🎉 **لقد حصلت على 0.025$ لإحالة مستخدم جديد أكمل إثبات الانضمام!**")
                conn.run("UPDATE users SET referred_by = NULL WHERE user_id = :uid", uid=from_id)
            conn.close()
            send_message(chat_id, TEXT_WELCOME, get_main_keyboard())
        else:
            send_message(chat_id, "❌ لم تقم بالاشتراك في جميع القنوات بعد!")

def handle_admin_messages(chat_id, text, msg):
    if text in ["/admin", "لوحة الأدمن"]:
        admin_kb = {
            "inline_keyboard": [
                [{"text": "➕ إضافة قناة اشتراك", "callback_data": "adm_add_ch"}, {"text": "➖ حذف قناة اشتراك", "callback_data": "adm_del_ch"}]
            ]
        }
        send_message(chat_id, "🛠️ **لوحة تحكم الأدمن:**", admin_kb)
        return True
    return False

@app.route('/')
def index():
    return "🤖 البوت يعمل بكفاءة مع Supabase السحابية وpg8000!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))