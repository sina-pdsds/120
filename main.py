import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = "8957787512:AAGCSkFyh1plc9GLbXIno-wJTwqjLlEv0"

# آیدی عددی ادمین‌ها
ADMIN_IDS = {
    8837001390,
}

DB_NAME = "uploader.db"

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

FORCE_CHANNEL = ""
# مثال:
# FORCE_CHANNEL = "@YourChannel"


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("UploaderBot")


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(DB_NAME, check_same_thread=False)
db.row_factory = sqlite3.Row


def init_db():
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            points INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            vip_until TEXT,
            is_banned INTEGER DEFAULT 0,
            uploads INTEGER DEFAULT 0,
            downloads INTEGER DEFAULT 0,
            joined_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_id TEXT,
            file_unique_id TEXT,
            file_name TEXT,
            file_size INTEGER DEFAULT 0,
            file_type TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            created_at TEXT
        )
    """)

    db.commit()


def add_user(user_id, username, full_name):
    cursor = db.cursor()

    cursor.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,)
    )

    if cursor.fetchone() is None:
        cursor.execute("""
            INSERT INTO users
            (user_id, username, full_name, joined_at)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            username or "",
            full_name or "",
            datetime.now().isoformat(),
        ))
        db.commit()


def get_user(user_id):
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )
    return cursor.fetchone()


def is_banned(user_id):
    user = get_user(user_id)

    if not user:
        return False

    return bool(user["is_banned"])


def is_vip(user_id):
    user = get_user(user_id)

    if not user:
        return False

    if not user["is_vip"]:
        return False

    if user["vip_until"]:
        try:
            until = datetime.fromisoformat(user["vip_until"])

            if datetime.now() > until:
                db.execute("""
                    UPDATE users
                    SET is_vip = 0, vip_until = NULL
                    WHERE user_id = ?
                """, (user_id,))
                db.commit()

                return False

        except Exception:
            pass

    return True


def add_log(user_id, action):
    db.execute("""
        INSERT INTO logs
        (user_id, action, created_at)
        VALUES (?, ?, ?)
    """, (
        user_id,
        action,
        datetime.now().isoformat(),
    ))

    db.commit()


def save_file(
    user_id,
    file_id,
    unique_id,
    file_name,
    file_size,
    file_type,
):
    db.execute("""
        INSERT INTO files
        (user_id, file_id, file_unique_id, file_name,
         file_size, file_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        file_id,
        unique_id,
        file_name,
        file_size or 0,
        file_type,
        datetime.now().isoformat(),
    ))

    db.execute("""
        UPDATE users
        SET uploads = uploads + 1
        WHERE user_id = ?
    """, (user_id,))

    db.commit()


def get_stats():
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM files")
    files = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(file_size), 0) FROM files")
    storage = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE is_vip = 1"
    )
    vip = cursor.fetchone()[0]

    return users, files, storage, vip


def get_all_users():
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM users")
    return cursor.fetchall()


# =========================================================
# HELPERS
# =========================================================

def format_size(size):
    if not size:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]

    index = 0

    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1

    return f"{size:.2f} {units[index]}"


def admin(user_id):
    return user_id in ADMIN_IDS


def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 ارسال فایل",
                    callback_data="upload"
                ),
                InlineKeyboardButton(
                    text="👤 حساب من",
                    callback_data="profile"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 آمار",
                    callback_data="stats"
                ),
                InlineKeyboardButton(
                    text="⭐ VIP",
                    callback_data="vip"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ راهنما",
                    callback_data="help"
                ),
            ],
        ]
    )


def admin_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 آمار ربات",
                    callback_data="admin_stats"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👥 کاربران",
                    callback_data="admin_users"
                ),
                InlineKeyboardButton(
                    text="📁 فایل‌ها",
                    callback_data="admin_files"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📢 Broadcast",
                    callback_data="broadcast"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⭐ مدیریت VIP",
                    callback_data="vip_manage"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 منوی اصلی",
                    callback_data="home"
                ),
            ],
        ]
    )


# =========================================================
# FSM
# =========================================================

class BroadcastState(StatesGroup):
    waiting_message = State()


class VipState(StatesGroup):
    waiting_user = State()
    waiting_days = State()


# =========================================================
# BOT
# =========================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    ),
)

dp = Dispatcher()


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: Message):

    user = message.from_user

    add_user(
        user.id,
        user.username,
        user.full_name,
    )

    if is_banned(user.id):
        await message.answer(
            "🚫 <b>حساب شما مسدود شده است.</b>"
        )
        return

    add_log(user.id, "start")

    text = (
        "🚀 <b>به ربات آپلودر خوش آمدید!</b>\n\n"
        "📤 فایل خودت رو ارسال کن تا ذخیره بشه.\n"
        "⚡ سریع و ساده\n"
        "🔐 امن\n"
        "⭐ پشتیبانی از VIP\n\n"
        "یکی از گزینه‌های زیر رو انتخاب کن:"
    )

    if admin(user.id):
        text += "\n\n👑 <b>شما ادمین هستید.</b>"

    keyboard = main_menu()

    if admin(user.id):
        keyboard.inline_keyboard.insert(
            0,
            [
                InlineKeyboardButton(
                    text="👑 پنل مدیریت",
                    callback_data="admin_panel"
                )
            ]
        )

    await message.answer(
        text,
        reply_markup=keyboard
    )


# =========================================================
# CALLBACK HOME
# =========================================================

@dp.callback_query(F.data == "home")
async def home_callback(callback: CallbackQuery):

    await callback.message.edit_text(
        "🏠 <b>منوی اصلی</b>\n\n"
        "فایل خودت رو ارسال کن یا یکی از گزینه‌ها رو انتخاب کن.",
        reply_markup=main_menu()
    )

    await callback.answer()


# =========================================================
# PROFILE
# =========================================================

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):

    user_id = callback.from_user.id
    user = get_user(user_id)

    vip_status = "فعال ⭐" if is_vip(user_id) else "غیرفعال"

    if user["vip_until"]:
        vip_until = user["vip_until"]
    else:
        vip_until = "-"

    text = (
        "👤 <b>پروفایل شما</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 نام: {user['full_name']}\n"
        f"🔹 Username: @{user['username'] or 'ندارد'}\n\n"
        f"📤 تعداد آپلود: <b>{user['uploads']}</b>\n"
        f"💎 امتیاز: <b>{user['points']}</b>\n"
        f"⭐ VIP: <b>{vip_status}</b>\n"
        f"⏰ پایان VIP: <code>{vip_until}</code>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 بازگشت",
                        callback_data="home"
                    )
                ]
            ]
        )
    )

    await callback.answer()


# =========================================================
# USER STATS
# =========================================================

@dp.callback_query(F.data == "stats")
async def user_stats(callback: CallbackQuery):

    user = get_user(callback.from_user.id)

    await callback.message.edit_text(
        "📊 <b>آمار شما</b>\n\n"
        f"📤 آپلودها: <b>{user['uploads']}</b>\n"
        f"💎 امتیاز: <b>{user['points']}</b>\n"
        f"⭐ VIP: <b>{'فعال' if is_vip(user['user_id']) else 'غیرفعال'}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 بازگشت",
                        callback_data="home"
                    )
                ]
            ]
        )
    )

    await callback.answer()


# =========================================================
# HELP
# =========================================================

@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):

    text = (
        "ℹ️ <b>راهنمای ربات</b>\n\n"
        "📤 برای آپلود، کافیست فایل خود را ارسال کنید.\n\n"
        "📦 فایل‌های زیر پشتیبانی می‌شوند:\n"
        "• Document\n"
        "• Video\n"
        "• Photo\n"
        "• Audio\n"
        "• Voice\n\n"
        "⭐ کاربران VIP محدودیت‌های بیشتری دارند."
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 بازگشت",
                        callback_data="home"
                    )
                ]
            ]
        )
    )

    await callback.answer()


# =========================================================
# VIP INFO
# =========================================================

@dp.callback_query(F.data == "vip")
async def vip_callback(callback: CallbackQuery):

    text = (
        "⭐ <b>VIP</b>\n\n"
        "امکانات VIP:\n"
        "⚡ اولویت پردازش\n"
        "📦 محدودیت بیشتر\n"
        "🚀 امکانات ویژه\n\n"
        "برای خرید VIP با پشتیبانی تماس بگیرید."
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 بازگشت",
                        callback_data="home"
                    )
                ]
            ]
        )
    )

    await callback.answer()


# =========================================================
# UPLOAD BUTTON
# =========================================================

@dp.callback_query(F.data == "upload")
async def upload_callback(callback: CallbackQuery):

    await callback.message.answer(
        "📤 <b>فایل خود را ارسال کنید.</b>\n\n"
        "ربات فایل را دریافت و در دیتابیس ثبت می‌کند."
    )

    await callback.answer()


# =========================================================
# FILE HANDLER
# =========================================================

@dp.message(
    F.content_type.in_({
        ContentType.DOCUMENT,
        ContentType.VIDEO,
        ContentType.PHOTO,
        ContentType.AUDIO,
        ContentType.VOICE,
    })
)
async def file_handler(message: Message):

    user = message.from_user

    add_user(
        user.id,
        user.username,
        user.full_name,
    )

    if is_banned(user.id):
        await message.answer(
            "🚫 <b>شما مسدود هستید.</b>"
        )
        return

    file_id = None
    unique_id = None
    file_name = "file"
    file_size = 0
    file_type = message.content_type

    if message.document:

        file_id = message.document.file_id
        unique_id = message.document.file_unique_id
        file_name = message.document.file_name or "document"
        file_size = message.document.file_size or 0

    elif message.video:

        file_id = message.video.file_id
        unique_id = message.video.file_unique_id
        file_name = "video.mp4"
        file_size = message.video.file_size or 0

    elif message.photo:

        photo = message.photo[-1]

        file_id = photo.file_id
        unique_id = photo.file_unique_id
        file_name = "photo.jpg"
        file_size = photo.file_size or 0

    elif message.audio:

        file_id = message.audio.file_id
        unique_id = message.audio.file_unique_id
        file_name = message.audio.file_name or "audio"
        file_size = message.audio.file_size or 0

    elif message.voice:

        file_id = message.voice.file_id
        unique_id = message.voice.file_unique_id
        file_name = "voice.ogg"
        file_size = message.voice.file_size or 0

    if file_size > MAX_FILE_SIZE:

        await message.answer(
            "❌ <b>حجم فایل بیش از حد مجاز است.</b>\n\n"
            f"حداکثر: {format_size(MAX_FILE_SIZE)}"
        )

        return

    save_file(
        user.id,
        file_id,
        unique_id,
        file_name,
        file_size,
        file_type,
    )

    add_log(
        user.id,
        f"upload: {file_name}"
    )

    await message.answer(
        "✅ <b>فایل با موفقیت دریافت شد.</b>\n\n"
        f"📁 نام: <code>{file_name}</code>\n"
        f"📦 حجم: <b>{format_size(file_size)}</b>\n"
        f"🆔 File ID:\n<code>{file_id}</code>"
    )


# =========================================================
# ADMIN PANEL
# =========================================================

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):

    if not admin(callback.from_user.id):
        await callback.answer(
            "⛔ دسترسی ندارید.",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        "👑 <b>پنل مدیریت</b>\n\n"
        "مدیریت کامل ربات از این قسمت انجام می‌شود.",
        reply_markup=admin_menu()
    )

    await callback.answer()


# =========================================================
# ADMIN STATS
# =========================================================

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):

    if not admin(callback.from_user.id):
        return

    users, files, storage, vip = get_stats()

    text = (
        "📊 <b>آمار کلی ربات</b>\n\n"
        f"👥 کاربران: <b>{users}</b>\n"
        f"📁 فایل‌ها: <b>{files}</b>\n"
        f"💾 حجم فایل‌ها: <b>{format_size(storage)}</b>\n"
        f"⭐ کاربران VIP: <b>{vip}</b>\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=admin_menu()
    )

    await callback.answer()


# =========================================================
# ADMIN USERS
# =========================================================

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):

    if not admin(callback.from_user.id):
        return

    users, files, storage, vip = get_stats()

    rows = db.execute("""
        SELECT user_id, username, full_name,
               uploads, points, is_vip, is_banned
        FROM users
        ORDER BY joined_at DESC
        LIMIT 10
    """).fetchall()

    text = (
        f"👥 <b>کاربران</b>\n\n"
        f"تعداد کل: <b>{users}</b>\n\n"
    )

    for row in rows:

        status = "🚫" if row["is_banned"] else "🟢"
        vip_icon = "⭐" if row["is_vip"] else ""

        text += (
            f"{status} {vip_icon} "
            f"<code>{row['user_id']}</code> "
            f"{row['full_name'][:20]}\n"
            f"   📤 {row['uploads']} | 💎 {row['points']}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=admin_menu()
    )

    await callback.answer()


# =========================================================
# ADMIN FILES
# =========================================================

@dp.callback_query(F.data == "admin_files")
async def admin_files(callback: CallbackQuery):

    if not admin(callback.from_user.id):
        return

    rows = db.execute("""
        SELECT id, user_id, file_name, file_size
        FROM files
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    text = "📁 <b>آخرین فایل‌ها</b>\n\n"

    if not rows:
        text += "هیچ فایلی ثبت نشده."
    else:

        for row in rows:

            text += (
                f"🆔 #{row['id']}\n"
                f"👤 <code>{row['user_id']}</code>\n"
                f"📄 {row['file_name']}\n"
                f"📦 {format_size(row['file_size'])}\n\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=admin_menu()
    )

    await callback.answer()


# =========================================================
# BROADCAST
# =========================================================

@dp.callback_query(F.data == "broadcast")
async def broadcast_start(
    callback: CallbackQuery,
    state: FSMContext
):

    if not admin(callback.from_user.id):
        return

    await state.set_state(
        BroadcastState.waiting_message
    )

    await callback.message.answer(
        "📢 <b>پیام Broadcast را ارسال کنید.</b>\n\n"
        "هر نوع پیام متنی را می‌توانید ارسال کنید.\n"
        "برای لغو: /cancel"
    )

    await callback.answer()


@dp.message(
    BroadcastState.waiting_message
)
async def broadcast_message(
    message: Message,
    state: FSMContext
):

    if not admin(message.from_user.id):
        return

    users = get_all_users()

    sent = 0
    failed = 0

    status_message = await message.answer(
        "📢 شروع ارسال..."
    )

    for row in users:

        try:

            await bot.copy_message(
                chat_id=row["user_id"],
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )

            sent += 1

        except (
            TelegramForbiddenError,
            TelegramBadRequest
        ):

            failed += 1

        await asyncio.sleep(0.04)

    await status_message.edit_text(
        "✅ <b>Broadcast تمام شد.</b>\n\n"
        f"📨 ارسال موفق: <b>{sent}</b>\n"
        f"❌ ناموفق: <b>{failed}</b>"
    )

    await state.clear()


# =========================================================
# VIP MANAGEMENT
# =========================================================

@dp.callback_query(F.data == "vip_manage")
async def vip_manage(
    callback: CallbackQuery,
    state: FSMContext
):

    if not admin(callback.from_user.id):
        return

    await state.set_state(
        VipState.waiting_user
    )

    await callback.message.answer(
        "⭐ <b>مدیریت VIP</b>\n\n"
        "آیدی عددی کاربر را ارسال کنید:"
    )

    await callback.answer()


@dp.message(VipState.waiting_user)
async def vip_user(
    message: Message,
    state: FSMContext
):

    if not admin(message.from_user.id):
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:

        await message.answer(
            "❌ آیدی باید عددی باشد."
        )
        return

    user = get_user(user_id)

    if not user:

        await message.answer(
            "❌ کاربر پیدا نشد."
        )

        await state.clear()
        return

    await state.update_data(
        vip_user_id=user_id
    )

    await state.set_state(
        VipState.waiting_days
    )

    await message.answer(
        "⏰ تعداد روز VIP را ارسال کنید.\n\n"
        "مثال:\n"
        "<code>30</code>"
    )


@dp.message(VipState.waiting_days)
async def vip_days(
    message: Message,
    state: FSMContext
):

    if not admin(message.from_user.id):
        return

    try:
        days = int(message.text.strip())

        if days <= 0:
            raise ValueError

    except ValueError:

        await message.answer(
            "❌ تعداد روز معتبر نیست."
        )
        return

    data = await state.get_data()

    user_id = data["vip_user_id"]

    until = datetime.now() + timedelta(days=days)

    db.execute("""
        UPDATE users
        SET is_vip = 1,
            vip_until = ?
        WHERE user_id = ?
    """, (
        until.isoformat(),
        user_id,
    ))

    db.commit()

    add_log(
        message.from_user.id,
        f"VIP {user_id} for {days} days"
    )

    await message.answer(
        "✅ <b>VIP فعال شد.</b>\n\n"
        f"👤 کاربر: <code>{user_id}</code>\n"
        f"⏰ مدت: <b>{days} روز</b>\n"
        f"📅 پایان: <code>{until:%Y-%m-%d %H:%M}</code>"
    )

    try:

        await bot.send_message(
            user_id,
            "⭐ <b>VIP شما فعال شد!</b>\n\n"
            f"⏰ مدت: {days} روز\n"
            f"📅 پایان: {until:%Y-%m-%d %H:%M}"
        )

    except Exception:
        pass

    await state.clear()


# =========================================================
# CANCEL
# =========================================================

@dp.message(Command("cancel"))
async def cancel_handler(
    message: Message,
    state: FSMContext
):

    await state.clear()

    await message.answer(
        "❌ عملیات لغو شد.",
        reply_markup=main_menu()
    )


# =========================================================
# ADMIN COMMAND
# =========================================================

@dp.message(Command("admin"))
async def admin_command(message: Message):

    if not admin(message.from_user.id):

        await message.answer(
            "⛔ شما ادمین نیستید."
        )
        return

    await message.answer(
        "👑 <b>پنل مدیریت</b>",
        reply_markup=admin_menu()
    )


# =========================================================
# BAN COMMAND
# =========================================================

@dp.message(Command("ban"))
async def ban_command(message: Message):

    if not admin(message.from_user.id):
        return

    args = message.text.split()

    if len(args) < 2:

        await message.answer(
            "استفاده:\n"
            "<code>/ban 123456789</code>"
        )
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ آیدی نامعتبر.")
        return

    db.execute("""
        UPDATE users
        SET is_banned = 1
        WHERE user_id = ?
    """, (user_id,))

    db.commit()

    add_log(
        message.from_user.id,
        f"ban {user_id}"
    )

    await message.answer(
        f"🚫 کاربر <code>{user_id}</code> بن شد."
    )


# =========================================================
# UNBAN COMMAND
# =========================================================

@dp.message(Command("unban"))
async def unban_command(message: Message):

    if not admin(message.from_user.id):
        return

    args = message.text.split()

    if len(args) < 2:

        await message.answer(
            "استفاده:\n"
            "<code>/unban 123456789</code>"
        )
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ آیدی نامعتبر.")
        return

    db.execute("""
        UPDATE users
        SET is_banned = 0
        WHERE user_id = ?
    """, (user_id,))

    db.commit()

    add_log(
        message.from_user.id,
        f"unban {user_id}"
    )

    await message.answer(
        f"✅ کاربر <code>{user_id}</code> آن‌بن شد."
    )


# =========================================================
# ERROR HANDLER
# =========================================================

@dp.errors()
async def errors_handler(event):

    logger.exception(
        "Unhandled error: %s",
        event.exception
    )


# =========================================================
# START BOT
# =========================================================

async def main():

    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":

        raise RuntimeError(
            "BOT_TOKEN را در کد قرار دهید."
        )

    init_db()

    logger.info("Database initialized.")
    logger.info("Bot starting...")

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(
        bot
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:

        logger.info(
            "Bot stopped."
        )

    finally:

        db.close()