import os
import json
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from datetime import date, timedelta
from supabase import create_client, Client
from aiogram import Bot, Dispatcher, Types
from aiogram.types import Update

app = FastAPI(title="Smart Sook Cloud API")

# --- ENV VARIABLES (በVercel ላይ የሚሞሉ) ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ክላየንቶች
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- 1. የቴሌግራም ቦት ሎጂክ (AIOGRAM) ---

@dp.message(commands=['start'])
async def send_welcome(message: Types.Message):
    await message.reply(
        "እንኳን ወደ ስማርት ሱቅ ቦት በሰላም መጡ! 🛍️\n\n"
        "የአገልግሎት ጊዜ ያለፈባቸውን ዕቃዎች ለማየት: /expiry\n"
        "ያለቁ ዕቃዎችን ለማየት: /stock"
    )

@dp.message(commands=['expiry'])
async def bot_check_expiry(message: Types.Message):
    today = date.today()
    warning_date = today + timedelta(days=30)
    
    data = supabase.table("products")\
        .select("name, expiry_date")\
        .lte("expiry_date", str(warning_date))\
        .gte("expiry_date", str(today))\
        .execute()
    
    if not data.data:
        await message.reply("በሚቀጥሉት 30 ቀናት ውስጥ ኤክስፓየር የሚሆን ዕቃ የለም። ✅")
        return
        
    response = "⚠️ **ኤክስፓየር ሊሆኑ የቀረቡ ዕቃዎች:**\n"
    for item in data.data:
        response += f"• {item['name']} - ቀን: {item['expiry_date']}\n"
    await message.reply(response, parse_mode="Markdown")

@dp.message(commands=['stock'])
async def bot_out_of_stock(message: Types.Message):
    data = supabase.table("products").select("name, quantity").lte("quantity", 5).execute()
    
    if not data.data:
        await message.reply("ክምችቱ አስተማማኝ ነው፣ ያለቀ ዕቃ የለም። ✅")
        return
        
    response = "🚨 **ያለቁ ወይም ሊያልቁ የተቃረቡ ዕቃዎች:**\n"
    for item in data.data:
        response += f"• {item['name']} - የቀረው ብዛት: {item['quantity']}\n"
    await message.reply(response, parse_mode="Markdown")

# --- 2. VERCEL WEBHOOK ENDPOINT ---

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    """ ቴሌግራም መልክቶችን በቀጥታ ወደ ቨርሰል የሚልክበት ዌብሁክ """
    try:
        request_json = await request.json()
        update = Update.model_validate(request_json, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
