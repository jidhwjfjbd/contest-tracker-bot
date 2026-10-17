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
                    language TEXT DEFAULT 'ar',
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

# لتتبع خطوات المستخدم (مثل إدخال مبلغ السحب ثم إدخال Binance ID)
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

def get_user_lang(user_id):
    conn = get_db()
    u = conn.execute("SELECT language FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return u["language"] if u else "ar"

# ----------------- Texts & Translations ----------------- #

TASKS_TEXT_AR = """🎯 **مهمة الربح المجاني المميزة**

⚠️ **ل للحصول على مكافأة المهمة، يجب إكمال الشروط التالية بدقة:**

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

TASKS_TEXT_EN = """🎯 **Free Reward Task**

⚠️ **To claim your task reward, you must complete the following steps carefully:**

1️⃣ **First Condition:**
Join the channel via this private link:
👉 https://t.me/+4jDGJ8ZM2XI2NzQ0
Take a screenshot proving you joined, and send it to: @tawsiatKE

2️⃣ **Second Condition:**
Take a screenshot of your Profile showing your **Account ID** and that it is **Verified**, then send it to: @tawsiatKE
*(This is strictly required to detect fake or photo-edited accounts)*.

3️⃣ **Third & Most Important Condition (Between you and God):**
Do not leave the channel after receiving your reward. Doing so violates all terms, and your earnings will **not be permissible (حرام/Halal concern)** even if it is just $0.05.

📩 **Send proof to:** @tawsiatKE"""

TEXTS = {
    "ar": {
        "welcome": "👋 **أهلاً بك في بوت الربح المجاني!**\n\nقم بزيادة رصيدك من خلال الإحالات وإكمال المهام اليومية.",
        "lang_select": "🌐 **اختر اللغة المناسبة لك / Choose your language:**",
        "verify_req": "⚠️ **عذراً، يجب إكمال عملية التحقق من الجهاز لمنع الحسابات المكررة أولاً:**",
        "must_sub": "⚠️ **يجب عليك الاشتراك في القنوات التالية لاستخدام البوت:**",
        "check_sub_btn": "🔄 تحقق من الاشتراك",
        "btn_tasks": "🎯 مهام ربح مجانية",
        "btn_ref": "🔗 رابط الإحالة",
        "btn_withdraw": "💸 طلب السحب",
        "btn_lang": "🌐 تغيير اللغة",
        "ref_text": "🔗 **رابط الإحالة الخاص بك:**\n`{link}`\n\n🎁 **مكافأة كل إحالة:** 0.01$\n👥 **عدد إحالاتك:** {count}",
        "tasks_text": TASKS_TEXT_AR,
        "withdraw_enter_amount": "💰 **رصيدك الحالي:** ${bal:.2f}\n\nالحد الأدنى للسحب هو **0.10$**.\nالرجاء كتابة المبلغ الذي تريد سحبه الآن:",
        "withdraw_min_err": "❌ **المبلغ المكتوب (${amt:.2f}) أقل من الحد الأدنى للسحب (0.10$)!**\nقم بجمع المزيد من الإحالات والعودة مجدداً.",
        "withdraw_bal_err": "❌ **المبلغ المطلوب (${amt:.2f}) أكثر من رصيدك الحالي (${bal:.2f})!**",
        "withdraw_prompt_binance": "💳 **المبلغ المراد سحبه:** ${amt:.2f}\n\nالرجاء إرسال **Binance ID** الخاص بك الآن لاستلام السحب:",
        "withdraw_success": "✅ **تم تسجيل طلب السحب بنجاح!**\n💰 المبلغ: ${amt:.2f}\n🆔 Binance ID: `{bid}`\nسيتم مراجعته وإرسال المبلغ قريباً.",
        "lang_changed": "✅ تم تغيير اللغة بنجاح إلى العربية!"
    },
    "en": {
        "welcome": "👋 **Welcome to Earn Free Bot!**\n\nEarn money by inviting friends and completing daily tasks.",
        "lang_select": "🌐 **Choose your language / اختر اللغة المناسبة لك:**",
        "verify_req": "⚠️ **Device verification is required to prevent multiple accounts:**",
        "must_sub": "⚠️ **You must join the following channels to use the bot:**",
        "check_sub_btn": "🔄 Check Subscription",
        "btn_tasks": "🎯 Free Tasks",
        "btn_ref": "🔗 Referral Link",
        "btn_withdraw": "💸 Withdraw",
        "btn_lang": "🌐 Change Language",
        "ref_text": "🔗 **Your Referral Link:**\n`{link}`\n\n🎁 **Reward per referral:** $0.01\n👥 **Total Referrals:** {count}",
        "tasks_text": TASKS_TEXT_EN,
        "withdraw_enter_amount": "💰 **Your Balance:** ${bal:.2f}\n\nMinimum withdrawal is **$0.10**.\nPlease enter the amount you wish to withdraw:",
        "withdraw_min_err": "❌ **The entered amount (${amt:.2f}) is below the minimum withdrawal ($0.10)!**",
        "withdraw_bal_err": "❌ **The requested amount (${amt:.2f}) exceeds your balance (${bal:.2f})!**",
        "withdraw_prompt_binance": "💳 **Withdrawal Amount:** ${amt:.2f}\n\nPlease send your **Binance ID** now:",
        "withdraw_success": "✅ **Withdrawal request submitted!**\n💰 Amount: ${amt:.2f}\n🆔 Binance ID: `{bid}`\nProcessing soon.",
        "lang_changed": "✅ Language changed successfully to English!"
    }
}

def get_main_keyboard(lang):
    t = TEXTS[lang]
    return {
        "keyboard": [
            [{"text": t["btn_tasks"]}, {"text": t["btn_ref"]}],
            [{"text": t["btn_withdraw"]}, {"text": t["btn_lang"]}]
        ],
        "resize_keyboard": True
    }

# ----------------- Web Application for Verification (ZORO Fingerprint) ----------------- #

ZORO_HTML = """
<!DOCTYPE html>
<html lang="en">
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
        <h2>🛡️ ZORO Security Verification</h2>
        <p>Click below to verify your device fingerprint and secure your account.</p>
        <div class="loader" id="loader"></div>
        <button class="btn" id="verifyBtn" onclick="verifyDevice()">Verify Device Now</button>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        function getFingerprint() {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            ctx.textBaseline = "top";
            ctx.font = "14px 'Arial'";
            ctx.textBaseline = "alphabetic";
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
                alert("Please open this page inside Telegram!");
                return;
            }

            const payload = {
                user_id: user.id,
                fingerprint: getFingerprint()
            };

            fetch('/api/verify-device', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    tg.close();
                } else {
                    alert(data.message || "Verification Failed!");
                    document.getElementById('verifyBtn').style.display = 'inline-block';
                    document.getElementById('loader').style.display = 'none';
                }
            })
            .catch(err => {
                alert("Network Error!");
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
        return jsonify({"status": "error", "message": "Invalid Parameters"}), 400

    conn = get_db()
    existing = conn.execute("SELECT user_id FROM users WHERE device_fingerprint=? AND user_id!=?", (fp, user_id)).fetchone()
    
    if existing:
        conn.close()
        return jsonify({"status": "error", "message": "⛔ Multi-account detected! Devices can only hold one account."}), 403

    conn.execute("UPDATE users SET verified=1, device_fingerprint=? WHERE user_id=?", (fp, user_id))
    conn.commit()
    conn.close()

    lang = get_user_lang(user_id)
    send_message(user_id, "✅ **تم التحقق من جهازك بنجاح وحفظ بصمتك! يمكنك الآن استخدام البوت بكامل ميزاته.**", get_main_keyboard(lang))
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
    
    # جلب أو تسجيل المستخدم
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (from_id,)).fetchone()
    
    # تسجيل الإحالة إن وجدت
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

    # القراءة الفورية والمباشرة لحالة التحقق واللغة
    is_verified = u["verified"] if u else 0
    lang = u["language"] if u else "ar"
    conn.close()

    t = TEXTS.get(lang, TEXTS["ar"])

    # الأدمن يتجاوز التحقق دائماً
    if from_id == ADMIN_ID and handle_admin_messages(chat_id, text, msg):
        return '', 200

    # 1. Verification Gate (التحقق الفوري)
    if not is_verified:
        verify_markup = {
            "inline_keyboard": [[
                {"text": "🛡️ التحقق من الجهاز (Verify Device)", "web_app": {"url": f"{BASE_URL}/verify"}}
            ]]
        }
        send_message(chat_id, t["verify_req"], verify_markup)
        return '', 200

    # 2. Forced Subscription Check
    unsub = check_forced_subscriptions(from_id)
    if unsub:
        buttons = []
        for index, ch in enumerate(unsub, 1):
            buttons.append([{"text": f"📢 القناة {index}", "url": ch["invite_link"]}])
        buttons.append([{"text": t["check_sub_btn"], "callback_data": "check_sub"}])
        send_message(chat_id, t["must_sub"], {"inline_keyboard": buttons})
        return '', 200

    # 3. Handling Pending Steps (منطق السحب خطوة بخطوة)
    state = user_steps.get(from_id)
    
    if isinstance(state, str) and state == "waiting_withdraw_amount":
        try:
            amount = float(text)
            conn = get_db()
            bal = conn.execute("SELECT balance FROM users WHERE user_id=?", (from_id,)).fetchone()["balance"]
            conn.close()

            if amount < 0.10:
                send_message(chat_id, t["withdraw_min_err"].format(amt=amount))
                user_steps[from_id] = None
            elif amount > bal:
                send_message(chat_id, t["withdraw_bal_err"].format(amt=amount, bal=bal))
                user_steps[from_id] = None
            else:
                user_steps[from_id] = {"step": "waiting_binance_id", "amount": amount}
                send_message(chat_id, t["withdraw_prompt_binance"].format(amt=amount))
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
            send_message(chat_id, t["withdraw_success"].format(amt=amount, bid=binance_id))
            send_message(ADMIN_ID, f"📥 **طلب سحب جديد:**\n👤 المستخدم: `{from_id}`\n💰 المبلغ: ${amount:.2f}\n🆔 Binance ID: `{binance_id}`")
        else:
            send_message(chat_id, t["withdraw_min_err"].format(amt=amount))
        conn.close()
        return '', 200

    # 4. Main Menu Buttons Processing (فحص واسع النطاق يضم كافة الحالات)
    if text in ["/start", "الرئيسية", "Main"]:
        user_steps[from_id] = None
        send_message(chat_id, t["welcome"], get_main_keyboard(lang))

    elif any(k in text for k in ["مهام", "Tasks"]):
        user_steps[from_id] = None
        send_message(chat_id, t["tasks_text"])

    elif any(k in text for k in ["إحالة", "Referral"]):
        user_steps[from_id] = None
        conn = get_db()
        cnt = conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (from_id,)).fetchone()[0]
        conn.close()
        bot_res = send_telegram_request('getMe', {}) or {}
        bot_username = bot_res.get('result', {}).get('username', '')
        ref_link = f"https://t.me/{bot_username}?start={from_id}"
        send_message(chat_id, t["ref_text"].format(link=ref_link, count=cnt))

    elif any(k in text for k in ["سحب", "Withdraw"]):
        conn = get_db()
        bal = conn.execute("SELECT balance FROM users WHERE user_id=?", (from_id,)).fetchone()["balance"]
        conn.close()
        user_steps[from_id] = "waiting_withdraw_amount"
        send_message(chat_id, t["withdraw_enter_amount"].format(bal=bal))

    elif any(k in text for k in ["لغة", "Language"]):
        user_steps[from_id] = None
        lang_kb = {
            "inline_keyboard": [
                [{"text": "🇸🇦 العربية", "callback_data": "set_lang_ar"}, {"text": "🇺🇸 English", "callback_data": "set_lang_en"}]
            ]
        }
        send_message(chat_id, t["lang_select"], lang_kb)

    return '', 200

# ----------------- Callbacks & Admin Control ----------------- #

def handle_callback(cq):
    from_id = cq["from"]["id"]
    chat_id = cq["message"]["chat"]["id"]
    data = cq["data"]

    if data.startswith("set_lang_"):
        new_lang = data.split("_")[2]
        conn = get_db()
        conn.execute("UPDATE users SET language=? WHERE user_id=?", (new_lang, from_id))
        conn.commit()
        conn.close()
        send_message(chat_id, TEXTS[new_lang]["lang_changed"], get_main_keyboard(new_lang))

    elif data == "check_sub":
        unsub = check_forced_subscriptions(from_id)
        lang = get_user_lang(from_id)
        if not unsub:
            conn = get_db()
            u = conn.execute("SELECT referred_by, verified FROM users WHERE user_id=?", (from_id,)).fetchone()
            if u and u["referred_by"]:
                ref_user = conn.execute("SELECT user_id FROM users WHERE user_id=?", (u["referred_by"],)).fetchone()
                if ref_user:
                    conn.execute("UPDATE users SET balance = balance + 0.01 WHERE user_id=?", (u["referred_by"],))
                    send_message(u["referred_by"], "🎉 **لقد حصلت على 0.01$ لإحالة مستخدم جديد!**")
                    conn.execute("UPDATE users SET referred_by=NULL WHERE user_id=?", (from_id,))
                    conn.commit()
            conn.close()
            send_message(chat_id, TEXTS[lang]["welcome"], get_main_keyboard(lang))
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
    return "🤖 البوت يعمل بكفاءة وحساب التحقق يحدث لحظياً!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))