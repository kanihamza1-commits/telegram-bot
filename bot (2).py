import os
import sqlite3
from datetime import datetime, timedelta, date
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

MEMBERSHIP_DAYS = {
    "3 Months": 90,
    "6 Months": 180,
    "1 Year": 365,
    "Lifetime": None
}

MEMBERSHIP_PRICES = {
    "3 Months": "$299",
    "6 Months": "$499",
    "1 Year": "$799",
    "Lifetime": "$2,199"
}

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

RENEWAL_MESSAGE = """👋 Hello! Wave Kani here!

How have you been?

🗓 Today is the last day of your membership — and I genuinely hope it has been worth every moment.

I would love to continue this journey with you, so I have put together 2 special offers just for you:

🔥 *Special Loyalty Offers — 30% Off:*

🔹 1 Year — ~$799~ → *$559* _(save $240)_
🔹 Lifetime — ~$2,199~ → *$1,539* _(one payment, forever)_

Or renew your previous plan at the same price:

▪️ 3 Months — $299
▪️ 6 Months — $499

What do you think? 😊

— Wave Kani"""

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
            start_date    TEXT,
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
        INSERT OR IGNORE INTO users (user_id, username, full_name, joined_at, step, is_active)
        VALUES (?, ?, ?, ?, 'ask_email', 1)
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

def calculate_start_date():
    """Start date: next weekday. If today is Fri/Sat/Sun → Monday"""
    today = date.today()
    weekday = today.weekday()  # 0=Mon, 5=Sat, 6=Sun
    if weekday == 4:   # Friday
        delta = 3
    elif weekday == 5: # Saturday
        delta = 2
    elif weekday == 6: # Sunday
        delta = 1
    else:
        delta = 1  # Mon-Thu → next day
    return today + timedelta(days=delta)

def set_membership(user_id, plan):
    start = calculate_start_date()
    days = MEMBERSHIP_DAYS.get(plan)
    if days is None:
        expiry = None  # Lifetime
    else:
        expiry = (start + timedelta(days=days)).strftime("%Y-%m-%d")

    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE users
        SET membership = ?, start_date = ?, expiry_date = ?, step = 'done', is_active = 1
        WHERE user_id = ?
    """, (plan, start.strftime("%Y-%m-%d"), expiry, user_id))
    conn.commit()
    conn.close()
    return start.strftime("%Y-%m-%d"), expiry

def set_expiry_manual(user_id, days):
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
    c.execute("SELECT user_id, username, full_name, email, membership, start_date, expiry_date, is_active FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def get_expired_today():
    today = date.today().strftime("%Y-%m-%d")
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, full_name, membership
        FROM users
        WHERE expiry_date = ? AND is_active = 1
    """, (today,))
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

    if existing and existing[9] == 'done':
        await update.message.reply_text(
            f"👋 Welcome back, {user.first_name}!\n\n"
            "You're already registered.\n"
            "Use /status to check your membership."
        )
        return

    upsert_user(user.id, user.username or "", user.full_name or "")
    await update.message.reply_text(
        f"👋 Hello! Welcome to *Wave Kani Premium Trading* 📊\n\n"
        "I'm glad to have you here!\n\n"
        "📧 Please share your *email address* to get started:",
        parse_mode="Markdown"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("❌ You're not registered yet. Please type /start")
        return

    is_active = user[8]
    membership = user[4] or "Not set"
    expiry = user[7]

    if is_active:
        if expiry:
            exp_text = f"📅 Expires on: {expiry}"
        else:
            exp_text = "♾️ Lifetime membership — never expires"
        await update.message.reply_text(
            f"✅ Your subscription is active\n"
            f"📋 Plan: {membership}\n"
            f"{exp_text}"
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
        "/status — Check your membership\n"
        "/contact — Message the admin",
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
    await update.message.reply_text("✅ Your message has been sent.")

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
        f"👑 *Admin Panel*\n👥 Active subscribers: *{total}*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        # Handle membership selection by user
        if query.data.startswith("membership_"):
            await handle_membership_selection(query, context)
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
        await query.edit_message_text("📢 Send the message to broadcast to all subscribers:")

    elif data == "list_users":
        users = get_all_users()
        if not users:
            await query.edit_message_text("No subscribers yet.")
            return
        text = "👥 *Subscribers List:*\n\n"
        for u in users[:20]:
            icon = "✅" if u[7] == 1 else "❌"
            exp = u[6] if u[6] else "♾️ Lifetime"
            text += f"{icon} {u[2]} | `{u[0]}`\n    Plan: {u[4] or 'N/A'} | Exp: {exp}\n\n"
        if len(users) > 20:
            text += f"...and {len(users)-20} more"
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "set_expiry":
        context.user_data["action"] = "set_expiry"
        await query.edit_message_text(
            "➕ Send: `USER_ID NUMBER_OF_DAYS`\n\nExample: `123456789 30`",
            parse_mode="Markdown"
        )

    elif data == "deactivate":
        context.user_data["action"] = "deactivate"
        await query.edit_message_text("🚫 Send the user ID to deactivate:")

    elif data.startswith("membership_"):
        await handle_membership_selection(query, context)

async def handle_membership_selection(query, context):
    plan = query.data.replace("membership_", "")
    user_id = query.from_user.id
    user = query.from_user

    start_d, expiry = set_membership(user_id, plan)

    if expiry:
        exp_text = f"📅 Expires on: *{expiry}*"
    else:
        exp_text = "♾️ *Lifetime — never expires*"

    await query.edit_message_text(
        f"✅ Membership confirmed!\n\n"
        f"📋 Plan: *{plan}*\n"
        f"🗓 Starts: *{start_d}*\n"
        f"{exp_text}\n\n"
        f"Sending your welcome package... 📦",
        parse_mode="Markdown"
    )

    await send_welcome_package_by_id(context.bot, user_id)

    # Notify admin
    db_user = get_user(user_id)
    email = db_user[3] if db_user else "N/A"
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 *New Subscriber!*\n\n"
        f"Name: {user.full_name}\n"
        f"Username: @{user.username or 'none'}\n"
        f"ID: `{user_id}`\n"
        f"Email: {email}\n"
        f"Plan: *{plan}*\n"
        f"Starts: {start_d}\n"
        f"Expires: {expiry or 'Lifetime'}\n\n"
        f"Total active: {count_active()}",
        parse_mode="Markdown"
    )

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
            await context.bot.send_message(uid, msg)
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
        await context.bot.send_message(int(target_id), msg)
        await update.message.reply_text("✅ Sent.")
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
    expiry = set_expiry_manual(user_id, days)
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
    await update.message.reply_text(f"✅ User {user_id} deactivated.")
    try:
        await context.bot.send_message(user_id, "❌ Your subscription has been deactivated. Please contact the admin.")
    except:
        pass

# ========================================
# 💬 MESSAGE HANDLER
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
                    await context.bot.send_message(uid, text)
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
                expiry = set_expiry_manual(uid, days)
                context.user_data.pop("action", None)
                await update.message.reply_text(f"✅ Renewed until: {expiry}")
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

        # Admin typed freely — no action pending, just ignore
        await update.message.reply_text("ℹ️ No active action. Use /admin panel or /reply USER_ID message")
        return

    # USER registration flow
    db_user = get_user(user.id)
    if not db_user:
        await update.message.reply_text("Please type /start to register.")
        return

    step = db_user[9]

    # Forward messages from registered users to admin
    if step == "done":
        username = user.username or "no username"
        keyboard = [[InlineKeyboardButton(
            f"💬 Reply to {user.first_name}",
            url=f"tg://user?id={user.id}"
        )]]
        await context.bot.send_message(
            ADMIN_ID,
            f"📩 *{user.full_name}* (@{username}) | `{user.id}`:\n\n{text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if step == "ask_email":
        set_email(user.id, text)
        keyboard = [
            [InlineKeyboardButton("📅 3 Months — $299", callback_data="membership_3 Months")],
            [InlineKeyboardButton("📅 6 Months — $499", callback_data="membership_6 Months")],
            [InlineKeyboardButton("📅 1 Year — $799", callback_data="membership_1 Year")],
            [InlineKeyboardButton("♾️ Lifetime — $2,199", callback_data="membership_Lifetime")],
        ]
        await update.message.reply_text(
            "✅ Email saved!\n\n📋 Please select your *membership period*:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif step == "ask_membership":
        start_d, expiry = set_membership(user.id, text)
        await send_welcome_package_by_id(context.bot, user.id)

# ========================================
# 📦 WELCOME PACKAGE
# ========================================
async def send_welcome_package_by_id(bot, user_id):
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
    expired = get_expired_today()
    for user_id, full_name, membership in expired:
        try:
            await context.bot.send_message(
                user_id,
                RENEWAL_MESSAGE,
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 *Membership expired today:*\n"
                f"Name: {full_name}\n"
                f"ID: `{user_id}`\n"
                f"Plan: {membership}\n"
                f"Renewal message sent ✅",
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("reply", reply_cmd))
    app.add_handler(CommandHandler("setexpiry", setexpiry_cmd))
    app.add_handler(CommandHandler("deactivate", deactivate_cmd))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Daily check at 9AM for expired memberships
    from datetime import time as dtime
    app.job_queue.run_daily(check_expiry, time=dtime(9, 0))

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
