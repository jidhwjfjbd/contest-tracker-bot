import os
import logging
from flask import Flask, request
import requests

TOKEN = os.getenv("BOT_TOKEN", "8938116145:AAHkVV0geUtkdOh04pZgdzQpxL0qVchO6Io")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@neoearnboot")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

admin_current_id = 894
user_steps = {}

# قائمة لتخزين جميع المستخدمين الذين تفاعلوا مع البوت لترسل لهم التنبيهات الجماعية
bot_users = set()

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
    global admin_current_id
    if request.headers.get('content-type') == 'application/json':
        data = request.get_json()
        
        # حفظ أي مستخدم يتفاعل مع البوت في قائمة المستلمين
        if "message" in data:
            bot_users.add(data["message"]["chat"]["id"])
        elif "callback_query" in data:
            bot_users.add(data["callback_query"]["message"]["chat"]["id"])
            
        # معالجة الأزرار التفاعلية
        if "callback_query" in data:
            cq = data["callback_query"]
            chat_id = cq["message"]["chat"]["id"]
            message_id = cq["message"]["message_id"]
            data_action = cq["data"]
            
            if data_action == 'next_id':
                admin_current_id += 1
            elif data_action == 'prev_id':
                admin_current_id -= 1
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
                send_telegram_message(chat_id, "📢 أرسل الرسالة التي تريد بثها لجميع المستخدمين:")
                return '', 200
            elif data_action == 'forced_sub_menu':
                user_steps[chat_id] = {"step": "waiting_for_channel"}
                send_telegram_message(chat_id, "➕ أرسل يوزر القناة للاشتراك الإجباري (مثلاً @MyChannel):")
                return '', 200

            # تحديث لوحة التحكم الرئيسية
            link = f"https://t.me/Randomalbot?startapp=contest_{admin_current_id}__r8557464787"
            text = (
                f"🤖 **مرحباً بك في لوحة تحكم البوت**\n\n"
                f"📌 **رقم المسابقة الحالي:** `{admin_current_id}`\n"
                f"🔗 **الرابط الحالي لفحصه:**\n`{link}`"
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "⬅️ السابق", "callback_data": "prev_id"}, {"text": "التالي ➡️", "callback_data": "next_id"}],
                    [{"text": "✏️ تعديل الرقم يدوياً", "callback_data": "edit_id"}],
                    [{"text": "✅ الرابط سليم (ابدأ النشر)", "callback_data": "approve_contest"}],
                    [{"text": "📢 رسالة جماعية", "callback_data": "broadcast_menu"}, {"text": "➕ إشتراك إجباري", "callback_data": "forced_sub_menu"}]
                ]
            }
            requests.post(f"https://api.telegram.org/bot{TOKEN}/editMessageText", json={
                "chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown", "reply_markup": markup
            })

        # معالجة الرسائل النصية والفيديوهات
        elif "message" in data:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")
            
            if text == "/start" or text == "/admin":
                user_steps[chat_id] = {}
                link = f"https://t.me/Randomalbot?startapp=contest_{admin_current_id}__r8557464787"
                text_msg = (
                    f"🤖 **مرحباً بك في لوحة تحكم البوت**\n\n"
                    f"📌 **رقم المسابقة الحالي:** `{admin_current_id}`\n"
                    f"🔗 **الرابط الحالي لفحصه:**\n`{link}`\n\n"
                    f"👇 اختر الإجراء المناسب:"
                )
                markup = {
                    "inline_keyboard": [
                        [{"text": "⬅️ السابق", "callback_data": "prev_id"}, {"text": "التالي ➡️", "callback_data": "next_id"}],
                        [{"text": "✏️ تعديل الرقم يدوياً", "callback_data": "edit_id"}],
                        [{"text": "📢 رسالة جماعية", "callback_data": "broadcast_menu"}, {"text": "➕ إشتراك إجباري", "callback_data": "forced_sub_menu"}]
                    ]
                }
                send_telegram_message(chat_id, text_msg, markup)
                
            elif chat_id in user_steps:
                current_state = user_steps[chat_id].get("step")
                
                if current_state == "waiting_for_custom_id":
                    try:
                        admin_current_id = int(text.strip())
                        user_steps[chat_id] = {}
                        link = f"https://t.me/Randomalbot?startapp=contest_{admin_current_id}__r8557464787"
                        send_telegram_message(chat_id, f"✅ تم تحديث الرقم إلى: `{admin_current_id}`\n🔗 الرابط:\n`{link}`")
                    except ValueError:
                        send_telegram_message(chat_id, "❌ أرسل رقماً صحيحاً فقط!")
                        
                elif current_state == "waiting_for_video":
                    if "video" in msg:
                        user_steps[chat_id]["video_id"] = msg["video"]["file_id"]
                        user_steps[chat_id]["step"] = "waiting_for_prizes"
                        send_telegram_message(chat_id, "🎁 ممتاز! الآن أرسل **عدد الجوائز والتفاصيل** الخاصة بالمسابقة:")
                    else:
                        send_telegram_message(chat_id, "❌ يرجى إرسال فيديو صحيح للمسابقة!")
                        
                elif current_state == "waiting_for_prizes":
                    user_steps[chat_id]["prizes"] = text
                    user_steps[chat_id]["step"] = "waiting_for_time"
                    send_telegram_message(chat_id, "⏰ أدخل الآن **موعد إنتهاء المسابقة** (مثلاً: بعد ساعتين):")
                    
                elif current_state == "waiting_for_time":
                    time_left = text
                    state_data = user_steps[chat_id]
                    contest_id = state_data.get("contest_id")
                    video_id = state_data.get("video_id")
                    prizes = state_data.get("prizes")
                    
                    user_steps[chat_id] = {}
                    
                    approved_contest_link = f"https://t.me/Randomalbot?startapp=contest_{contest_id}__r8557464787"
                    
                    caption = (
                        f"🎁 **مسابقة جديدة قيد انتضارك**\n\n"
                        f"🏆 **التفاصيل والجوائز:**\n{prizes}\n\n"
                        f"⏳ تبقى **{time_left}** على نهاية المسابقة\n\n"
                        f"👇 **شارك في السحب من هنا**"
                    )
                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "🚀 شارك في السحب الآن", "url": approved_contest_link}]
                        ]
                    }
                    
                    # 1. النشر في القناة
                    send_telegram_video(CHANNEL_ID, video_id, caption, keyboard)
                    
                    # 2. إرسال التنبيه لجميع أعضاء ومستخدمي البوت داخل خاص البوت
                    user_notification = (
                        f"🚨 **تنبيه مسابقة جديدة!**\n\n"
                        f"تم إطلاق مسابقة جديدة رقم #{contest_id}، سارع بالمشاركة فوراً! 🔥\n\n"
                        f"🏆 **الجوائز:** {prizes}\n"
                        f"⏳ **الوقت المتبقي:** {time_left}"
                    )
                    user_keyboard = {
                        "inline_keyboard": [
                            [{"text": "🚀 شارك في المسابقة الآن", "url": approved_contest_link}]
                        ]
                    }
                    
                    # حلقة تكرارية للإرسال لكل مستخدمي البوت
                    for user_id in bot_users:
                        try:
                            send_telegram_message(user_id, user_notification, user_keyboard)
                        except Exception:
                            pass # في حال قام مستخدم بحظر البوت لا تتوقف العملية

                    send_telegram_message(chat_id, "✅ **تم نشر المسابقة في القناة وإرسال التنبيه لجميع مستخدمي البوت بنجاح!**\n\nاكتب /admin للعودة للوحة التحكم.")

        return '', 200
    return 'OK', 200

@app.route('/')
def index():
    return "🤖 البوت يعمل بكفاءة!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))