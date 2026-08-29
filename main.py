import asyncio
import random
import string
import aiosqlite

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)

# ================= تنظیمات =================

TOKEN = "8957787512:AAH1rj3cHk7xCtGxE90gocPWDUyPGVhHzpY"
ADMIN_ID = 8837001390

DB = "bot.db"

bot = Bot(TOKEN)
dp = Dispatcher()


# ================= دیتابیس =================

async def db_init():
    async with aiosqlite.connect(DB) as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            username TEXT,
            active INTEGER DEFAULT 0,
            files INTEGER DEFAULT 0
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS codes(
            code TEXT PRIMARY KEY
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS files(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_id TEXT
        )
        """)

        await db.commit()



async def add_user(user_id, username):

    async with aiosqlite.connect(DB) as db:

        await db.execute(
            "INSERT OR IGNORE INTO users(id,username) VALUES(?,?)",
            (user_id, username)
        )

        await db.commit()



async def is_active(user_id):

    async with aiosqlite.connect(DB) as db:

        cur = await db.execute(
            "SELECT active FROM users WHERE id=?",
            (user_id,)
        )

        r = await cur.fetchone()

        return r and r[0] == 1



async def activate(user_id):

    async with aiosqlite.connect(DB) as db:

        await db.execute(
            "UPDATE users SET active=1 WHERE id=?",
            (user_id,)
        )

        await db.commit()



async def make_code():

    code = ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for _ in range(8)
    )

    async with aiosqlite.connect(DB) as db:

        await db.execute(
            "INSERT INTO codes VALUES(?)",
            (code,)
        )

        await db.commit()

    return code



async def check_code(code):

    async with aiosqlite.connect(DB) as db:

        cur = await db.execute(
            "SELECT * FROM codes WHERE code=?",
            (code,)
        )

        r = await cur.fetchone()

        if r:

            await db.execute(
                "DELETE FROM codes WHERE code=?",
                (code,)
            )

            await db.commit()

            return True

        return False



async def save_file(user_id,file_id):

    async with aiosqlite.connect(DB) as db:

        await db.execute(
            "INSERT INTO files(user_id,file_id) VALUES(?,?)",
            (user_id,file_id)
        )

        await db.execute(
            "UPDATE users SET files=files+1 WHERE id=?",
            (user_id,)
        )

        await db.commit()



async def user_info(user_id):

    async with aiosqlite.connect(DB) as db:

        cur = await db.execute(
            "SELECT files FROM users WHERE id=?",
            (user_id,)
        )

        return await cur.fetchone()



async def stats():

    async with aiosqlite.connect(DB) as db:

        users = await db.execute(
            "SELECT COUNT(*) FROM users"
        )

        files = await db.execute(
            "SELECT COUNT(*) FROM files"
        )

        return (
            (await users.fetchone())[0],
            (await files.fetchone())[0]
        )


# ================= منوها =================


user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📤 ارسال فایل"),
            KeyboardButton(text="👤 حساب کاربری")
        ],
        [
            KeyboardButton(text="ℹ️ درباره")
        ]
    ],
    resize_keyboard=True
)


admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🔑 ساخت کد ورود"),
            KeyboardButton(text="📊 آمار")
        ],
        [
            KeyboardButton(text="📤 ارسال فایل")
        ]
    ],
    resize_keyboard=True
)



# ================= هندلرها =================


@dp.message(Command("start"))
async def start(message:types.Message):

    await add_user(
        message.from_user.id,
        message.from_user.username
    )

    if message.from_user.id == ADMIN_ID:

        await message.answer(
            "پنل مدیریت",
            reply_markup=admin_menu
        )

    elif await is_active(message.from_user.id):

        await message.answer(
            "خوش آمدید",
            reply_markup=user_menu
        )

    else:

        await message.answer(
            "🔐 کد ورود خود را ارسال کنید"
        )



@dp.message()
async def messages(message:types.Message):

    uid = message.from_user.id


    # ساخت کد ادمین

    if message.text == "🔑 ساخت کد ورود" and uid == ADMIN_ID:

        code = await make_code()

        await message.answer(
            f"کد ساخته شد:\n\n{code}"
        )



    # آمار

    elif message.text == "📊 آمار" and uid == ADMIN_ID:

        u,f = await stats()

        await message.answer(
            f"👥 کاربران: {u}\n📁 فایل‌ها: {f}"
        )



    # ورود با کد

    elif message.text:

        if await check_code(message.text):

            await activate(uid)

            await message.answer(
                "ورود موفق ✅",
                reply_markup=user_menu
            )



    # حساب کاربری

    elif message.text == "👤 حساب کاربری":

        info = await user_info(uid)

        await message.answer(
            f"📁 تعداد فایل‌ها: {info[0]}"
        )



    # درباره

    elif message.text == "ℹ️ درباره":

        await message.answer(
            "ربات آپلودر فایل"
        )



    # دریافت فایل

    elif message.document:

        if await is_active(uid):

            await save_file(
                uid,
                message.document.file_id
            )

            await message.answer(
                "فایل ذخیره شد ✅"
            )

        else:

            await message.answer(
                "ابتدا وارد شوید"
            )



# ================= اجرا =================


async def main():

    await db_init()

    await dp.start_polling(bot)



if __name__ == "__main__":
    asyncio.run(main())
