import os
import json
from fastapi import FastAPI, Request, HTTPException
from datetime import date, timedelta
from supabase import create_client, Client
from aiogram import Bot, Dispatcher, Types, F
from aiogram.types import Update, InlineKeyboardMarkup, InlineKeyboardButton

app = FastAPI(title="Smart Sook Cloud API")

# ኮንፊገሬሽን
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- ኪቦርዶች (KEYBOARDS) ---

def get_main_menu():
    """ ለባለሱቁ ዋና ማውጫ ባተኖችን መፍጠሪያ """
    buttons = [
        [InlineKeyboardButton(text="📦 የዕቃዎች ክምችት (Stock)", callback_data="check_stock")],
        [InlineKeyboardButton(text="⚠️ ኤክስፓየር ዴት (Expiry)", callback_data="check_expiry")],
        [InlineKeyboardButton(text="💰 የቀን ሂሳብ (Finance)", callback_data="check_finance")],
        [InlineKeyboardButton(text="📝 የዱቤ መዝገብ (Credit)", callback_data="check_credit")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- 1. የቴሌግራም ቦት ሎጂክ ---

@dp.message(F.text == "/start")
async def send_welcome(message: Types.Message):
    await message.reply(
        "እንኳን ወደ ስማርት ሱቅ ማስተዳደሪያ ቦት በሰላም መጡ! 🛍️\n\n"
        "ለመጠቀም ከታች ያሉትን አማራጮች ይጫኑ፦",
        reply_markup=get_main_menu()
    )

# --- BUTTON HANDLERS (የባተኖች ምላሽ) ---

@dp.callback_query(F.data == "check_expiry")
async def bot_check_expiry(callback: Types.CallbackQuery):
    today = date.today()
    warning_date = today + timedelta(days=30)
    
    data = supabase.table("products")\
        .select("name, expiry_date")\
        .lte("expiry_date", str(warning_date))\
        .gte("expiry_date", str(today))\
        .execute()
    
    if not data.data:
        await callback.message.edit_text("በሚቀጥሉት 30 ቀናት ውስጥ ኤክስፓየር የሚሆን ዕቃ የለም። ✅", reply_markup=get_main_menu())
        return
        
    response = "⚠️ **ኤክስፓየር ሊሆኑ የቀረቡ ዕቃዎች:**\n\n"
    for item in data.data:
        response += f"• {item['name']} - ቀን: {item['expiry_date']}\n"
    
    await callback.message.edit_text(response, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.callback_query(F.data == "check_stock")
async def bot_out_of_stock(callback: Types.CallbackQuery):
    data = supabase.table("products").select("name, quantity").lte("quantity", 5).execute()
    
    if not data.data:
        await callback.message.edit_text("ክምችቱ አስተማማኝ ነው፣ ያለቀ ዕቃ የለም። ✅", reply_markup=get_main_menu())
        return
        
    response = "🚨 **ያለቁ ወይም ሊያልቁ የተቃረቡ ዕቃዎች:**\n\n"
    for item in data.data:
        response += f"• {item['name']} - የቀረው ብዛት: {item['quantity']}\n"
        
    await callback.message.edit_text(response, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.callback_query(F.data == "check_credit")
async def bot_check_credit(callback: Types.CallbackQuery):
    data = supabase.table("customers_credit").select("customer_name, total_debt").gt("total_debt", 0).execute()
    
    if not data.data:
        await callback.message.edit_text("በአሁኑ ሰዓት ምንም የዱቤ ዕዳ ያለበት ደንበኛ የለም። 🕊️", reply_markup=get_main_menu())
        return
        
    response = "📝 **የዱቤ መዝገብ (ባለዕዳዎች):**\n\n"
    for customer in data.data:
        response += f"• {customer['customer_name']} - ዕዳ: {customer['total_debt']} ብር\n"
        
    await callback.message.edit_text(response, parse_mode="Markdown", reply_markup=get_main_menu())

# --- 2. VERCEL WEBHOOK ENDPOINT ---

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    try:
        request_json = await request.json()
        update = Update.model_validate(request_json, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
