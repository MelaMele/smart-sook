import os
import asyncio
from fastapi import FastAPI, Request
from datetime import date, timedelta
from supabase import create_client, Client
from aiogram import Bot, Dispatcher, Types, F
from aiogram.types import Update, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

app = FastAPI()

# ኮንፊገሬሽን
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- ኪቦርድ ---
def get_main_menu():
    buttons = [
        [InlineKeyboardButton(text="📦 የዕቃዎች ክምችት (Stock)", callback_data="check_stock")],
        [InlineKeyboardButton(text="⚠️ ኤክስፓየር ዴት (Expiry)", callback_data="check_expiry")],
        [InlineKeyboardButton(text="💰 የቀን ሂሳብ (Finance)", callback_data="check_finance")],
        [InlineKeyboardButton(text="📝 የዱቤ መዝገብ (Credit)", callback_data="check_credit")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ቦት ሎጂክ ---
@dp.message(Command("start"))
async def send_welcome(message: Types.Message):
    await message.reply("እንኳን ወደ ስማርት ሱቅ ቦት በሰላም መጡ! 🛍️", reply_markup=get_main_menu())

@dp.callback_query(F.data == "check_stock")
async def bot_out_of_stock(callback: Types.CallbackQuery):
    await callback.message.edit_text("ክምችቱን በማረጋገጥ ላይ...", reply_markup=get_main_menu())

# --- ቨርሰል ዌብሁክ (የተስተካከለ) ---
@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    try:
        raw_json = await request.json()
        update = Update.model_validate(raw_json, context={"bot": bot})
        
        # ቨርሰል ላይ አዲስ ሉፕ ፈጥሮ ወዲያውኑ እንዲጨርስ ማድረግ
        loop = asyncio.get_event_loop()
        loop.run_until_complete(dp.feed_update(bot, update))
        
        return {"status": "ok"}
    except Exception as e:
        return {"status": "ignored", "reason": str(e)}

@app.get("/")
def read_root():
    return {"status": "active", "message": "Smart Sook API is live!"}
