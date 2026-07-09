import os
from datetime import date, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update

app = FastAPI(title="Smart Sook Cloud API")

# --- 1. CONFIGURATION & CLIENTS ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# --- 2. PYDANTIC SCHEMAS ---
class ProductCreate(BaseModel):
    name: str
    quantity: int
    barcode: str | None = None
    buying_price: float
    selling_price: float
    expiry_date: str

class TransferCreate(BaseModel):
    product_name: str
    quantity: int

class CreditCreate(BaseModel):
    customer_name: str
    total_debt: float
    phone_number: str | None = None

class FinanceCreate(BaseModel):
    type: str  # 'income' ወይም 'expense'
    amount: float
    description: str

# 🔔 አዲስ፦ የደንበኛ ትዕዛዝ መቀበያ ስኪማ
class OrderCreate(BaseModel):
    customer_name: str
    telegram_id: str
    product_name: str
    quantity: int
    note: str

# --- 3. KEYBOARD MENU ---
def get_main_menu():
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("➕ አዲስ ዕቃ / ሂሳብ መዝግብ (Mini App)", web_app=telebot.types.WebAppInfo(url="https://smart-sook.vercel.app/")))
    markup.row(
        InlineKeyboardButton("📦 የሱቅ ክምችት (Shelf)", callback_data="check_stock"),
        InlineKeyboardButton("⛨ ማከማቻ ክፍል (Store)", callback_data="check_warehouse")
    )
    markup.row(
        InlineKeyboardButton("⚠️ ኤክስፓየር (Expiry)", callback_data="check_expiry"),
        InlineKeyboardButton("📝 የዱቤ መዝገብ (Credit)", callback_data="check_credit")
    )
    markup.row(InlineKeyboardButton("💰 የዛሬ የቀን ሂሳብ ሪፖርት (Finance)", callback_data="check_finance"))
    # 🔔 አዲስ፦ ለደንበኞች ብቻ የሚሆን ልዩ የትዕዛዝ ማቅረቢያ አዝራር
    markup.row(InlineKeyboardButton("🛍️ የደንበኞች ገጽ (Order & Debt)", web_app=telebot.types.WebAppInfo(url="https://smart-sook.vercel.app/customer")))
    return markup

# --- 4. TELEGRAM BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "እንኳን ወደ ስማርት ሱቅ ማስተዳደሪያ ቦት በሰላም መጡ! 🛍️\n\nለመጠቀም ከታች ያሉትን አማራጮች ይጫኑ፦", 
        reply_markup=get_main_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data == "check_stock")
def bot_check_stock(call):
    try:
        data = supabase.table("products").select("name, quantity").execute()
        if not data.data:
            bot.edit_message_text("በሱቅ መደርደሪያዎች ላይ ምንም ዕቃ የለም። 🛍️", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
            return
            
        response = "📦 **የሱቅ መደርደሪያ ዕቃዎች ክምችት (Shelf)፦**\n\n"
        out_of_stock_warnings = ""
        for item in data.data:
            qty = item['quantity']
            if qty == 0:
                out_of_stock_warnings += f"❌ {item['name']} - **አልቋል!** (0)\n"
            elif qty <= 5:
                out_of_stock_warnings += f"⚠️ {item['name']} - ሊያልቅ ነው! ({qty})\n"
            else:
                response += f"• {item['name']} - ብዛት፦ {qty}\n"
        
        if out_of_stock_warnings:
            response = "🚨 **አስቸኳይ ትኩረት የሚሹ፦**\n" + out_of_stock_warnings + "\n" + response
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        bot.edit_message_text(f"የዳታቤዝ ስህተት፦ {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "check_warehouse")
def bot_check_warehouse(call):
    try:
        data = supabase.table("warehouse_stock").select("product_name, quantity, location_rack").execute()
        if not data.data:
            bot.edit_message_text("በማከማቻ ክፍሉ (Warehouse) ውስጥ ምንም ዕቃ የለም። ⛨", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
            return
            
        response = "⛨ **የማከማቻ ክፍል ዕቃዎች ዝርዝር (Store)፦**\n\n"
        for item in data.data:
            rack = f" [ክፍል: {item['location_rack']}]" if item['location_rack'] else ""
            response += f"• {item['product_name']} - ብዛት፦ {item['quantity']}{rack}\n"
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
    except Exception as e:
        bot.edit_message_text(f"የዳታቤዝ ስህተት፦ {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "check_expiry")
def bot_check_expiry(call):
    today = date.today()
    warning_date = today + timedelta(days=30)
    try:
        data = supabase.table("products").select("name, expiry_date").lte("expiry_date", str(warning_date)).gte("expiry_date", str(today)).execute()
        if not data.data:
            bot.edit_message_text("በሚቀጥሉት 30 ቀናት ውስጥ ኤክስፓየር የሚሆን ዕቃ የለም። ✅", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
            return
            
        response = "⚠️ **ኤክስፓየር ሊሆኑ የቀረቡ ዕቃዎች:**\n\n"
        for item in data.data:
            response += f"• {item['name']} - ቀን: {item['expiry_date']}\n"
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        bot.edit_message_text(f"የዳታቤዝ ስህተት፦ {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "check_credit")
def bot_check_credit(call):
    try:
        data = supabase.table("customers_credit").select("customer_name, total_debt").gt("total_debt", 0).execute()
        if not data.data:
            bot.edit_message_text("በአሁኑ ሰዓት ምንም የዱቤ ዕዳ ያለበት ደንበኛ የለም። 🕊️", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
            return
            
        response = "📝 **የዱቤ መዝገብ (ባለዕዳዎች):**\n\n"
        for customer in data.data:
            response += f"• {customer['customer_name']} - ዕዳ: {customer['total_debt']} ብር\n"
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        bot.edit_message_text(f"የዳታቤዝ ስህተት፦ {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "check_finance")
def bot_check_finance(call):
    try:
        today_str = str(date.today())
        # የዛሬ መዝገቦችን ከዳታቤዝ ማምጣት
        data = supabase.table("finance_records").select("type, amount, description").gte("created_at", f"{today_str}T00:00:00").execute()
        
        if not data.data:
            bot.edit_message_text("📊 ለዛሬ ቀን እስካሁን የተመዘገበ የገቢም ሆነ የወጪ ሂሳብ የለም።", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())
            return
            
        total_income = 0
        total_expense = 0
        details = ""
        
        for rec in data.data:
            amt = float(rec['amount'])
            if rec['type'] == 'income':
                total_income += amt
                details += f"📥 +{amt} ብር ({rec['description']})\n"
            else:
                total_expense += amt
                details += f"📤 -{amt} ብር ({rec['description']})\n"
                
        net_profit = total_income - total_expense
        profit_status = "📈 የተጣራ ትርፍ" if net_profit >= 0 else "📉 ኪሳራ"
        
        response = f"📊 **የዛሬ ዕለት የሂሳብ ማጠቃለያ ሪፖርት ({today_str})**\n"
        response += f"----------------------------------------\n"
        response += f"📥 ጠቅላላ ገቢ፦ **{total_income:.2f} ብር**\n"
        response += f"📤 ጠቅላላ ወጪ፦ **{total_expense:.2f} ብር**\n"
        response += f"----------------------------------------\n"
        response += f"{profit_status}፦ **{abs(net_profit):.2f} ብር**\n\n"
        response += f"📋 **ዝርዝር እንቅስቃሴዎች፦**\n{details}"
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        bot.edit_message_text(f"የዳታቤዝ ስህተት፦ {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu())

# --- 5. FASTAPI ROUTES (WEBHOOK & FRONTEND) ---
@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open("api/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h3>index.html ፋይል በ api/ ፎልደር ውስጥ አልተገኘም!</h3>"

# 🔔 አዲስ፦ የደንበኞችን የፊት ገጽ መክፈቻ መስመር
@app.get("/customer", response_class=HTMLResponse)
def read_customer_root():
    try:
        with open("api/customer.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h3>customer.html ፋይል በ api/ ፎልደር ውስጥ አልተገኘም!</h3>"

# 🔔 አዲስ፦ ደንበኞች የራሳቸውን የዱቤ ዕዳ የሚፈልጉበት ኤንድፖይንት
@app.get("/api/customer/debt")
def get_customer_debt(name: str):
    try:
        data = supabase.table("customers_credit").select("total_debt").eq("customer_name", name).execute()
        debt = data.data[0]['total_debt'] if data.data else 0.0
        return {"status": "success", "debt": debt}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 🔔 አዲስ፦ ደንበኛ ምርት ሲያዝዝ ለባለሱቁ በቴሌግራም የሚያሳውቅ ኤንድፖይንት
@app.post("/api/customer/order")
def create_customer_order(order: OrderCreate):
    try:
        ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
        
        msg = f"🔔 **አዲስ የደንበኛ ትዕዛዝ ደርሷል!** 🛒\n\n"
        msg += f"👤 ደንበኛ፦ {order.customer_name}\n"
        msg += f"📦 ምርት፦ {order.product_name}\n"
        msg += f"🔢 ብዛት፦ {order.quantity}\n"
        msg += f"📝 ማስታወሻ፦ {order.note}\n"
        
        if ADMIN_CHAT_ID:
            bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
            
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/products")
def create_product(product: ProductCreate):
    try:
        existing = supabase.table("warehouse_stock").select("id, quantity").eq("product_name", product.name).execute()
        if existing.data:
            new_qty = existing.data[0]['quantity'] + product.quantity
            supabase.table("warehouse_stock").update({"quantity": new_qty}).eq("id", existing.data[0]['id']).execute()
        else:
            supabase.table("warehouse_stock").insert({
                "product_name": product.name,
                "quantity": product.quantity,
                "barcode": product.barcode
            }).execute()
            
        shelf_exist = supabase.table("products").select("id").eq("name", product.name).execute()
        if not shelf_exist.data:
            supabase.table("products").insert({
                "name": product.name,
                "quantity": 0,
                "barcode": product.barcode,
                "buying_price": product.buying_price,
                "selling_price": product.selling_price,
                "expiry_date": product.expiry_date
            }).execute()
            
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/transfer")
def transfer_product(transfer: TransferCreate):
    try:
        w_item = supabase.table("warehouse_stock").select("quantity, barcode").eq("product_name", transfer.product_name).execute()
        if not w_item.data or w_item.data[0]['quantity'] < transfer.quantity:
            return {"status": "error", "message": "በቂ ዕቃ ማከማቻ ውስጥ የለም!"}
            
        new_w_qty = w_item.data[0]['quantity'] - transfer.quantity
        barcode = w_item.data[0]['barcode']
        
        supabase.table("warehouse_stock").update({"quantity": new_w_qty}).eq("product_name", transfer.product_name).execute()
        
        shelf_item = supabase.table("products").select("quantity").eq("name", transfer.product_name).execute()
        if shelf_item.data:
            new_s_qty = shelf_item.data[0]['quantity'] + transfer.quantity
            supabase.table("products").update({"quantity": new_s_qty}).eq("name", transfer.product_name).execute()
        else:
            supabase.table("products").insert({
                "name": transfer.product_name,
                "quantity": transfer.quantity,
                "barcode": barcode
            }).execute()
            
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/credit")
def create_credit(credit: CreditCreate):
    try:
        existing = supabase.table("customers_credit").select("id, total_debt").eq("customer_name", credit.customer_name).execute()
        if existing.data:
            new_debt = float(existing.data[0]['total_debt']) + credit.total_debt
            data = supabase.table("customers_credit").update({"total_debt": new_debt, "phone_number": credit.phone_number}).eq("id", existing.data[0]['id']).execute()
        else:
            data = supabase.table("customers_credit").insert(credit.model_dump()).execute()
            
        return {"status": "success", "data": data.data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/finance")
def create_finance(finance: FinanceCreate):
    try:
        data = supabase.table("finance_records").insert(finance.model_dump()).execute()
        return {"status": "success", "data": data.data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/cron/nightly-report")
def send_nightly_report():
    """ በየቀኑ ማታ በክሮን ጆብ ተጠርቶ የዕለቱን ሪፖርት ለባለሱቁ ቀጥታ የሚልክ """
    try:
        today_str = str(date.today())
        data = supabase.table("finance_records").select("type, amount, description").gte("created_at", f"{today_str}T00:00:00").execute()
        
        ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID") 
        if not ADMIN_CHAT_ID:
            return {"status": "error", "message": "ADMIN_CHAT_ID አልተገኘም!"}

        if not data.data:
            bot.send_message(ADMIN_CHAT_ID, f"🌙 **የዕለቱ ማጠቃለያ ሪፖርት ({today_str})**\n\n📊 ለዛሬ ቀን የተመዘገበ የገቢም ሆነ የወጪ ሂሳብ የለም። ሱቁ መልካም ምሽት ይመኛል! 🕊️")
            return {"status": "success", "message": "No records, empty report sent."}
            
        total_income = 0
        total_expense = 0
        details = ""
        
        for rec in data.data:
            amt = float(rec['amount'])
            if rec['type'] == 'income':
                total_income += amt
                details += f"📥 +{amt} ብር ({rec['description']})\n"
            else:
                total_expense += amt
                details += f"📤 -{amt} ብር ({rec['description']})\n"
                
        net_profit = total_income - total_expense
        profit_status = "📈 የተጣራ ትርፍ" if net_profit >= 0 else "📉 ኪሳራ"
        
        response = f"🌙 **የዛሬ ዕለት አውቶማቲክ የሂሳብ ሪፖርት ({today_str})**\n"
        response += f"----------------------------------------\n"
        response += f"📥 ጠቅላላ ገቢ፦ **{total_income:.2f} ብር**\n"
        response += f"📤 ጠቅላላ ወጪ፦ **{total_expense:.2f} ብር**\n"
        response += f"----------------------------------------\n"
        response += f"{profit_status}፦ **{abs(net_profit):.2f} ብር**\n\n"
        response += f"📋 **የዕለቱ ዝርዝር እንቅስቃሴዎች፦**\n{details}"
        
        bot.send_message(ADMIN_CHAT_ID, response, parse_mode="Markdown")
        return {"status": "success", "message": "Nightly report sent successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/webhook")
async def telegram_webhook(request: Request):
    try:
        raw_json = await request.json()
        update = Update.de_json(raw_json)
        bot.process_new_updates([update])
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
