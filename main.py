import asyncio
import sqlite3
import secrets
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8957787512:AAER4M-9nWKBU0RUtVXQP71DFJddehupgUI"
ADMIN_ID = 8837001390

bot = Bot(TOKEN)
dp = Dispatcher()

db = sqlite3.connect("bot.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS files(
token TEXT,
file_id TEXT,
expire INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER,
vip INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS settings(
expire INTEGER
)
""")

db.commit()


# زمان پیشفرض حذف
cur.execute("SELECT * FROM settings")
if not cur.fetchone():
    cur.execute("INSERT INTO settings VALUES(10)")
    db.commit()


@dp.message(Command("start"))
async def start(message: types.Message):

    args = message.text.split()

    if len(args) > 1:
        token = args[1].replace("file_", "")

        cur.execute(
            "SELECT file_id,expire FROM files WHERE token=?",
            (token,)
        )

        data = cur.fetchone()

        if data:

            file_id, expire = data

            msg = await message.answer_document(
                file_id
            )

            await asyncio.sleep(expire)

            try:
                await msg.delete()
            except:
                pass

            return

    await message.answer(
        "سلام، ربات آپلودر فعال است."
    )


@dp.message(Command("panel"))
async def panel(message: types.Message):

    if message.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚙ تنظیم زمان حذف",
                    callback_data="time"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 آمار",
                    callback_data="stats"
                )
            ]
        ]
    )

    await message.answer(
        "پنل مدیریت",
        reply_markup=kb
    )


@dp.message(
    lambda m:
    m.from_user.id == ADMIN_ID
    and m.document
)
async def upload(message: types.Message):

    cur.execute(
        "SELECT expire FROM settings"
    )

    expire = cur.fetchone()[0]

    token = secrets.token_urlsafe(8)

    cur.execute(
        "INSERT INTO files VALUES(?,?,?)",
        (
            token,
            message.document.file_id,
            expire
        )
    )

    db.commit()

    link = (
        f"https://t.me/"
        f"{(await bot.me()).username}"
        f"?start=file_{token}"
    )

    await message.answer(
        f"✅ لینک ساخته شد:\n\n{link}\n\n"
        f"حذف بعد از {expire} ثانیه"
    )


@dp.callback_query(lambda c:c.data=="stats")
async def stats(call):

    if call.from_user.id != ADMIN_ID:
        return

    cur.execute(
        "SELECT COUNT(*) FROM files"
    )

    count = cur.fetchone()[0]

    await call.message.answer(
        f"📁 تعداد فایل‌ها: {count}"
    )


async def main():
    await dp.start_polling(bot)


if __name__=="__main__":
    asyncio.run(main())
