import os
import sqlite3
import json
import requests
import re
import random
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

# Config
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8932085001:AAFSuqyjALyhumCO-Y6RwfHlwz1HJaugevU")
ADMIN_ID = os.environ.get("ADMIN_ID", "5351353727")
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://koketi-eku-bot-1.onrender.com")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "koketi_equb.db"))
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

failed_attempts = {}
current_otp = None

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Equb Members Table
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
            share_count INTEGER DEFAULT 1,
            paid_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'Pending',
            weekly_paid_status INTEGER DEFAULT 0,
            member_cheque TEXT DEFAULT '-',
            guarantor_name TEXT DEFAULT '-',
            guarantor_cheque TEXT DEFAULT '-',
            collateral_item TEXT DEFAULT '-',
            receipt_path TEXT DEFAULT '-',
            receipt_url TEXT DEFAULT NULL,
            receipt_ref TEXT DEFAULT NULL,
            weekly_receipt_url TEXT DEFAULT NULL,
            weekly_receipt_ref TEXT DEFAULT NULL,
            transaction_id TEXT DEFAULT NULL,
            referred_by TEXT DEFAULT '-',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Auto-migration for existing DBs
    cursor.execute("PRAGMA table_info(equb_members)")
    cols = [col[1] for col in cursor.fetchall()]
    new_cols = {
        'receipt_url': 'TEXT DEFAULT NULL',
        'receipt_ref': 'TEXT DEFAULT NULL',
        'weekly_receipt_url': 'TEXT DEFAULT NULL',
        'weekly_receipt_ref': 'TEXT DEFAULT NULL',
        'transaction_id': 'TEXT DEFAULT NULL'
    }
    for col_name, col_type in new_cols.items():
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE equb_members ADD COLUMN {col_name} {col_type}")

    # 2. Equb Settings Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equb_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            total_target_amount REAL DEFAULT 2000000,
            latest_draw_number TEXT DEFAULT 'አልወጣም',
            latest_draw_date TEXT DEFAULT '-',
            current_week INTEGER DEFAULT 1,
            winner_name TEXT DEFAULT '-',
            max_members INTEGER DEFAULT 100,
            registration_status TEXT DEFAULT 'OPEN',
            bot_status TEXT DEFAULT 'ACTIVE',
            admin_password TEXT DEFAULT 'Koketi@2026',
            support_phone TEXT DEFAULT '+251 911 00 00 00'
        )
    ''')
    
    cursor.execute("PRAGMA table_info(equb_settings)")
    s_cols = [col[1] for col in cursor.fetchall()]
    if 'bot_status' not in s_cols:
        cursor.execute("ALTER TABLE equb_settings ADD COLUMN bot_status TEXT DEFAULT 'ACTIVE'")
    if 'support_phone' not in s_cols:
        cursor.execute("ALTER TABLE equb_settings ADD COLUMN support_phone TEXT DEFAULT '+251 911 00 00 00'")

    cursor.execute('INSERT OR IGNORE INTO equb_settings (id, total_target_amount, max_members, registration_status, bot_status, admin_password, support_phone) VALUES (1, 2000000, 100, "OPEN", "ACTIVE", "Koketi@2026", "+251 911 00 00 00")')
    
    # 3. Payment Transactions Ledger Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER,
            ref_no TEXT,
            week_number INTEGER,
            amount REAL,
            receipt_url TEXT,
            receipt_ref TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(member_id) REFERENCES equb_members(id)
        )
    ''')

    conn.commit()
    conn.close()

init_db()

def set_telegram_webhook():
    webhook_url = f"{WEB_APP_URL}/webhook"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    try:
        requests.get(url, timeout=5)
    except Exception as e:
        print(f"Webhook Error: {e}")

set_telegram_webhook()

def is_strong_password(password):
    if len(password) < 8 or not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password) or not re.search(r"[0-9]", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

# Persistent Reply Keyboard Generator (የተቀነሰ ናቪጌሽን)
def get_persistent_reply_keyboard(is_admin=False):
    keyboard_buttons = [
        [{"text": "💳 ሳምንታዊ ክፍያ ፈፅም"}]
    ]
    if is_admin:
        keyboard_buttons.append([{"text": "⚙️ የአድሚን መቆጣጠሪያ ፓናል"}])
        
    return {
        "keyboard": keyboard_buttons,
        "resize_keyboard": True,
        "is_persistent": True
    }

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = reply_markup
    try:
        return requests.post(url, json=payload, timeout=5).json()
    except Exception as e:
        print(f"Telegram Msg Error: {e}")
        return None

def send_telegram_photo(chat_id, photo_path, caption, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
            files = {"photo": photo}
            return requests.post(url, data=payload, files=files, timeout=10).json()
    except Exception as e:
        print(f"Telegram Photo Error: {e}")
        return None

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/admin')
def admin_page():
    return send_from_directory('.', 'admin.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    global failed_attempts
    data = request.json or {}
    password = data.get('password', '')
    ip = request.remote_addr

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT admin_password FROM equb_settings WHERE id=1")
    db_pass = cursor.fetchone()[0]
    conn.close()

    if password == db_pass:
        failed_attempts[ip] = 0
        return jsonify({"status": "success", "message": "Login Successful"})
    else:
        failed_attempts[ip] = failed_attempts.get(ip, 0) + 1
        attempts = failed_attempts[ip]
        if attempts >= 3:
            alert_msg = (
                f"🚨 <b>SECURITY ALERT!</b>\n\n"
                f"⚠️ የአድሚን ፓናሉን ለመክፈት ያልተፈቀደ/የተሳሳተ የ Log In ሙከራ ተደርጓል!\n"
                f"🌐 <b>IP:</b> <code>{ip}</code> | ❌ <b>ሙከራ:</b> {attempts} ጊዜ"
            )
            send_telegram_message(ADMIN_ID, alert_msg)
        return jsonify({"status": "error", "message": "የተሳሳተ የይለፍ ቃል ነው!", "attempts": attempts}), 401

@app.route('/api/admin/request_otp', methods=['POST'])
def request_otp():
    global current_otp
    current_otp = str(random.randint(100000, 999999))
    msg = f"🔐 <b>የይለፍ ቃል መቀየሪያ OTP:</b> <code>{current_otp}</code>\n⚠️ ለማንም ሰው አያጋሩ!"
    send_telegram_message(ADMIN_ID, msg)
    return jsonify({"status": "success", "message": "OTP ወደ አድሚኑ ቴሌግራም ተልኳል!"})

@app.route('/api/admin/reset_password', methods=['POST'])
def reset_password():
    global current_otp
    data = request.json or {}
    otp = data.get('otp')
    new_password = data.get('new_password')

    if not current_otp or otp != current_otp:
        return jsonify({"status": "error", "message": "የተሳሳተ OTP ኮድ ነው!"}), 400
    if not is_strong_password(new_password):
        return jsonify({"status": "error", "message": "ፓስወርዱ ጥንካሬ አልጠበቀም! ቢያንስ 8 አሃዝ፣ ትልቅ/ትንሽ ፊደል፣ ቁጥርና ልዩ ምልክት ያካቱ።"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE equb_settings SET admin_password=? WHERE id=1", (new_password,))
    conn.commit()
    conn.close()
    current_otp = None
    send_telegram_message(ADMIN_ID, "✅ <b>የአድሚን ይለፍ ቃልዎ በስኬት ተቀይሯል!</b>")
    return jsonify({"status": "success", "message": "የይለፍ ቃልዎ በስኬት ተቀይሯል!"})

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.json
    if not update: return jsonify({"status": "ok"}), 200

    conn = get_db_connection()
    cursor = conn.cursor()

    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        cb_data = cb.get("data", "")

        if cb_data.startswith("approve_m_"):
            m_id = cb_data.replace("approve_m_", "")
            cursor.execute("UPDATE equb_members SET status='Approved' WHERE id=?", (m_id,))
            cursor.execute("SELECT telegram_id, first_name, ref_no FROM equb_members WHERE id=?", (m_id,))
            row = cursor.fetchone()
            conn.commit()
            if row and row['telegram_id']:
                p_key = get_persistent_reply_keyboard(str(row['telegram_id']) == str(ADMIN_ID))
                send_telegram_message(row['telegram_id'], f"🎉 <b>እንኳን ደስ አለዎት {row['first_name']}!</b>\nየዕቁብ ምዝገባዎ ጸድቋል። የመዝገብ ቁጥር: <b>{row['ref_no']}</b>", p_key)
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "አባሉ ጸድቋል!"})

        elif cb_data.startswith("reject_m_"):
            m_id = cb_data.replace("reject_m_", "")
            cursor.execute("UPDATE equb_members SET status='Cancelled' WHERE id=?", (m_id,))
            cursor.execute("SELECT telegram_id, first_name FROM equb_members WHERE id=?", (m_id,))
            row = cursor.fetchone()
            conn.commit()
            if row and row['telegram_id']:
                send_telegram_message(row['telegram_id'], f"🚫 <b>ሰላም {row['first_name']}፣</b>\nየዕቁብ ምዝገባዎ ውድቅ ተደርጓል።")
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "ምዝገባው ውድቅ ተደርጓል!"})

        elif cb_data.startswith("block_m_"):
            m_id = cb_data.replace("block_m_", "")
            cursor.execute("UPDATE equb_members SET status='Blocked' WHERE id=?", (m_id,))
            cursor.execute("SELECT telegram_id, first_name FROM equb_members WHERE id=?", (m_id,))
            row = cursor.fetchone()
            conn.commit()
            if row and row['telegram_id']:
                send_telegram_message(row['telegram_id'], f"⛔ <b>ሰላም {row['first_name']}፣</b>\nአካውንትዎ ታግዷል። እባክዎን አድሚኑን ያናግሩ።")
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "አባሉ ታግዷል!"})

        elif cb_data.startswith("approve_pay_"):
            raw_id = cb_data.replace("approve_pay_", "")
            tx_row = None
            if raw_id.isdigit():
                cursor.execute("SELECT * FROM payment_transactions WHERE id=?", (raw_id,))
                tx_row = cursor.fetchone()

            if tx_row:
                if tx_row['status'] == 'Approved':
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "⚠️ ይህ ደረሰኝ አስቀድሞ ጸድቋል!"})
                else:
                    m_id = tx_row['member_id']
                    pay_amt = tx_row['amount']
                    cursor.execute("UPDATE payment_transactions SET status='Approved' WHERE id=?", (raw_id,))
                    cursor.execute("UPDATE equb_members SET weekly_paid_status=1, paid_amount=paid_amount+? WHERE id=?", (pay_amt, m_id))
                    cursor.execute("SELECT telegram_id, first_name, ref_no FROM equb_members WHERE id=?", (m_id,))
                    mrow = cursor.fetchone()
                    conn.commit()
                    if mrow and mrow['telegram_id']:
                        send_telegram_message(mrow['telegram_id'], f"✅ <b>ሰላም {mrow['first_name']}፣</b>\nለአካውንትዎ (Ref: <b>{mrow['ref_no']}</b>) የላኩት ክፍያ {pay_amt:,.2f} ብር ተረጋግጦ በደብተርዎ ላይ ጸድቋል!")
                    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "ክፍያው በስኬት ጸድቋል!"})
            else:
                m_id = raw_id
                cursor.execute("SELECT cycle_amount, share_count, paid_amount, telegram_id, first_name, ref_no, weekly_paid_status FROM equb_members WHERE id=?", (m_id,))
                row = cursor.fetchone()
                if row:
                    if row['weekly_paid_status'] == 1:
                        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "⚠️ ይህ ክፍያ አስቀድሞ ጸድቋል!"})
                    else:
                        add_pay = row['cycle_amount'] * row['share_count']
                        cursor.execute("UPDATE equb_members SET weekly_paid_status=1, paid_amount=paid_amount+? WHERE id=?", (add_pay, m_id))
                        conn.commit()
                        if row['telegram_id']:
                            send_telegram_message(row['telegram_id'], f"✅ <b>ሰላም {row['first_name']}፣</b>\nለአካውንትዎ (Ref: <b>{row['ref_no']}</b>) የላኩት ክፍያ {add_pay:,.2f} ብር ተረጋግጦ ጸድቋል!")
                        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "የሳምንቱ ክፍያ ተጸድቋል!"})

        conn.close()
        return jsonify({"status": "ok"}), 200

    if "message" in update:
        chat_id = str(update["message"]["chat"]["id"])
        text = update["message"].get("text", "")

        cursor.execute("SELECT COUNT(*) as count FROM equb_members WHERE status='Approved'")
        approved_count = cursor.fetchone()['count']
        cursor.execute("SELECT current_week, latest_draw_number, latest_draw_date, winner_name, support_phone FROM equb_settings WHERE id=1")
        sett = cursor.fetchone()

        cursor.execute("SELECT * FROM equb_members WHERE telegram_id=?", (chat_id,))
        members = cursor.fetchall()

        is_admin = (chat_id == str(ADMIN_ID))
        p_key = get_persistent_reply_keyboard(is_admin)

        if text.startswith("/start"):
            if members:
                msg = f"📖 <b>የ KOKETI ዕቁብ ደብተር (አካውንቶች፦ {len(members)})</b>\n━━━━━━━━━━━━━━━━━━━\n"
                for m in members:
                    paid_str = "✅ ተከፍሏል" if m['weekly_paid_status'] == 1 else "❌ አልተከፈለም"
                    msg += f"👤 <b>{m['first_name']} {m['father_name']}</b> ({m['ref_no']})\n📌 <b>ሁኔታ:</b> {m['status']} | <b>ክፍያ:</b> {paid_str}\n💰 <b>የተከፈለ:</b> {m['paid_amount']:,.2f} / {m['cycle_amount'] * m['share_count']:,.2f} ብር\n-----------------------------------\n"
            else:
                msg = f"👋 <b>እንኳን ወደ KOKETI KURT & LOUNGE ዕቁብ አገልግሎት በሰላም መጡ!</b>\n\n👥 <b>ተመዝጋቢ አባላት:</b> {approved_count}\n📅 <b>ሳምንት:</b> {sett['current_week'] if sett else 1}"

            inline_key = {"inline_keyboard": [[{"text": "📝 የዕቁብ ገጽ / አዲስ ምዝገባ", "web_app": {"url": WEB_APP_URL}}]]}
            if is_admin:
                inline_key["inline_keyboard"].append([{"text": "⚙️ የአድሚን መቆጣጠሪያ ፓናል", "web_app": {"url": f"{WEB_APP_URL}/admin"}}])

            send_telegram_message(chat_id, msg, p_key)
            send_telegram_message(chat_id, "👇 ከታች ያለውን አዝራር በመጫን የዕቁብ አፕሊኬሽኑን መክፈት ይችላሉ፦", inline_key)

        elif text == "💳 ሳምንታዊ ክፍያ ፈፅም":
            inline_key = {"inline_keyboard": [[{"text": "💳 ክፍያ ለመክፈል አፑን ክፈት", "web_app": {"url": WEB_APP_URL}}]]}
            send_telegram_message(chat_id, "📲 እባክዎን ከታች ያለውን አዝራር በመጫን የክፍያ ስክሪንሹት ወይም የትራንዛክሽን ቁጥር ያስገቡ፦", inline_key)

        elif text == "⚙️ የአድሚን መቆጣጠሪያ ፓናል" and is_admin:
            inline_key = {"inline_keyboard": [[{"text": "⚙️ ወደ አድሚን ፓናል ግባ", "web_app": {"url": f"{WEB_APP_URL}/admin"}}]]}
            send_telegram_message(chat_id, "🔧 የአድሚን ፓናሉን ለመክፈት ከታች ያለውን ይጫኑ፦", inline_key)

        conn.close()
    return jsonify({"status": "ok"}), 200

@app.route('/api/member_info/<telegram_id>', methods=['GET'])
def get_member_info(telegram_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equb_members WHERE telegram_id=? ORDER BY id DESC", (telegram_id,))
    members = [dict(r) for r in cursor.fetchall()]
    cursor.execute("SELECT registration_status, max_members, current_week, latest_draw_number, latest_draw_date, winner_name, bot_status, support_phone FROM equb_settings WHERE id=1")
    settings = dict(cursor.fetchone())
    cursor.execute("SELECT COUNT(*) as count FROM equb_members WHERE status='Approved'")
    total_approved = cursor.fetchone()['count']
    conn.close()
    return jsonify({"members": members, "settings": settings, "total_approved": total_approved})

@app.route('/api/register', methods=['POST'])
def register_equb():
    try:
        ref_no = request.form.get('ref_no')
        telegram_id = request.form.get('telegram_id', '')
        first_name = request.form.get('first_name')
        father_name = request.form.get('father_name')
        grand_name = request.form.get('grand_name')
        phone_number = request.form.get('phone_number')
        region = request.form.get('region_select', '')
        gps_location = request.form.get('gps_location', '')
        share_count = int(request.form.get('share_count', 1))
        cycle_amount = float(request.form.get('cycle_amount', 5000))
        payment_method = request.form.get('payment_method', '')
        referred_by = request.form.get('referred_by', '-')
        receipt_url = request.form.get('receipt_url', None)
        receipt_ref = request.form.get('receipt_ref', None)

        receipt_file = request.files.get('receipt')
        receipt_filename = '-'
        filepath = None

        if receipt_file:
            receipt_filename = f"reg_{ref_no}_{receipt_file.filename}"
            filepath = os.path.join(UPLOAD_FOLDER, receipt_filename)
            receipt_file.save(filepath)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO equb_members (
                ref_no, telegram_id, first_name, father_name, grand_name,
                phone_number, gps_location, region, payment_method, cycle_amount,
                share_count, paid_amount, status, receipt_path, receipt_url, receipt_ref, referred_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'Pending', ?, ?, ?, ?)
        ''', (ref_no, telegram_id, first_name, father_name, grand_name, phone_number, gps_location, region, payment_method, cycle_amount, share_count, receipt_filename, receipt_url, receipt_ref, referred_by))
        member_id = cursor.lastrowid

        conn.commit()
        conn.close()

        msg_admin = (
            f"🔔 <b>አዲስ አባል ተመዝግቧል!</b>\n\n"
            f"🆔 <b>Ref No:</b> {ref_no}\n"
            f"👤 <b>ስም:</b> {first_name} {father_name} {grand_name}\n"
            f"📞 <b>ስልክ:</b> {phone_number}\n"
            f"🎲 <b>የዕጣ ብዛት:</b> {share_count}\n"
            f"💵 <b>የዕጣ ዙር:</b> {cycle_amount:,.2f} ብር\n"
            f"📌 <b>ደረሰኝ/Ref:</b> {receipt_ref or '-'}\n"
            f"🔗 <b>ሪፈራል:</b> {referred_by}"
        )
        inline_markup = {"inline_keyboard": [
            [{"text": "✅ አጽድቅ", "callback_data": f"approve_m_{member_id}"}, {"text": "⚙️ አገልግሎት/አሻሽል", "callback_data": f"approve_m_{member_id}"}, {"text": "⛔ አግድ", "callback_data": f"block_m_{member_id}"}],
            [{"text": "⚙️ ወደ አድሚን ፓናል ግባ", "web_app": {"url": f"{WEB_APP_URL}/admin"}}]
        ]}

        if filepath and os.path.exists(filepath):
            send_telegram_photo(ADMIN_ID, filepath, msg_admin, inline_markup)
        else:
            send_telegram_message(ADMIN_ID, msg_admin, inline_markup)

        return jsonify({"status": "success", "message": "ምዝገባው ተጠናቅቋል!"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "ይህ መዝገብ ቁጥር አስቀድሞ አለ!"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/upload_weekly_receipt', methods=['POST'])
def upload_weekly_receipt():
    member_id = request.form.get('member_id')
    receipt_file = request.files.get('receipt')
    receipt_url = request.form.get('receipt_url', None)
    receipt_ref = request.form.get('receipt_ref', None)

    if not member_id:
        return jsonify({"status": "error", "message": "አባል አልተመረጠም"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equb_members WHERE id=?", (member_id,))
    member = cursor.fetchone()

    if not member: 
        conn.close()
        return jsonify({"status": "error", "message": "አባል አልተገኘም"}), 404

    cursor.execute("SELECT current_week FROM equb_settings WHERE id=1")
    curr_week = cursor.fetchone()['current_week']

    filename = '-'
    filepath = None
    if receipt_file:
        filename = f"weekly_{member['ref_no']}_{receipt_file.filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        receipt_file.save(filepath)

    pay_amt = member['cycle_amount'] * member['share_count']

    # Insert into payment transactions ledger
    cursor.execute('''
        INSERT INTO payment_transactions (member_id, ref_no, week_number, amount, receipt_url, receipt_ref, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Pending')
    ''', (member_id, member['ref_no'], curr_week, pay_amt, receipt_url, receipt_ref))
    tx_id = cursor.lastrowid

    # Update latest pointers on member row
    cursor.execute('''
        UPDATE equb_members 
        SET weekly_receipt_url=?, weekly_receipt_ref=?, transaction_id=?
        WHERE id=?
    ''', (receipt_url, receipt_ref, receipt_ref, member_id))

    conn.commit()
    conn.close()

    caption = (
        f"🧾 <b>አዲስ የሳምንታዊ ክፍያ ማረጋገጫ!</b>\n\n"
        f"👤 <b>አባል:</b> {member['first_name']} {member['father_name']}\n"
        f"🔢 <b>Ref No:</b> {member['ref_no']}\n"
        f"📞 <b>ስልክ:</b> {member['phone_number']}\n"
        f"💰 <b>የሳምንቱ ክፍያ:</b> {pay_amt:,.2f} ብር\n"
        f"📌 <b>Ref/Tx ID:</b> {receipt_ref or '-'}"
    )
    inline_markup = {"inline_keyboard": [
        [{"text": "✅ አጽድቅ (Approve)", "callback_data": f"approve_pay_{tx_id}"}, {"text": "⚙️ ሰርቪስ (Service)", "callback_data": f"approve_pay_{tx_id}"}, {"text": "⛔ አግድ (Block)", "callback_data": f"block_m_{member_id}"}],
        [{"text": "⚙️ ወደ አድሚን ፓናል ግባ", "web_app": {"url": f"{WEB_APP_URL}/admin"}}]
    ]}

    if filepath and os.path.exists(filepath):
        send_telegram_photo(ADMIN_ID, filepath, caption, inline_markup)
    else:
        send_telegram_message(ADMIN_ID, caption, inline_markup)

    return jsonify({"status": "success", "message": "የክፍያ መረጃው ለአድሚኑ ተልኳል!"}), 200

@app.route('/api/admin/members', methods=['GET'])
def get_admin_members():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equb_members ORDER BY id DESC")
    members = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(*) as total FROM equb_members")
    total_reg = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as approved FROM equb_members WHERE status='Approved'")
    total_approved = cursor.fetchone()['approved']
    cursor.execute("SELECT COUNT(*) as pending FROM equb_members WHERE status='Pending'")
    total_pending = cursor.fetchone()['pending']
    cursor.execute("SELECT COUNT(*) as blocked FROM equb_members WHERE status='Blocked'")
    total_blocked = cursor.fetchone()['blocked']
    cursor.execute("SELECT SUM(paid_amount) as total_paid FROM equb_members")
    total_paid_sum = cursor.fetchone()['total_paid'] or 0

    cursor.execute("SELECT * FROM equb_settings WHERE id=1")
    settings = dict(cursor.fetchone())
    conn.close()

    stats = {
        "total_registered": total_reg,
        "total_approved": total_approved,
        "total_pending": total_pending,
        "total_blocked": total_blocked,
        "total_paid_sum": total_paid_sum
    }
    return jsonify({"members": members, "settings": settings, "stats": stats})

@app.route('/api/admin/change_status/<int:member_id>', methods=['POST'])
def change_status(member_id):
    data = request.json
    new_status = data.get('status')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE equb_members SET status=? WHERE id=?", (new_status, member_id))
    cursor.execute("SELECT telegram_id, first_name, ref_no FROM equb_members WHERE id=?", (member_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()

    if row and row['telegram_id']:
        p_key = get_persistent_reply_keyboard(str(row['telegram_id']) == str(ADMIN_ID))
        if new_status == 'Approved':
            send_telegram_message(row['telegram_id'], f"🎉 <b>እንኳን ደስ አለዎት {row['first_name']}!</b>\nመዝገብ ቁጥርዎ <b>{row['ref_no']}</b> ጸድቋል።", p_key)
        elif new_status == 'Blocked':
            send_telegram_message(row['telegram_id'], f"⛔ <b>ሰላም {row['first_name']}፣</b>\nአካውንትዎ ታግዷል።")
        elif new_status == 'Cancelled':
            send_telegram_message(row['telegram_id'], f"🚫 <b>ሰላም {row['first_name']}፣</b>\nየዕቁብ ምዝገባዎ ተሰርዟል።")

    return jsonify({"status": "success"})

@app.route('/api/admin/delete_member/<int:member_id>', methods=['DELETE'])
def delete_member(member_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM equb_members WHERE id=?", (member_id,))
    cursor.execute("DELETE FROM payment_transactions WHERE member_id=?", (member_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "አባሉ ተሰርዟል"})

@app.route('/api/admin/update_bot_status', methods=['POST'])
def update_bot_status():
    data = request.json or {}
    bot_status = data.get('bot_status', 'ACTIVE')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE equb_settings SET bot_status=? WHERE id=1", (bot_status,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "የቦቱ ሁኔታ ተስተካክሏል"})

@app.route('/api/admin/update_registration_settings', methods=['POST'])
def update_registration_settings():
    data = request.json
    max_m = data.get('max_members', 100)
    reg_s = data.get('registration_status', 'OPEN')
    support_phone = data.get('support_phone', '+251 911 00 00 00')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE equb_settings SET max_members=?, registration_status=?, support_phone=? WHERE id=1", (max_m, reg_s, support_phone))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/admin/update_guarantor/<int:member_id>', methods=['POST'])
def update_guarantor(member_id):
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE equb_members 
        SET member_cheque=?, guarantor_name=?, guarantor_cheque=?, collateral_item=? 
        WHERE id=?
    ''', (data.get('member_cheque', '-'), data.get('guarantor_name', '-'), data.get('guarantor_cheque', '-'), data.get('collateral_item', '-'), member_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/admin/toggle_payment/<int:member_id>', methods=['POST'])
def toggle_payment(member_id):
    data = request.json
    status = data.get('weekly_paid_status', 0)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT cycle_amount, share_count, paid_amount, telegram_id, first_name, ref_no, weekly_paid_status FROM equb_members WHERE id=?", (member_id,))
    row = cursor.fetchone()
    if row:
        if status == 1 and row['weekly_paid_status'] == 1:
            conn.close()
            return jsonify({"status": "already_approved", "message": "ይህ ክፍያ አስቀድሞ ጸድቋል!"})

        cycle_amt = row['cycle_amount']
        share_cnt = row['share_count']
        curr_paid = row['paid_amount']
        add_pay = cycle_amt * share_cnt
        new_paid = curr_paid + add_pay if status == 1 else max(0, curr_paid - add_pay)
        
        cursor.execute("UPDATE equb_members SET weekly_paid_status=?, paid_amount=? WHERE id=?", (status, new_paid, member_id))
        
        if status == 1:
            cursor.execute("SELECT current_week FROM equb_settings WHERE id=1")
            cw = cursor.fetchone()['current_week']
            cursor.execute('''
                INSERT INTO payment_transactions (member_id, ref_no, week_number, amount, status)
                VALUES (?, ?, ?, ?, 'Approved')
            ''', (member_id, row['ref_no'], cw, add_pay))

        conn.commit()

        if row['telegram_id']:
            msg = f"✅ <b>የዚህ ሳምንት ክፍያዎ ({add_pay:,.2f} ብር) በአድሚኑ ተረጋግጦ ጸድቋል!</b>" if status == 1 else "⚠️ <b>የዚህ ሳምንት ክፍያዎ አልተከፈለም ተብሎ ተስተካክሏል።</b>"
            send_telegram_message(row['telegram_id'], f"👋 ሰላም {row['first_name']} (Ref: {row['ref_no']}),\n\n{msg}")

    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/admin/send_direct_msg', methods=['POST'])
def send_direct_msg():
    data = request.json
    telegram_id = data.get('telegram_id')
    message = data.get('message')
    if not telegram_id or not message: return jsonify({"status": "error", "message": "መረጃው አልተሟላም"}), 400

    send_telegram_message(telegram_id, f"📩 <b>ከአድሚን የተላከ መልእክት፦</b>\n\n{message}")
    return jsonify({"status": "success"})

@app.route('/api/admin/notify_unpaid', methods=['POST'])
def notify_unpaid():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT current_week FROM equb_settings WHERE id=1")
    curr_week = cursor.fetchone()['current_week']
    cursor.execute("SELECT telegram_id, first_name, cycle_amount, share_count, ref_no FROM equb_members WHERE status='Approved' AND weekly_paid_status=0 AND telegram_id != '' AND telegram_id IS NOT NULL")
    unpaid_members = cursor.fetchall()
    conn.close()

    count = 0
    for m in unpaid_members:
        msg = f"⚠️ <b>ማሳሰቢያ፦ የሳምንት {curr_week} የዕቁብ ክፍያ!</b>\n\nሰላም <b>{m['first_name']}</b> (Ref: {m['ref_no']})፣ ክፍያዎ አልተመዘገበም።\n💰 ክፍያ መጠን፦ <b>{m['cycle_amount'] * m['share_count']:,.2f} ብር</b>"
        send_telegram_message(m['telegram_id'], msg)
        count += 1

    return jsonify({"status": "success", "notified_count": count})

@app.route('/api/admin/update_draw', methods=['POST'])
def update_draw():
    data = request.json
    draw_num = data.get('draw_number')
    draw_date = data.get('draw_date')
    week = data.get('current_week')
    winner = data.get('winner_name')
    broadcast = data.get('broadcast', False)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE equb_settings SET latest_draw_number=?, latest_draw_date=?, current_week=?, winner_name=? WHERE id=1", (draw_num, draw_date, week, winner))
    
    # Auto-reset weekly paid status for new week draw
    cursor.execute("UPDATE equb_members SET weekly_paid_status=0")
    conn.commit()

    if broadcast:
        cursor.execute("SELECT first_name, ref_no, weekly_paid_status FROM equb_members WHERE status='Approved'")
        all_members = cursor.fetchall()
        paid_text = "\n".join([f"• {m['first_name']} ({m['ref_no']}) ✅" for m in all_members if m['weekly_paid_status'] == 1]) or "የለም"
        unpaid_text = "\n".join([f"• {m['first_name']} ({m['ref_no']}) ❌" for m in all_members if m['weekly_paid_status'] == 0]) or "የለም"

        announcement = (
            f"📣 <b>የ KOKETI ዕቁብ ሳምንት {week} መረጃ!</b>\n"
            f"🎲 <b>የወጣው ዕጣ ቁጥር:</b> <code>{draw_num}</code>\n"
            f"🏆 <b>የዕጣው ባለቤት:</b> <b>{winner}</b>\n"
            f"📆 <b>ቀን:</b> {draw_date}\n━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>የከፈሉ አባላት፦</b>\n{paid_text}\n\n"
            f"❌ <b>ያልከፈሉ አባላት፦</b>\n{unpaid_text}"
        )
        cursor.execute("SELECT DISTINCT telegram_id FROM equb_members WHERE status='Approved' AND telegram_id != '' AND telegram_id IS NOT NULL")
        for u in cursor.fetchall():
            send_telegram_message(u['telegram_id'], announcement)

    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/admin/broadcast_announcement', methods=['POST'])
def broadcast_announcement():
    data = request.json or {}
    message = data.get('message', '').strip()

    if not message:
        return jsonify({"status": "error", "message": "እባክዎን የሚላከውን መልእክት ያስገቡ!"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT telegram_id FROM equb_members WHERE status='Approved' AND telegram_id IS NOT NULL AND telegram_id != ''")
    members = cursor.fetchall()
    conn.close()

    if not members:
        return jsonify({"status": "error", "message": "መልእክት የሚላክላቸው የተመዘገቡ አባላት አልተገኙም!"}), 404

    formatted_msg = f"📢 <b>የአድሚን ማስታወቂያ፦</b>\n\n{message}"
    sent_count = 0

    for m in members:
        try:
            res = send_telegram_message(m['telegram_id'], formatted_msg)
            if res and res.get('ok'):
                sent_count += 1
            time.sleep(0.05)
        except Exception as e:
            print(f"Failed to send broadcast to {m['telegram_id']}: {e}")

    return jsonify({
        "status": "success",
        "message": f"ማስታወቂያው ለ {sent_count} አባላት በስኬት ተላከ!",
        "sent_count": sent_count
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
