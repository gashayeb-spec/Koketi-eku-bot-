import os
import sqlite3
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8932085001:AAFSuqyjALyhumCO-Y6RwfHlwz1HJaugevU")
ADMIN_ID = os.environ.get("ADMIN_ID", "5351353727")
WEB_APP_URL = "https://koketi-eku-bot-1.onrender.com"
DB_PATH = os.environ.get("DB_PATH", "koketi_equb.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # የዕቁብ አባላት ሠንጠረዥ
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
            payment_method TEXT,
            cycle_amount REAL,
            paid_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'Pending',
            member_cheque TEXT,
            guarantor_name TEXT,
            guarantor_cheque TEXT,
            collateral_item TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # የዕቁብ አጠቃላይ ሴቲንግ (የዕጣ ቁጥር፣ ቀን፣ ጠቅላላ የብር ግብ)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equb_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            total_target_amount REAL DEFAULT 2000000,
            latest_draw_number TEXT DEFAULT 'አልወጣም',
            latest_draw_date TEXT DEFAULT '-'
        )
    ''')
    cursor.execute('INSERT OR IGNORE INTO equb_settings (id, total_target_amount) VALUES (1, 2000000)')
    conn.commit()
    conn.close()

init_db()

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.json
    if update and "message" in update:
        chat_id = str(update["message"]["chat"]["id"])
        text = update["message"].get("text", "")

        if text.startswith("/start"):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # የአባላት ብዛት ማወቅ
            cursor.execute("SELECT COUNT(*) FROM equb_members WHERE status='Approved'")
            approved_count = cursor.fetchone()[0]

            # የሴቲንግ መረጃዎች
            cursor.execute("SELECT total_target_amount, latest_draw_number, latest_draw_date FROM equb_settings WHERE id=1")
            sett = cursor.fetchone()
            target_amount, draw_num, draw_date = sett if sett else (2000000, 'አልወጣም', '-')

            # የአባሉን መረጃ መፈለግ
            cursor.execute("SELECT ref_no, first_name, cycle_amount, paid_amount, status, member_cheque, guarantor_name, guarantor_cheque, collateral_item FROM equb_members WHERE telegram_id=?", (chat_id,))
            member = cursor.fetchone()
            conn.close()

            if member:
                ref_no, name, cycle_amt, paid_amt, status, m_cheque, g_name, g_cheque, col_item = member
                remaining = max(0, cycle_amt - paid_amt)

                if status == 'Pending':
                    msg = (
                        f"👋 <b>ሰላም {name}!</b>\n\n"
                        f"📌 <b>የመዝገብ ቁጥር:</b> {ref_no}\n"
                        f"⏳ <b>የምዝገባ ሁኔታ:</b> <a href='#'>በአድሚን በመረጋገጥ ላይ (Pending)</a>\n\n"
                        f"<i>አድሚኑ መረጃዎትን አረጋግጦ ሲያጸድቀው ዲጂታል የዕቁብ ደብተርዎ ይከፈታል።</i>"
                    )
                else:
                    msg = (
                        f"📖 <b>የ KOKETI ዕቁብ ደብተር (Passbook)</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 <b>አባል:</b> {name} ({ref_no})\n"
                        f"👥 <b>ጠቅላላ የዕቁብ አባላት ብዛት:</b> {approved_count} አባላት\n"
                        f"🎯 <b>ጠቅላላ የዕቁብ ግብ:</b> {target_amount:,.2f} ብር\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"💰 <b>የእርስዎ የዕቁብ ዙር:</b> {cycle_amt:,.2f} ብር\n"
                        f"✅ <b>እስካሁን የከፈሉት:</b> {paid_amt:,.2f} ብር\n"
                        f"🔻 <b>ቀሪ እዳዎ:</b> {remaining:,.2f} ብር\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🎲 <b>የሳምንቱ የወጣው ዕጣ ቁጥር:</b> {draw_num}\n"
                        f"📅 <b>የዕጣ ቀን:</b> {draw_date}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🔒 <b>የግልና የዋስትና መረጃዎ (ለእርስዎ ብቻ የሚታይ)፦</b>\n"
                        f"• የእርስዎ ቼክ: {m_cheque or 'አልተመዘገበም'}\n"
                        f"• የዋስ ስም: {g_name or 'አልተመዘገበም'}\n"
                        f"• የዋስ ቼክ: {g_cheque or 'አልተመዘገበም'}\n"
                        f"• የዋስትና ንብረት: {col_item or 'አልተመዘገበም'}"
                    )
            else:
                msg = (
                    "👋 <b>እንኳን ወደ KOKETI KURT & LOUNGE የዕቁብ አገልግሎት በሰላም መጡ!</b>\n\n"
                    f"👥 <b>አሁን ያሉት ተመዝጋቢ አባላት ብዛት:</b> {approved_count}\n\n"
                    "ከታች ያለውን ቁልፍ በመጫን መመዝገብ ይችላሉ።"
                )

            reply_markup = {
                "inline_keyboard": [[
                    {"text": "📝 የዕቁብ መመዝገቢያ ፎርም", "web_app": {"url": WEB_APP_URL}}
                ]]
            }
            send_telegram_message(chat_id, msg, reply_markup)

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
        telegram_id = str(data.get('telegram_id', ''))
        first_name = data.get('first_name')
        father_name = data.get('father_name')
        grand_name = data.get('grand_name')
        phone_number = data.get('phone_number')
        gps_location = data.get('gps_location', '')
        region = data.get('region_select', '')
        payment_method = data.get('payment_method', '')
        cycle_amount = float(data.get('cycle_amount', 0))
        paid_amount = float(data.get('paid_amount', 0))
        member_cheque = data.get('member_cheque', '')
        guarantor_name = data.get('guarantor_name', '')
        guarantor_cheque = data.get('guarantor_cheque', '')
        collateral_item = data.get('collateral_item', '')

        cursor.execute('''
            INSERT INTO equb_members (
                ref_no, telegram_id, first_name, father_name, grand_name,
                phone_number, gps_location, region, payment_method, cycle_amount,
                paid_amount, member_cheque, guarantor_name,
                guarantor_cheque, collateral_item, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
        ''', (
            ref_no, telegram_id, first_name, father_name, grand_name,
            phone_number, gps_location, region, payment_method, cycle_amount,
            paid_amount, member_cheque, guarantor_name,
            guarantor_cheque, collateral_item
        ))
        
        conn.commit()
        conn.close()

        # ለአድሚኑ ማሳወቂያ መላክ
        msg_admin = (
            f"🔔 <b>አዲስ አባል ተመዝግቧል (ማረጋገጫ ይፈልጋል)!</b>\n\n"
            f"🆔 <b>Ref No:</b> {ref_no}\n"
            f"👤 <b>ስም:</b> {first_name} {father_name} {grand_name}\n"
            f"📞 <b>ስልክ:</b> {phone_number}\n"
            f"💳 <b>የክፍያ መንገድ:</b> {payment_method}\n"
            f"💵 <b>የዕቁብ መጠን:</b> {cycle_amount:,.2f} ብር\n"
            f"✅ <b>የተከፈለ:</b> {paid_amount:,.2f} ብር"
        )
        send_telegram_message(ADMIN_ID, msg_admin)

        return jsonify({"status": "success", "message": "ምዝገባዎ ተልኳል! አድሚኑ ሲያረጋግጠው ደብተርዎ ይከፈታል።"}), 200

    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "ይህ የመዝገብ ቁጥር አስቀድሞ ተመዝግቧል!"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
