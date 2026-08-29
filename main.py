import asyncio
import sqlite3
import uuid
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command, CommandStart
from aiogram.utils.deep_linking import create_start_link


# ================= CONFIG =================

TOKEN = "YOUR_BOT_TOKEN"

ADMIN_IDS = [
    123456789
]

DEFAULT_DELETE_TIME = 10


# ================= DATABASE =================

db = sqlite3.connect("bot.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS files(
    id TEXT PRIMARY KEY,
    file_id TEXT,
    name TEXT,
    delete_time INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    vip INTEGER DEFAULT 0,
    banned INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS settings(
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

db.commit()


def get_setting(key, default):
    cur.execute(
        "SELECT value FROM settings WHERE key=?",
        (key,)
    )
    r = cur.fetchone()

    if r:
        return r[0]

    cur.execute(
        "INSERT INTO settings VALUES (?,?)",
        (key, str(default))
    )
    db.commit()

    return default


def set_setting(key, value):
    cur.execute(
        """
        INSERT INTO settings(key,value)
        VALUES(?,?)
        ON CONFLICT(key)
        DO UPDATE SET value=excluded.value
        """,
        (key, str(value))
    )
    db.commit()


# ================= BOT =================

bot = Bot(TOKEN)

dp = Dispatcher()


def is_admin(uid):
    return uid in ADMIN_IDS


def add_user(uid):
    cur.execute(
        "INSERT OR IGNORE INTO users(id) VALUES(?)",
        (uid,)
    )
    db.commit()


def is_vip(uid):
    cur.execute(
        "SELECT vip FROM users WHERE id=?",
        (uid,)
    )
    r = cur.fetchone()

    return r and r[0] == 1


# ================= START =================


@dp.message(CommandStart())
async def start(message: Message):

    add_user(message.from_user.id)

    args = message.text.split()

    if len(args) > 1:

        file_id = args[1]

        cur.execute(
            "SELECT file_id,name,delete_time FROM files WHERE id=?",
            (file_id,)
        )

        data = cur.fetchone()

        if not data:
            await message.answer(
                "❌ فایل پیدا نشد یا حذف شده"
            )
            return


        tg_file,name,delete_time = data


        sent = await message.answer_document(
            tg_file,
            caption=name
        )


        await asyncio.sleep(
            int(delete_time)
        )


        try:
            await sent.delete()
        except:
            pass


        return


    await message.answer(
        "سلام 👋\n"
        "به ربات آپلودر خوش آمدید."
    )


# ================= ADMIN UPLOAD =================


@dp.message(F.document)
async def upload(message: Message):

    if not is_admin(message.from_user.id):
        return


    file = message.document

    fid = str(uuid.uuid4())[:10]

    delete_time = int(
        get_setting(
            "delete_time",
            DEFAULT_DELETE_TIME
        )
    )


    cur.execute(
        """
        INSERT INTO files
        VALUES(?,?,?,?)
        """,
        (
            fid,
            file.file_id,
            file.file_name,
            delete_time
        )
    )

    db.commit()


    link = await create_start_link(
        bot,
        fid
    )


    await message.answer(
        f"✅ فایل ذخیره شد\n\n"
        f"🔗 لینک:\n{link}\n\n"
        f"⏱ حذف بعد از: {delete_time} ثانیه"
    )


# ادامه در بخش ۲...
# ================= ADMIN PANEL =================


@dp.message(Command("admin"))
async def admin_panel(message: Message):

    if not is_admin(message.from_user.id):
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚙️ تنظیم زمان حذف فایل",
                    callback_data="set_time"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 آمار کاربران",
                    callback_data="stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ VIP کردن کاربر",
                    callback_data="vip_help"
                )
            ]
        ]
    )

    await message.answer(
        "🔐 پنل مدیریت",
        reply_markup=keyboard
    )



@dp.callback_query(F.data == "stats")
async def stats(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    users = cur.fetchone()[0]


    cur.execute(
        "SELECT COUNT(*) FROM files"
    )

    files = cur.fetchone()[0]


    await call.message.answer(
        f"""
📊 آمار ربات

👤 کاربران:
{users}

📁 فایل‌ها:
{files}
"""
    )



@dp.callback_query(F.data == "set_time")
async def set_time_help(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return


    await call.message.answer(
        "برای تغییر زمان حذف ارسال کن:\n\n"
        "/time 30\n\n"
        "یعنی حذف فایل بعد از ۳۰ ثانیه"
    )



@dp.message(Command("time"))
async def change_time(message: Message):

    if not is_admin(message.from_user.id):
        return


    try:
        sec = int(
            message.text.split()[1]
        )

    except:
        await message.answer(
            "فرمت صحیح:\n/time 20"
        )
        return


    set_setting(
        "delete_time",
        sec
    )


    await message.answer(
        f"✅ زمان حذف روی {sec} ثانیه تنظیم شد"
    )



# ================= VIP SYSTEM =================


@dp.message(Command("vip"))
async def vip_user(message: Message):

    if not is_admin(message.from_user.id):
        return


    try:

        uid = int(
            message.text.split()[1]
        )

    except:

        await message.answer(
            "استفاده:\n/vip USER_ID"
        )
        return


    cur.execute(
        """
        INSERT INTO users(id,vip)
        VALUES(?,1)
        ON CONFLICT(id)
        DO UPDATE SET vip=1
        """,
        (uid,)
    )

    db.commit()


    await message.answer(
        "⭐ کاربر VIP شد"
    )



@dp.message(Command("unvip"))
async def remove_vip(message: Message):

    if not is_admin(message.from_user.id):
        return


    try:

        uid = int(
            message.text.split()[1]
        )

    except:

        await message.answer(
            "استفاده:\n/unvip USER_ID"
        )
        return


    cur.execute(
        "UPDATE users SET vip=0 WHERE id=?",
        (uid,)
    )

    db.commit()


    await message.answer(
        "❌ VIP حذف شد"
    )



# ================= BAN SYSTEM =================


@dp.message(Command("ban"))
async def ban(message: Message):

    if not is_admin(message.from_user.id):
        return


    try:
        uid = int(
            message.text.split()[1]
        )

    except:
        return


    cur.execute(
        "UPDATE users SET banned=1 WHERE id=?",
        (uid,)
    )

    db.commit()


    await message.answer(
        "🚫 کاربر مسدود شد"
    )



@dp.message(Command("unban"))
async def unban(message: Message):

    if not is_admin(message.from_user.id):
        return


    try:
        uid = int(
            message.text.split()[1]
        )

    except:
        return


    cur.execute(
        "UPDATE users SET banned=0 WHERE id=?",
        (uid,)
    )

    db.commit()


    await message.answer(
        "✅ کاربر آزاد شد"
    )



# ادامه در بخش ۳/۴...
# ================= USER CHECK =================


@dp.message()
async def check_user(message: Message):

    add_user(message.from_user.id)

    cur.execute(
        "SELECT banned FROM users WHERE id=?",
        (message.from_user.id,)
    )

    user = cur.fetchone()

    if user and user[0] == 1:

        await message.answer(
            "🚫 شما از استفاده از ربات محروم شده‌اید."
        )

        return



# ================= VIP GIFT =================


@dp.message(Command("giftvip"))
async def gift_vip(message: Message):

    if not is_admin(message.from_user.id):
        return


    args = message.text.split()


    if len(args) < 2:

        await message.answer(
            "استفاده:\n"
            "/giftvip USER_ID"
        )

        return


    try:

        uid = int(args[1])

    except:

        return



    cur.execute(
        """
        INSERT INTO users(id,vip)
        VALUES(?,1)
        ON CONFLICT(id)
        DO UPDATE SET vip=1
        """,
        (uid,)
    )

    db.commit()


    await message.answer(
        "🎁 VIP هدیه داده شد"
    )


    try:

        await bot.send_message(
            uid,
            "🎉 شما VIP شدید!"
        )

    except:

        pass



# ================= BROADCAST =================


@dp.message(Command("broadcast"))
async def broadcast(message: Message):

    if not is_admin(message.from_user.id):
        return


    text = message.text.replace(
        "/broadcast",
        ""
    ).strip()


    if not text:

        await message.answer(
            "متن پیام را وارد کنید"
        )

        return



    cur.execute(
        "SELECT id FROM users"
    )

    users = cur.fetchall()


    count = 0


    for user in users:

        try:

            await bot.send_message(
                user[0],
                text
            )

            count += 1

            await asyncio.sleep(
                0.05
            )

        except:

            pass



    await message.answer(
        f"✅ ارسال شد\n"
        f"تعداد: {count}"
    )



# ================= FILE INFO =================


@dp.message(Command("files"))
async def files_list(message: Message):

    if not is_admin(message.from_user.id):
        return


    cur.execute(
        """
        SELECT id,name
        FROM files
        LIMIT 20
        """
    )

    rows = cur.fetchall()


    if not rows:

        await message.answer(
            "فایلی وجود ندارد"
        )

        return



    text = "📁 فایل‌ها:\n\n"


    for r in rows:

        text += (
            f"🆔 {r[0]}\n"
            f"📄 {r[1]}\n\n"
        )


    await message.answer(text)



# ================= DELETE FILE =================


@dp.message(Command("delfile"))
async def delete_file(message: Message):

    if not is_admin(message.from_user.id):
        return


    try:

        fid = message.text.split()[1]

    except:

        await message.answer(
            "استفاده:\n/delfile FILE_ID"
        )

        return



    cur.execute(
        "DELETE FROM files WHERE id=?",
        (fid,)
    )

    db.commit()


    await message.answer(
        "🗑 فایل حذف شد"
    )



# ================= VIP CHECK =================


@dp.message(Command("myvip"))
async def myvip(message: Message):

    if is_vip(message.from_user.id):

        await message.answer(
            "⭐ شما VIP هستید"
        )

    else:

        await message.answer(
            "❌ شما VIP نیستید"
        )



# ================= START BOT =================
# ================= RUN =================


async def main():

    print(
        "Bot Started..."
    )

    await dp.start_polling(
        bot
    )



if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "Bot Stopped"
        )
