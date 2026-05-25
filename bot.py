import os
import sqlite3
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ========================================
# ⚙️ الإعدادات — غيّر هذه القيم فقط
# ========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ضع-توكن-البوت-هنا")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "ضع-رقم-حسابك-هنا"))  # رقم ID الخاص بك في تيليغرام

# ========================================
# 🗄️ قاعدة البيانات
# ========================================
def init_db():
    conn = sqlite3.connect("subscribers.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            joined_at   TEXT,
            expiry_date TEXT,
            is_active   INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect("subscribers.db")

def add_user(user_id, username, full_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO users (user_id, username, full_name, joined_at, expiry_date, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (user_id, username, full_name, datetime.now().strftime("%Y-%m-%d %H:%M"), None))
    conn.commit()
    conn.close()

def get_all_active_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_active = 1")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, username, full_name, joined_at, expiry_date, is_active FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def set_expiry(user_id, days):
    expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET expiry_date = ?, is_active = 1 WHERE user_id = ?", (expiry, user_id))
    conn.commit()
    conn.close()
    return expiry

def deactivate_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def activate_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_active = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_expiring_users():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, expiry_date FROM users WHERE expiry_date = ? AND is_active = 1", (tomorrow,))
    rows = c.fetchall()
    conn.close()
    return rows

def count_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    total = c.fetchone()[0]
    conn.close()
    return total

# ========================================
# 🤖 أوامر المستخدمين
# ========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username or "", user.full_name or "")

    text = (
        f"👋 مرحباً {user.first_name}!\n\n"
        "شكراً على اشتراكك في خدمتنا.\n"
        "ستصلك التحديثات والتحليلات مباشرة هنا.\n\n"
        "📌 الأوامر المتاحة:\n"
        "/status — معرفة حالة اشتراكك\n"
        "/help — المساعدة"
    )
    await update.message.reply_text(text)

    # إشعار الأدمن
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 مشترك جديد!\n"
        f"الاسم: {user.full_name}\n"
        f"يوزرنيم: @{user.username or 'لا يوجد'}\n"
        f"ID: {user.id}\n"
        f"إجمالي المشتركين: {count_users()}"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT is_active, expiry_date FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("❌ لست مسجلاً، اكتب /start أولاً.")
        return

    is_active, expiry = row
    if is_active:
        exp_text = f"📅 تنتهي في: {expiry}" if expiry else "✅ عضوية دائمة"
        await update.message.reply_text(f"✅ اشتراكك نشط\n{exp_text}")
    else:
        await update.message.reply_text("❌ اشتراكك غير نشط، تواصل مع الأدمن.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 الأوامر:\n"
        "/start — تسجيل الاشتراك\n"
        "/status — حالة الاشتراك\n\n"
        "للتواصل مع الأدمن: /contact"
    )

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("✏️ اكتب رسالتك بعد الأمر:\n/contact رسالتك هنا")
        return
    msg = " ".join(context.args)
    await context.bot.send_message(
        ADMIN_ID,
        f"📩 رسالة من مشترك:\n"
        f"الاسم: {user.full_name}\n"
        f"ID: {user.id}\n"
        f"@{user.username or 'لا يوجد'}\n\n"
        f"الرسالة: {msg}"
    )
    await update.message.reply_text("✅ تم إرسال رسالتك للأدمن.")

# ========================================
# 👑 لوحة تحكم الأدمن
# ========================================
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الأمر للأدمن فقط.")
            return
        return await func(update, context)
    return wrapper

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = count_users()
    keyboard = [
        [InlineKeyboardButton("📢 بث رسالة للكل", callback_data="broadcast")],
        [InlineKeyboardButton("👥 قائمة المشتركين", callback_data="list_users")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("➕ تجديد عضوية", callback_data="set_expiry")],
        [InlineKeyboardButton("🚫 إلغاء عضوية", callback_data="deactivate")],
    ]
    await update.message.reply_text(
        f"👑 لوحة التحكم\n👥 المشتركين النشطين: {total}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    data = query.data

    if data == "stats":
        users = get_all_users()
        active = sum(1 for u in users if u[5] == 1)
        inactive = len(users) - active
        await query.edit_message_text(
            f"📊 الإحصائيات:\n"
            f"إجمالي المشتركين: {len(users)}\n"
            f"النشطين: {active}\n"
            f"غير النشطين: {inactive}"
        )

    elif data == "broadcast":
        context.user_data["action"] = "broadcast"
        await query.edit_message_text("📢 أرسل الرسالة التي تريد بثها للجميع:")

    elif data == "list_users":
        users = get_all_users()
        if not users:
            await query.edit_message_text("لا يوجد مشتركين بعد.")
            return
        text = "👥 قائمة المشتركين:\n\n"
        for u in users[:20]:  # أول 20 فقط
            status_icon = "✅" if u[5] == 1 else "❌"
            text += f"{status_icon} {u[2]} | ID: {u[0]} | ينتهي: {u[4] or 'دائم'}\n"
        if len(users) > 20:
            text += f"\n... و{len(users)-20} آخرين"
        await query.edit_message_text(text)

    elif data == "set_expiry":
        context.user_data["action"] = "set_expiry"
        await query.edit_message_text(
            "➕ لتجديد عضوية، أرسل:\n"
            "ID_المستخدم عدد_الأيام\n\n"
            "مثال: 123456789 30"
        )

    elif data == "deactivate":
        context.user_data["action"] = "deactivate"
        await query.edit_message_text(
            "🚫 لإلغاء عضوية، أرسل ID المستخدم:"
        )

@admin_only
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استخدام: /broadcast رسالتك هنا")
        return
    msg = " ".join(context.args)
    users = get_all_active_users()
    success, failed = 0, 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 تحديث جديد:\n\n{msg}")
            success += 1
        except:
            failed += 1
    await update.message.reply_text(
        f"✅ تم الإرسال!\nنجح: {success} | فشل: {failed}"
    )

@admin_only
async def reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد خاص على مشترك: /reply ID رسالة"""
    if len(context.args) < 2:
        await update.message.reply_text("استخدام: /reply ID_المستخدم رسالتك")
        return
    target_id = context.args[0]
    msg = " ".join(context.args[1:])
    try:
        await context.bot.send_message(int(target_id), f"💬 رسالة خاصة من الأدمن:\n\n{msg}")
        await update.message.reply_text("✅ تم الإرسال بنجاح.")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل الإرسال: {e}")

@admin_only
async def set_expiry_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تجديد عضوية: /setexpiry ID أيام"""
    if len(context.args) < 2:
        await update.message.reply_text("استخدام: /setexpiry ID_المستخدم عدد_الأيام")
        return
    user_id = int(context.args[0])
    days = int(context.args[1])
    expiry = set_expiry(user_id, days)
    await update.message.reply_text(f"✅ تم تجديد العضوية حتى: {expiry}")
    try:
        await context.bot.send_message(
            user_id,
            f"🎉 تم تجديد اشتراكك!\nينتهي في: {expiry}"
        )
    except:
        pass

@admin_only
async def deactivate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء عضوية: /deactivate ID"""
    if not context.args:
        await update.message.reply_text("استخدام: /deactivate ID_المستخدم")
        return
    user_id = int(context.args[0])
    deactivate_user(user_id)
    await update.message.reply_text(f"✅ تم إلغاء عضوية المستخدم {user_id}.")
    try:
        await context.bot.send_message(user_id, "❌ تم إلغاء اشتراكك. تواصل مع الأدمن.")
    except:
        pass

# معالجة الرسائل النصية للأدمن
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    action = context.user_data.get("action")

    if action == "broadcast":
        msg = update.message.text
        users = get_all_active_users()
        success, failed = 0, 0
        for uid in users:
            try:
                await context.bot.send_message(uid, f"📢 تحديث جديد:\n\n{msg}")
                success += 1
            except:
                failed += 1
        context.user_data.pop("action", None)
        await update.message.reply_text(f"✅ تم البث!\nنجح: {success} | فشل: {failed}")

    elif action == "set_expiry":
        parts = update.message.text.split()
        if len(parts) == 2:
            user_id, days = int(parts[0]), int(parts[1])
            expiry = set_expiry(user_id, days)
            context.user_data.pop("action", None)
            await update.message.reply_text(f"✅ تم تجديد العضوية حتى: {expiry}")
        else:
            await update.message.reply_text("❌ صيغة خاطئة. أرسل: ID عدد_الأيام")

    elif action == "deactivate":
        user_id = int(update.message.text.strip())
        deactivate_user(user_id)
        context.user_data.pop("action", None)
        await update.message.reply_text(f"✅ تم إلغاء عضوية {user_id}.")

# ========================================
# ⏰ مهمة يومية — فحص انتهاء العضويات
# ========================================
async def check_expiry(context: ContextTypes.DEFAULT_TYPE):
    expiring = get_expiring_users()
    for user_id, full_name, expiry in expiring:
        try:
            await context.bot.send_message(
                user_id,
                f"⚠️ تنبيه: اشتراكك سينتهي غداً ({expiry})!\n"
                "تواصل مع الأدمن للتجديد."
            )
            await context.bot.send_message(
                ADMIN_ID,
                f"⚠️ عضوية تنتهي غداً:\n{full_name} | ID: {user_id}"
            )
        except:
            pass

# ========================================
# 🚀 تشغيل البوت
# ========================================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # أوامر المستخدمين
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("contact", contact))

    # أوامر الأدمن
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("reply", reply_cmd))
    app.add_handler(CommandHandler("setexpiry", set_expiry_cmd))
    app.add_handler(CommandHandler("deactivate", deactivate_cmd))

    # الأزرار
    app.add_handler(CallbackQueryHandler(callback_handler))

    # الرسائل النصية
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # مهمة يومية الساعة 9 صباحاً
    app.job_queue.run_daily(check_expiry, time=datetime.strptime("09:00", "%H:%M").time())

    print("✅ البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
