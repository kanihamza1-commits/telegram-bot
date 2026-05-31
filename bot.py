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
# ⚙️ SETTINGS
# ========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))

BOOKS_LINK = "https://drive.google.com/drive/folders/1Dpr_Vjmf4cAGiEcsxZdp-HhX7tL8LZgJ?usp=drive_link"

WELCOME_MESSAGE = """❗️Please read the following carefully so we can work together effectively.❗️

🧾 I have received your payment — thank you!

Welcome to our Premium Trading Community! From now on, all trade analyses will be shared privately between us.

✅ You will receive detailed 1D, 4H, and 1H trade updates.
✅ Feel free to ask me any questions at any time.
✅ There is always enough time to enter trades, so no need to rush or panic.

Looking forward to working with you! 🚀"""

BOOKS_MESSAGE = """📚 *Recommended Reading*

To support your learning, I have compiled a collection of books that will help you gain a deeper and clearer understanding of Elliott Wave Theory.

I have uploaded them to Google Drive and recently added new books to the collection.

📥 You can download them here:
{}""".format(BOOKS_LINK)

RISK_MESSAGE = """⚠️ *Risk Management Guide*

This is extremely important — please read it carefully before placing any trade."""

# ========================================
# 🗄️ DATABASE
# ========================================
def init_db():
    conn = sqlite3.connect("subscribers.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            full_name     TEXT,
            email         TEXT,
            membership    TEXT,
            joined_at     TEXT,
            expiry_date   TEXT,
            is_active     INTEGER DEFAULT 1,
            step          TEXT DEFAULT 'done'
        )
    """)
    conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect("subscribers.db")

def upsert_user(user_id, username, full_name):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO users (user_id, username, full_name, joined_at, step)
        VALUES (?, ?, ?, ?, 'ask_email')
    """, (user_id, username, full_name, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def set_step(user_id, step):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET step = ? WHERE user_id = ?", (step, user_id))
    conn.commit()
    conn.close()

def set_email(user_id, email):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET email = ?, step = 'ask_membership' WHERE user_id = ?", (email, user_id))
    conn.commit()
    conn.close()

def set_membership(user_id, membership):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET membership = ?, step = 'done', is_active = 1 WHERE user_id = ?", (membership, user_id))
    conn.commit()
    conn.close()

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
    c.execute("SELECT user_id, username, full_name, email, membership, joined_at, expiry_date, is_active FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def get_expiring_users():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, expiry_date FROM users WHERE expiry_date = ? AND is_active = 1", (tomorrow,))
    rows = c.fetchall()
    conn.close()
    return rows

def count_active():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    total = c.fetchone()[0]
    conn.close()
    return total

# ========================================
# 🤖 USER COMMANDS
# ========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = get_user(user.id)

    if existing and existing[8] == 'done':
        await update.message.reply_text(
            f"👋 Welcome back, {user.first_name}!\n\n"
            "You're already registered. Use /status to check your membership."
        )
        return

    upsert_user(user.id, user.username or "", user.full_name or "")

    await update.message.reply_text(
        f"👋 Hello! Welcome to *Wave Kani Premium Trading* 📊\n\n"
        "I'm glad to have you here!\n\n"
        "📧 To get started, please share your *email address*:",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("❌ You're not registered yet. Please type /start")
        return

    is_active = user[7]
    expiry = user[6]
    membership = user[4] or "Not set"

    if is_active:
        exp_text = f"📅 Expires on: {expiry}" if expiry else "✅ Lifetime membership"
        await update.message.reply_text(
            f"✅ Your subscription is *active*\n"
            f"📋 Plan: {membership}\n"
            f"{exp_text}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ Your subscription is not active.\n"
            "Please contact the admin to renew."
        )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Available Commands:*\n\n"
        "/start — Register your account\n"
        "/status — Check your membership status\n"
        "/contact — Send a message to the admin",
        parse_mode="Markdown"
    )

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("✏️ Write your message after the command:\n/contact your message here")
        return
    msg = " ".join(context.args)
    await context.bot.send_message(
        ADMIN_ID,
        f"📩 *Message from subscriber:*\n"
        f"Name: {user.full_name}\n"
        f"ID: `{user.id}`\n"
        f"@{user.username or 'no username'}\n\n"
        f"Message: {msg}",
        parse_mode="Markdown"
    )
    await update.message.reply_text("✅ Your message has been sent to the admin.")

# ========================================
# 👑 ADMIN PANEL
# ========================================
def is_admin(user_id):
    return user_id == ADMIN_ID

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return

    total = count_active()
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast to All", callback_data="broadcast")],
        [InlineKeyboardButton("👥 Subscribers List", callback_data="list_users")],
        [InlineKeyboardButton("📊 Statistics", callback_data="stats")],
        [InlineKeyboardButton("➕ Renew Membership", callback_data="set_expiry")],
        [InlineKeyboardButton("🚫 Deactivate Member", callback_data="deactivate")],
    ]
    await update.message.reply_text(
        f"👑 *Admin Panel*\n👥 Active subscribers: {total}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data

    if data == "stats":
        users = get_all_users()
        active = sum(1 for u in users if u[7] == 1)
        inactive = len(users) - active
        await query.edit_message_text(
            f"📊 *Statistics:*\n\n"
            f"Total subscribers: {len(users)}\n"
            f"Active: {active}\n"
            f"Inactive: {inactive}",
            parse_mode="Markdown"
        )

    elif data == "broadcast":
        context.user_data["action"] = "broadcast"
        await query.edit_message_text("📢 Send the message you want to broadcast to all subscribers:")

    elif data == "list_users":
        users = get_all_users()
        if not users:
            await query.edit_message_text("No subscribers yet.")
            return
        text = "👥 *Subscribers List:*\n\n"
        for u in users[:20]:
            icon = "✅" if u[7] == 1 else "❌"
            text += f"{icon} {u[2]} | `{u[0]}` | {u[4] or 'N/A'} | Exp: {u[6] or 'Lifetime'}\n"
        if len(users) > 20:
            text += f"\n...and {len(users)-20} more"
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "set_expiry":
        context.user_data["action"] = "set_expiry"
        await query.edit_message_text(
            "➕ To renew a membership, send:\n"
            "`USER_ID NUMBER_OF_DAYS`\n\n"
            "Example: `123456789 30`",
            parse_mode="Markdown"
        )

    elif data == "deactivate":
        context.user_data["action"] = "deactivate"
        await query.edit_message_text("🚫 Send the user ID to deactivate:")

    # Membership selection buttons
    elif data.startswith("membership_"):
        plan = data.replace("membership_", "")
        user_id = context.user_data.get("pending_membership_user")
        if user_id:
            set_membership(user_id, plan)
            context.user_data.pop("pending_membership_user", None)
            await query.edit_message_text(f"✅ Membership set to: *{plan}*", parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    user_id,
                    f"✅ Your membership plan has been set: *{plan}*\n\nWelcome aboard! 🚀",
                    parse_mode="Markdown"
                )
            except:
                pass

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast your message here")
        return
    msg = " ".join(context.args)
    users = get_all_active_users()
    success, failed = 0, 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 *New Update:*\n\n{msg}", parse_mode="Markdown")
            success += 1
        except:
            failed += 1
    await update.message.reply_text(f"✅ Broadcast done!\nSuccess: {success} | Failed: {failed}")

async def reply_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /reply USER_ID your message")
        return
    target_id = context.args[0]
    msg = " ".join(context.args[1:])
    try:
        await context.bot.send_message(int(target_id), f"💬 *Private message from admin:*\n\n{msg}", parse_mode="Markdown")
        await update.message.reply_text("✅ Message sent successfully.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

async def setexpiry_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setexpiry USER_ID DAYS")
        return
    user_id = int(context.args[0])
    days = int(context.args[1])
    expiry = set_expiry(user_id, days)
    await update.message.reply_text(f"✅ Membership renewed until: {expiry}")
    try:
        await context.bot.send_message(user_id, f"🎉 Your subscription has been renewed!\nExpires on: *{expiry}*", parse_mode="Markdown")
    except:
        pass

async def deactivate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /deactivate USER_ID")
        return
    user_id = int(context.args[0])
    deactivate_user(user_id)
    await update.message.reply_text(f"✅ User {user_id} has been deactivated.")
    try:
        await context.bot.send_message(user_id, "❌ Your subscription has been deactivated. Please contact the admin.")
    except:
        pass

# ========================================
# 💬 MESSAGE HANDLER (registration flow + admin actions)
# ========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    # ADMIN actions
    if is_admin(user.id):
        action = context.user_data.get("action")

        if action == "broadcast":
            users = get_all_active_users()
            success, failed = 0, 0
            for uid in users:
                try:
                    await context.bot.send_message(uid, f"📢 *New Update:*\n\n{text}", parse_mode="Markdown")
                    success += 1
                except:
                    failed += 1
            context.user_data.pop("action", None)
            await update.message.reply_text(f"✅ Broadcast done!\nSuccess: {success} | Failed: {failed}")
            return

        elif action == "set_expiry":
            parts = text.split()
            if len(parts) == 2:
                uid, days = int(parts[0]), int(parts[1])
                expiry = set_expiry(uid, days)
                context.user_data.pop("action", None)
                await update.message.reply_text(f"✅ Membership renewed until: {expiry}")
                try:
                    await context.bot.send_message(uid, f"🎉 Your subscription has been renewed!\nExpires on: *{expiry}*", parse_mode="Markdown")
                except:
                    pass
            else:
                await update.message.reply_text("❌ Wrong format. Send: USER_ID DAYS")
            return

        elif action == "deactivate":
            uid = int(text.strip())
            deactivate_user(uid)
            context.user_data.pop("action", None)
            await update.message.reply_text(f"✅ User {uid} deactivated.")
            return

    # USER registration flow
    db_user = get_user(user.id)
    if not db_user:
        await update.message.reply_text("Please type /start to register.")
        return

    step = db_user[8]

    if step == "ask_email":
        # Save email
        set_email(user.id, text)

        # Ask membership type
        keyboard = [
            [InlineKeyboardButton("📅 1 Month", callback_data="membership_1 Month")],
            [InlineKeyboardButton("📅 3 Months", callback_data="membership_3 Months")],
            [InlineKeyboardButton("📅 1 Year", callback_data="membership_1 Year")],
        ]
        await update.message.reply_text(
            "✅ Email saved!\n\n📋 What is your membership period?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif step == "ask_membership":
        # fallback if they type instead of pressing button
        set_membership(user.id, text)
        await send_welcome_package(update, context, user.id)

async def handle_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not data.startswith("membership_"):
        return

    # Check if this is admin setting membership for another user
    if is_admin(query.from_user.id) and "pending_membership_user" in context.user_data:
        plan = data.replace("membership_", "")
        uid = context.user_data.pop("pending_membership_user")
        set_membership(uid, plan)
        await query.edit_message_text(f"✅ Membership set to: *{plan}*", parse_mode="Markdown")
        try:
            await context.bot.send_message(uid, f"✅ Your plan: *{plan}*\nWelcome! 🚀", parse_mode="Markdown")
        except:
            pass
        return

    # User selecting their own membership
    plan = data.replace("membership_", "")
    user_id = query.from_user.id
    set_membership(user_id, plan)

    await query.edit_message_text(
        f"✅ *Membership period:* {plan}\n\nThank you! Sending your welcome package... 📦",
        parse_mode="Markdown"
    )

    await send_welcome_package_by_id(context.bot, query.from_user, user_id)

    # Notify admin
    user = query.from_user
    db_user = get_user(user_id)
    email = db_user[3] if db_user else "N/A"
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 *New Subscriber!*\n\n"
        f"Name: {user.full_name}\n"
        f"Username: @{user.username or 'none'}\n"
        f"ID: `{user.id}`\n"
        f"Email: {email}\n"
        f"Plan: {plan}\n\n"
        f"Total active: {count_active()}",
        parse_mode="Markdown"
    )

async def send_welcome_package(update, context, user_id):
    await update.message.reply_text(WELCOME_MESSAGE)
    await update.message.reply_text(BOOKS_MESSAGE, parse_mode="Markdown")
    await update.message.reply_text(RISK_MESSAGE, parse_mode="Markdown")
    try:
        with open("risk_management.pdf", "rb") as f:
            await context.bot.send_document(user_id, f, filename="Wave_Kani_Risk_Management.pdf")
    except:
        pass

async def send_welcome_package_by_id(bot, user, user_id):
    await bot.send_message(user_id, WELCOME_MESSAGE)
    await bot.send_message(user_id, BOOKS_MESSAGE, parse_mode="Markdown")
    await bot.send_message(user_id, RISK_MESSAGE, parse_mode="Markdown")
    try:
        with open("risk_management.pdf", "rb") as f:
            await bot.send_document(user_id, f, filename="Wave_Kani_Risk_Management.pdf")
    except:
        pass

# ========================================
# ⏰ DAILY EXPIRY CHECK
# ========================================
async def check_expiry(context: ContextTypes.DEFAULT_TYPE):
    expiring = get_expiring_users()
    for user_id, full_name, expiry in expiring:
        try:
            await context.bot.send_message(
                user_id,
                f"⚠️ *Reminder:* Your subscription expires tomorrow ({expiry})!\n"
                "Please contact the admin to renew.",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                ADMIN_ID,
                f"⚠️ Subscription expiring tomorrow:\n{full_name} | ID: `{user_id}`",
                parse_mode="Markdown"
            )
        except:
            pass

# ========================================
# 🚀 MAIN
# ========================================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("contact", contact))

    # Admin commands
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("reply", reply_cmd))
    app.add_handler(CommandHandler("setexpiry", setexpiry_cmd))
    app.add_handler(CommandHandler("deactivate", deactivate_cmd))

    # Callbacks — membership first, then general
    app.add_handler(CallbackQueryHandler(handle_membership_callback, pattern="^membership_"))
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Daily expiry check at 9AM
    app.job_queue.run_daily(check_expiry, time=datetime.strptime("09:00", "%H:%M").time())

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
