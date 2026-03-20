import sqlite3
import telebot
import os
import platform
import time

# ================= إعدادات البوت والمالك =================
TOKEN = '8602810587:AAFtLOLeRfzafZmcm6R8L0zYOOd8TO3ePEE'
OWNER_ID = 1269208011 

bot = telebot.TeleBot(TOKEN)

# ================= إعدادات قاعدة البيانات (آمنة ولا تحذف البيانات القديمة) =================
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS banned_users (user_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    # تحديث الجدول القديم وإضافة عمود التاريخ بدون مسح الرسايل
    try:
        c.execute("ALTER TABLE messages ADD COLUMN date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except sqlite3.OperationalError:
        pass # لو العمود موجود أصلاً، هيتجاهل الأمر ويكمل عادي
        
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'off')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('spy', 'on')")
    conn.commit()
    conn.close()

init_db()

# ================= دوال التحكم والتحقق =================
def get_all_admins():
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("SELECT user_id FROM admins")
    admins_list = [row[0] for row in c.fetchall()]
    conn.close()
    if OWNER_ID not in admins_list: admins_list.append(OWNER_ID)
    return admins_list

def is_admin(user_id): return user_id in get_all_admins()
def is_banned(user_id):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("SELECT user_id FROM banned_users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close()
    return res is not None

def get_setting(key):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    res = c.fetchone(); conn.close()
    return res[0] if res else 'off'

def set_setting(key, value):
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    conn.commit(); conn.close()

# ================= 👑 لوحة تحكم God Mode =================
@bot.message_handler(commands=['shls', 'admin'])
def admin_panel(message):
    if not is_admin(message.from_user.id): return
    text = """👑 لوحة تحكم God Mode

🛑 /maintenance on/off - وضع الصيانة
👁️ /spy on/off - المراقبة اللحظية
💬 /reply [ID] [الرسالة] - الرد المباشر المجهول
🔍 /info [ID] - ملف مستخدم كامل
🗂️ /history [ID] - عرض أرشيف المحادثات
➕ /addadmin [ID] - إضافة أدمن جديد
💻 /sysinfo - مراقبة السيرفر
🗑️ /clear_db - مسح الداتا بيز الشامل
📊 /users_count - عدد المستخدمين
📢 /broadcast [رسالة] - إذاعة رسالة
🚫 /ban [ID] - حظر مستخدم
✅ /unban [ID] - فك حظر مستخدم
💾 /export - تحميل نسخة من قاعدة البيانات"""
    bot.reply_to(message, text)

# ================= أوامر الإدارة الشاملة =================
@bot.message_handler(commands=['info'])
def user_info(message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 2: return bot.reply_to(message, "❌ الصيغة: `/info [ID]`", parse_mode="Markdown")
    try:
        uid = int(args[1])
        conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
        c.execute("SELECT name FROM users WHERE user_id = ?", (uid,))
        user = c.fetchone()
        if not user: return bot.reply_to(message, "❌ المستخدم غير موجود.")
        c.execute("SELECT COUNT(*) FROM messages WHERE user_id = ?", (uid,))
        msgs_count = c.fetchone()[0]
        status = "محظور 🚫" if is_banned(uid) else "نشط ✅"
        role = "أدمن 👑" if is_admin(uid) else "عضو عادي 👤"
        conn.close()
        bot.reply_to(message, f"🔍 **ملف المستخدم:**\n\n👤 الاسم: [{user[0]}](tg://user?id={uid})\n🆔 الآيدي: `{uid}`\n💬 عدد رسائله: {msgs_count}\n📊 الحالة: {status}\n⭐ الرتبة: {role}\n\n💡 للأرشيف: `/history {uid}`\n💡 للرد: `/reply {uid} رسالتك`", parse_mode="Markdown")
    except ValueError: bot.reply_to(message, "❌ الآيدي يجب أن يكون أرقام.")

@bot.message_handler(commands=['history'])
def user_history(message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 2: return bot.reply_to(message, "❌ الصيغة: `/history [ID]`", parse_mode="Markdown")
    try:
        uid = int(args[1])
        conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
        
        # محاولة جلب الرسائل مع التاريخ (لو الداتا بيز اتحدثت)
        try:
            c.execute("SELECT text, date_added FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT 15", (uid,))
            msgs = c.fetchall()
            has_date = True
        except sqlite3.OperationalError:
            # لو العمود مش موجود (داتا بيز قديمة)، هنجيب النص بس عشان ميضربش إيرور
            c.execute("SELECT text FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT 15", (uid,))
            msgs = c.fetchall()
            has_date = False
            
        conn.close()
        
        if not msgs: return bot.reply_to(message, f"📭 لا توجد رسائل للمستخدم `{uid}`.", parse_mode="Markdown")
        
        history_text = f"📂 **أرشيف رسائل `{uid}`:**\n\n"
        for row in reversed(msgs):
            if has_date:
                text, date = row
                date_str = date[:16] if date else "غير محدد"
            else:
                text = row[0]
                date_str = "تاريخ قديم"
                
            history_text += f"🕒 `{date_str}`\n💬 {text}\n〰️〰️\n"
            
        bot.reply_to(message, history_text[:4000], parse_mode="Markdown")
    except ValueError: 
        bot.reply_to(message, "❌ خطأ في الآيدي.")

@bot.message_handler(commands=['reply'])
def admin_reply(message):
    if not is_admin(message.from_user.id): return
    args = message.text.split(maxsplit=2)
    if len(args) < 3: return bot.reply_to(message, "❌ الصيغة: `/reply [ID] [الرسالة]`", parse_mode="Markdown")
    try:
        bot.send_message(int(args[1]), f"📩 رسالة من الإدارة:\n\n{args[2]}")
        bot.reply_to(message, "✅ تم إرسال الرد.")
    except Exception: bot.reply_to(message, "❌ فشل الإرسال (تأكد من الآيدي أو ربما تم حظرك).")

@bot.message_handler(commands=['addadmin'])
def add_admin(message):
    if message.from_user.id != OWNER_ID: return bot.reply_to(message, "❌ للمالك فقط.")
    args = message.text.split()
    if len(args) < 2: return bot.reply_to(message, "❌ الصيغة: `/addadmin [ID]`", parse_mode="Markdown")
    try:
        uid = int(args[1])
        conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO admins VALUES (?)", (uid,)); conn.commit(); conn.close()
        bot.reply_to(message, f"✅ تم ترقية `{uid}` لأدمن.", parse_mode="Markdown")
    except ValueError: bot.reply_to(message, "❌ خطأ في الآيدي.")

@bot.message_handler(commands=['maintenance', 'spy'])
def toggle_settings(message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 2 or args[1].lower() not in ['on', 'off']: return bot.reply_to(message, f"❌ استخدم: `{args[0]} on/off`", parse_mode="Markdown")
    key = 'maintenance' if '/maintenance' in args[0] else 'spy'
    set_setting(key, args[1].lower())
    bot.reply_to(message, f"✅ تم ضبط {key} على {args[1].upper()}")

@bot.message_handler(commands=['sysinfo'])
def system_info(message):
    if not is_admin(message.from_user.id): return
    bot.reply_to(message, f"💻 **السيرفر:**\nنظام: {platform.system()} {platform.release()}\nقاعدة البيانات: {os.path.getsize('bot_data.db') / 1024:.2f} KB", parse_mode="Markdown")

@bot.message_handler(commands=['clear_db'])
def clear_database(message):
    if message.from_user.id != OWNER_ID: return bot.reply_to(message, "❌ للمالك فقط.")
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("DELETE FROM messages"); conn.commit(); conn.close()
    bot.reply_to(message, "🗑️ تم مسح أرشيف الرسائل.")

@bot.message_handler(commands=['users_count'])
def count_users(message):
    if not is_admin(message.from_user.id): return
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); u = c.fetchone()[0]; conn.close()
    bot.reply_to(message, f"📊 عدد المستخدمين: {u}")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if not is_admin(message.from_user.id): return
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return bot.reply_to(message, "❌ الصيغة: `/broadcast [الرسالة]`", parse_mode="Markdown")
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("SELECT user_id FROM users"); users = c.fetchall(); conn.close()
    bot.reply_to(message, "📢 جاري الإذاعة...")
    success, failed = 0, 0
    for (uid,) in users:
        try: bot.send_message(uid, f"📢 إعلان:\n\n{args[1]}"); success += 1; time.sleep(0.05)
        except: failed += 1
    bot.reply_to(message, f"✅ الإذاعة تمت!\nنجاح: {success}\nفشل: {failed}")

@bot.message_handler(commands=['ban', 'unban'])
def ban_unban_user(message):
    if not is_admin(message.from_user.id): return
    args = message.text.split()
    if len(args) < 2: return bot.reply_to(message, "❌ الصيغة: `/ban [ID]`", parse_mode="Markdown")
    try:
        uid, conn = int(args[1]), sqlite3.connect('bot_data.db'); c = conn.cursor()
        if '/ban' in args[0]: c.execute("INSERT OR IGNORE INTO banned_users VALUES (?)", (uid,)); bot.reply_to(message, f"🚫 تم حظر `{uid}`", parse_mode="Markdown")
        else: c.execute("DELETE FROM banned_users WHERE user_id = ?", (uid,)); bot.reply_to(message, f"✅ تم فك حظر `{uid}`", parse_mode="Markdown")
        conn.commit(); conn.close()
    except: bot.reply_to(message, "❌ خطأ في الآيدي.")

@bot.message_handler(commands=['export'])
def export_db(message):
    if not is_admin(message.from_user.id): return
    try:
        with open('bot_data.db', 'rb') as doc: bot.send_document(message.chat.id, doc, caption="💾 نسخة من قاعدة البيانات")
    except Exception as e: bot.reply_to(message, f"❌ خطأ: {e}")

# ================= معالجة المستخدمين وإشعارات الإدارة =================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if is_banned(user_id): return
    if get_setting('maintenance') == 'on' and not is_admin(user_id):
        return bot.reply_to(message, "🛑 البوت في وضع الصيانة.")
        
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    is_existing = c.fetchone()
    
    if not is_existing and not is_admin(user_id):
        c.execute("INSERT INTO users (user_id, name) VALUES (?, ?)", (user_id, str(message.from_user.first_name)))
        conn.commit()
        # إشعار العضو الجديد للإدارة
        for admin_id in get_all_admins():
            try: bot.send_message(admin_id, f"🚨 **دخول عضو جديد!**\n\n👤 الاسم: [{message.from_user.first_name}](tg://user?id={user_id})\n🆔 الآيدي: `{user_id}`", parse_mode="Markdown")
            except: pass
    conn.close()

    if is_admin(user_id): bot.reply_to(message, "أهلاً يا أدمن 👑. أرسل /shls للوحة التحكم.")
    else: bot.reply_to(message, f"أهلاً بك يا {message.from_user.first_name} 👋\nأرسل رسالتك وسنقوم بالرد عليك.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle_user_messages(message):
    if message.text and message.text.startswith('/'): return
    user_id = message.from_user.id
    user_name = str(message.from_user.first_name).replace('_', ' ').replace('*', '').replace('`', '')
    
    if is_banned(user_id): return
    if get_setting('maintenance') == 'on' and not is_admin(user_id): return bot.reply_to(message, "🛑 البوت في وضع الصيانة.")
    if is_admin(user_id): return bot.reply_to(message, "💡 أنت أدمن، للتواصل استخدم `/reply [ID] [الرسالة]`.", parse_mode="Markdown")

    msg_text = message.text or message.caption or "📸 [رسالة وسائط]"
    conn = sqlite3.connect('bot_data.db'); c = conn.cursor()
    c.execute("INSERT INTO messages (user_id, text) VALUES (?, ?)", (user_id, msg_text))
    conn.commit(); conn.close()

    bot.reply_to(message, "✅ تم إرسال رسالتك للإدارة.")
    
    if get_setting('spy') == 'on':
        for admin_id in get_all_admins():
            try:
                bot.forward_message(admin_id, message.chat.id, message.message_id)
                bot.send_message(admin_id, f"⬆️ رسالة من: [{user_name}](tg://user?id={user_id})\n🆔 الآيدي: `{user_id}`\n\nللرد: `/reply {user_id} الرد`\nللأرشيف: `/history {user_id}`", parse_mode="Markdown")
            except: pass

print("--- البوت يعمل الآن بكامل الأوامر وإشعار الدخول، والبيانات آمنة 100% ---")
bot.infinity_polling()