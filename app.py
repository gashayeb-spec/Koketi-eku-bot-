import os
import sqlite3
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

# የቴሌግራም ቦት እና የአድሚን መረጃዎች
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8932085001:AAFSuqyjALyhumCO-Y6RwfHlwz1HJaugevU")
ADMIN_ID = os.environ.get("ADMIN_ID", "5351353727")

# Render URL
WEB_APP_URL = "https://koketi-eku-bot-1.onrender.com"

# Render ላይ ዳታቤዙ እንዳይጠፋ የሚቀመጥበት መንገድ
DB_PATH = os.environ.get("DB_PATH", "koketi_equb.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equb_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_no TEXT UNIQUE,
            telegram_id TEXT,
            first_name TEXT,
            father_name TEXT,
            grand_name TEXT,
            phone_number TEXT,
            gps_location TEXT,
            region TEXT,
            cycle_amount REAL,
            paid_amount REAL,
            remaining_due REAL,
            member_cheque TEXT,
            guarantor_name TEXT,
            guarantor_cheque TEXT,
            collateral_item TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"የቴሌግራም መልእክት ስህተት: {e}")

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# የቴሌግራም Webhook መልእክቶችን መቀበያ endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.json
    if update and "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text.startswith("/start"):
            welcome_msg = (
                "👋 <b>እንኳን ወደ KOKETI KURT & LOUNGE የዕቁብ አገልግሎት በሰላም መጡ!</b>\n\n"
                "ከታች ያለውን <b>'📝 የዕቁብ መመዝገቢያ ፎርም'</b> የሚለውን ቁልፍ በመጫን መመዝገብና መረጃዎን መሙላት ይችላሉ።"
            )
            reply_markup = {
                "inline_keyboard": [[
                    {"text": "📝 የዕቁብ መመዝገቢያ ፎርም", "web_app": {"url": WEB_APP_URL}}
                ]]
            }
            send_telegram_message(chat_id, welcome_msg, reply_markup)

    return jsonify({"status": "ok"}), 200

@app.route('/api/register', methods=['POST'])
def register_equb():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "ምንም መረጃ አልተላከም!"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        ref_no = data.get('ref_no')
        telegram_id = data.get('telegram_id', '')
        first_name = data.get('first_name')
        father_name = data.get('father_name')
        grand_name = data.get('grand_name')
        phone_number = data.get('phone_number')
        gps_location = data.get('gps_location', '')
        region = data.get('region_select', '')
        cycle_amount = float(data.get('cycle_amount', 0))
        paid_amount = float(data.get('paid_amount', 0))
        remaining_due = float(data.get('remaining_due', 0))
        
        member_cheque = data.get('member_cheque', '')
        guarantor_name = data.get('guarantor_name', '')
        guarantor_cheque = data.get('guarantor_cheque', '')
        collateral_item = data.get('collateral_item', '')

        cursor.execute('''
            INSERT INTO equb_members (
                ref_no, telegram_id, first_name, father_name, grand_name,
                phone_number, gps_location, region, cycle_amount,
                paid_amount, remaining_due, member_cheque, guarantor_name,
                guarantor_cheque, collateral_item
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ref_no, telegram_id, first_name, father_name, grand_name,
            phone_number, gps_location, region, cycle_amount,
            paid_amount, remaining_due, member_cheque, guarantor_name,
            guarantor_cheque, collateral_item
        ))
        
        conn.commit()
        conn.close()

        # 1. ለተመዝጋቢው ደንበኛ ማረጋገጫ መላክ
        if telegram_id:
            msg_user = (
                f"🎉 <b>እንኳን ወደ KOKETI KURT & LOUNGE ዕቁብ በሰላም መጡ!</b>\n\n"
                f"📌 <b>የመዝገብ ቁጥር (Ref):</b> {ref_no}\n"
                f"👤 <b>ስም:</b> {first_name} {father_name}\n"
                f"💰 <b>የዕቁብ ዙር:</b> {cycle_amount:,.2f} ብር\n"
                f"✅ <b>የተከፈለ:</b> {paid_amount:,.2f} ብር\n"
                f"፪ <b>ቀሪ እዳ:</b> {remaining_due:,.2f} ብር\n\n"
                f"<i>ምዝገባዎ በተሳካ ሁኔታ ተጠናቋል!</i>"
            )
            send_telegram_message(telegram_id, msg_user)

        # 2. ለአድሚኑ አዲስ ምዝገባ መኖሩን ማሳወቅ
        msg_admin = (
            f"🔔 <b>አዲስ የዕቁብ ምዝገባ ተከናውኗል!</b>\n\n"
            f"🆔 <b>Ref No:</b> {ref_no}\n"
            f"👤 <b>ስም:</b> {first_name} {father_name} {grand_name}\n"
            f"📞 <b>ስልክ:</b> {phone_number}\n"
            f"📍 <b>ቦታ/ክልል:</b> {region} {gps_location}\n"
            f"💵 <b>የዕቁብ መጠን:</b> {cycle_amount:,.2f} ብር\n"
            f"💳 <b>የተከፈለ:</b> {paid_amount:,.2f} ብር"
        )
        send_telegram_message(ADMIN_ID, msg_admin)

        return jsonify({"status": "success", "message": "መረጃው በተሳካ ሁኔታ ተመዝግቧል!"}), 200

    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "ይህ የመዝገብ ቁጥር አስቀድሞ ተመዝግቧል!"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
