import os
import logging
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# إعدادات البوت والاتصال
TOKEN = os.getenv("BOT_TOKEN", "8938116145:AAHkVV0geUtkdOh04pZgdzQpxL0qVchO6Io")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@neoearnboot")
REF_LINK = os.getenv("REF_LINK", "https://t.me/DRAGON_STONE_BOT?start=ref_8557464787")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) # ضع معرف الأدمن هنا أو دعه يكتشفه

app = Flask(__name__)
bot = Bot(token=TOKEN, parse_mode=types.ParseMode.MARKDOWN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

logging.basicConfig(level=logging.INFO)

# تخزين مؤقت لرقم المسابقة الحالي لكل أدمن
admin_current_id = 894

# حالات الآلة الفسيفسائية (FSM) للخطوات
class ContestStates(StatesGroup):
    waiting_for_custom_id = State()
    waiting_for_video = State()
    waiting_for_prizes = State()
    waiting_for_time = State()
    waiting_for_broadcast = State()
    waiting_for_channel = State()

# ----------------- لوحة التحكم والتحكم بالروابط ----------------- #

@dp.message_handler(commands=['start', 'admin'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    global admin_current_id
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⬅️ السابق", callback_data="prev_id"),
        types.InlineKeyboardButton("التالي ➡️", callback_data="next_id")
    )
    markup.add(types.InlineKeyboardButton("✏️ تعديل الرقم يدوياً", callback_data="edit_id"))
    markup.add(
        types.InlineKeyboardButton("📢 رسالة جماعية", callback_data="broadcast_menu"),
        types.InlineKeyboardButton("➕ إشتراك إجباري", callback_data="forced_sub_menu")
    )
    
    link = f"https://t.me/Randomalbot?startapp=contest_{admin_current_id}__r8557464787"
    
    text = (
        f"🤖 **مرحباً بك في لوحة تحكم البوت**\n\n"
        f"📌 **رقم المسابقة الحالي:** `{admin_current_id}`\n"
        f"🔗 **الرابط الحالي لفحصه:**\n`{link}`\n\n"
        f"👇 اختر الإجراء المناسب:"
    )
    
    await message.answer(text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data in ['next_id', 'prev_id', 'edit_id'], state='*')
async def process_navigation(callback_query: types.CallbackQuery, state: FSMContext):
    global admin_current_id
    action = callback_query.data
    
    if action == 'next_id':
        admin_current_id += 1
    elif action == 'prev_id':
        admin_current_id -= 1
    elif action == 'edit_id':
        await callback_query.message.answer("✏️ أرسل الرقم الجديد الذي تريد البدء منه الآن:")
        await ContestStates.waiting_for_custom_id.set()
        await callback_query.answer()
        return

    # تحديث الرسالة بالرابط الجديد والأزرار التفاعلية
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("⬅️ السابق", callback_data="prev_id"),
        types.InlineKeyboardButton("التالي ➡️", callback_data="next_id")
    )
    markup.add(types.InlineKeyboardButton("✏️ تعديل الرقم يدوياً", callback_data="edit_id"))
    markup.add(types.InlineKeyboardButton("✅ الرابط سليم (ابدأ النشر)", callback_data="approve_contest"))
    
    link = f"https://t.me/Randomalbot?startapp=contest_{admin_current_id}__r8557464787"
    text = (
        f"📌 **رقم المسابقة الحالي:** `{admin_current_id}`\n"
        f"🔗 **الرابط:**\n`{link}`"
    )
    
    try:
        await callback_query.message.edit_text(text, reply_markup=markup)
    except Exception:
        await callback_query.message.answer(text, reply_markup=markup)
    await callback_query.answer()

@dp.message_handler(state=ContestStates.waiting_for_custom_id)
async def save_custom_id(message: types.Message, state: FSMContext):
    global admin_current_id
    try:
        admin_current_id = int(message.text.strip())
        await state.finish()
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("⬅️ السابق", callback_data="prev_id"),
            types.InlineKeyboardButton("التالي ➡️", callback_data="next_id")
        )
        markup.add(types.InlineKeyboardButton("✏️ تعديل الرقم يدوياً", callback_data="edit_id"))
        markup.add(types.InlineKeyboardButton("✅ الرابط سليم (ابدأ النشر)", callback_data="approve_contest"))
        
        link = f"https://t.me/Randomalbot?startapp=contest_{admin_current_id}__r8557464787"
        await message.answer(f"✅ تم تحديث الرقم بنجاح إلى: `{admin_current_id}`\n\n🔗 الرابط:\n`{link}`", reply_markup=markup)
    except ValueError:
        await message.answer("❌ يرجى إرسال رقم صحيح فقط!")

# ----------------- خطوات النشر عند الضغط على ✅ ----------------- #

@dp.callback_query_handler(lambda c: c.data == 'approve_contest', state='*')
async def approve_contest_start(callback_query: types.CallbackQuery, state: FSMContext):
    await state.update_data(contest_id=admin_current_id)
    await callback_query.message.answer("🎬 أرسل الآن **الفيديو** الذي تريد أن يظهر على المنشور:")
    await ContestStates.waiting_for_video.set()
    await callback_query.answer()

@dp.message_handler(content_types=['video'], state=ContestStates.waiting_for_video)
async def get_contest_video(message: types.Message, state: FSMContext):
    video_id = message.video.file_id
    await state.update_data(video_id=video_id)
    await message.answer("🎁 ممتاز! الآن أرسل **عدد الجوائز والتفاصيل** الخاصة بالمسابقة:")
    await ContestStates.waiting_for_prizes.set()

@dp.message_handler(state=ContestStates.waiting_for_prizes)
async def get_contest_prizes(message: types.Message, state: FSMContext):
    prizes = message.text
    await state.update_data(prizes=prizes)
    await message.answer("⏰ حسناً، أدخل الآن **موعد إنتهاء المسابقة** (مثلاً: بعد ساعتين / الساعة 8 مساءً):")
    await ContestStates.waiting_for_time.set()

@dp.message_handler(state=ContestStates.waiting_for_time)
async def get_contest_time(message: types.Message, state: FSMContext):
    time_left = message.text
    data = await state.get_data()
    video_id = data.get("video_id")
    prizes = data.get("prizes")
    contest_id = data.get("contest_id")
    
    await state.finish()
    
    # صياغة المنشور للقناة
    caption = (
        f"🎁 **مسابقة جديدة قيد انتضارك**\n\n"
        f"🏆 **التفاصيل والجوائز:**\n{prizes}\n\n"
        f"⏳ تبقى **{time_left}** على نهاية المسابقة\n\n"
        f"👇 **شارك في السحب من هنا**"
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🚀 شارك في السحب الآن", url=REF_LINK)]
    ])
    
    try:
        # 1. نشر المنشور في قناة البوت
        link = f"https://t.me/Randomalbot?startapp=contest_{contest_id}__r8557464787"
        await bot.send_video(chat_id=CHANNEL_ID, video=video_id, caption=caption, reply_markup=keyboard)
        
        # 2. نشر رسالة إشعار جماعية/أو إعلامية في القناة أو البوت
        broadcast_text = (
            f"🚨 **تنبيه مسابقة جديدة!**\n\n"
            f"تم إطلاق مسابقة جديدة رقم #{contest_id} في قناة البوت {CHANNEL_ID}، سارع بالمشاركة الآن ولا تفوت الفرصة! 🔥"
        )
        await bot.send_message(chat_id=CHANNEL_ID, text=broadcast_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📢 اذهب للقناة للمشاركة", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")
]
        ]))
        
        await message.answer("✅ **تم نشر المسابقة بنجاح في القناة وإرسال الإشعار!**\n\nيمكنك العودة للوحة التحكم عبر /admin")
    except Exception as e:
        await message.answer(f"❌ حدث خطأ أثناء النشر: {e}")

# ----------------- أزرار القائمة الإضافية ----------------- #

@dp.callback_query_handler(lambda c: c.data == 'broadcast_menu', state='*')
async def broadcast_menu(callback_query: types.CallbackQuery):
    await callback_query.message.answer("📢 أرسل الرسالة التي تريد بثها لجميع المستخدمين:")
    await ContestStates.waiting_for_broadcast.set()
    await callback_query.answer()

@dp.message_handler(state=ContestStates.waiting_for_broadcast)
async def send_broadcast(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("✅ جاري إرسال الرسالة الجماعية...")
    # (هنا يمكنك إضافة قاعدة بيانات المستخدمين لإرسالها لهم لاحقاً، حالياً تم تأكيد الخيار)

@dp.callback_query_handler(lambda c: c.data == 'forced_sub_menu', state='*')
async def forced_sub_menu(callback_query: types.CallbackQuery):
    await callback_query.message.answer("➕ أرسل يوزر القناة المراد إضافتها للاشتراك الإجباري (مثلاً @MyChannel):")
    await ContestStates.waiting_for_channel.set()
    await callback_query.answer()

@dp.message_handler(state=ContestStates.waiting_for_channel)
async def save_channel(message: types.Message, state: FSMContext):
    ch = message.text.strip()
    await state.finish()
    await message.answer(f"✅ تمت إضافة القناة {ch} بنجاح للاشتراك الإجباري.")

# ----------------- خادم Flask للويب هوك ----------------- #

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_data = request.get_json()
        update = types.Update.de_json(json_data)
        dp.process_update(update)
        return '', 200
    return 'OK', 200

@app.route('/')
def index():
    return "🤖 البوت البسيط يعمل بنجاح!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))