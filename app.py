import os
import sqlite3
import json
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8932085001:AAFSuqyjALyhumCO-Y6RwfHlwz1HJaugevU")
ADMIN_ID = os.environ.get("ADMIN_ID", "5351353727")
WEB_APP_URL = os.environ.get("WEB_APP_URL", "https://koketi-eku-bot-1.onrender.com")
DB_PATH = os.environ.get("DB_PATH", "koketi_equb.db")

UPLOAD_FOLDER = os.path.join('.', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equb_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            total_target_amount REAL DEFAULT 2000000,
            latest_draw_number TEXT DEFAULT 'አልወጣም',
            latest_draw_date TEXT DEFAULT '-',
            current_week INTEGER DEFAULT 1,
            winner_name TEXT DEFAULT '-',
            max_members INTEGER DEFAULT 100,
            registration_status TEXT DEFAULT 'OPEN'
        )
    ''')
    cursor.execute('INSERT OR IGNORE INTO equb_settings (id, total_target_amount, max_members, registration_status) VALUES (1, 2000000, 100, "OPEN")')
    
    # Check if receipt_path column exists in existing DB
    cursor.execute("PRAGMA table_info(equb_members)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'receipt_path' not in columns:
        cursor.execute("ALTER TABLE equb_members ADD COLUMN receipt_path TEXT DEFAULT '-'")
        
    conn.commit()
    conn.close()

init_db()

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        print(f"Telegram Msg Error: {e}")
        return None

def send_telegram_photo(chat_id, photo_path, caption, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            if reply_markup:
                payload["reply_markup"] = json.dumps(reply_markup)
            files = {"photo": photo}
            res = requests.post(url, data=payload, files=files, timeout=15)
            return res.json()
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

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.json
    if not update:
        return jsonify({"status": "ok"}), 200

    # 1. Handle Inline Button Clicks (Approval & Payment Approvals)
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        cb_data = cb.get("data", "")
        from_id = cb["from"]["id"]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if cb_data.startswith("approve_m_"):
            m_id = cb_data.replace("approve_m_", "")
            cursor.execute("UPDATE equb_members SET status='Approved' WHERE id=?", (m_id,))
            cursor.execute("SELECT telegram_id, first_name, ref_no FROM equb_members WHERE id=?", (m_id,))
            row = cursor.fetchone()
            conn.commit()
            if row and row[0]:
                send_telegram_message(row[0], f"🎉 <b>እንኳን ደስ አለዎት {row[1]}!</b>\n\nየዕቁብ ምዝገባዎ በአድሚን ጸድቋል። የመዝገብ ቁጥርዎ: <b>{row[2]}</b>")
            
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "አባሉ በስኬት ጸድቋል!"})

        elif cb_data.startswith("reject_m_"):
            m_id = cb_data.replace("reject_m_", "")
            cursor.execute("UPDATE equb_members SET status='Cancelled' WHERE id=?", (m_id,))
            cursor.execute("SELECT telegram_id, first_name FROM equb_members WHERE id=?", (m_id,))
            row = cursor.fetchone()
            conn.commit()
            if row and row[0]:
                send_telegram_message(row[0], f"🚫 <b>ሰላም {row[1]}፣</b>\n\nየዕቁብ ምዝገባዎ ውድቅ ተደርጓል።")
            
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "ምዝገባው ውድቅ ተደርጓል!"})

        elif cb_data.startswith("approve_pay_"):
            m_id = cb_data.replace("approve_pay_", "")
            cursor.execute("UPDATE equb_members SET weekly_paid_status=1 WHERE id=?", (m_id,))
            cursor.execute("SELECT telegram_id, first_name FROM equb_members WHERE id=?", (m_id,))
            row = cursor.fetchone()
            conn.commit()
            if row and row[0]:
                send_telegram_message(row[0], f"✅ <b>ሰላም {row[1]}፣</b>\n\nየላኩት የሳምንቱ ክፍያ ስክሪንሹት ተረጋግጦ ጸድቋል! አመሰግናለሁ።")
            
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id, "text": "የሳምንቱ ክፍያ ተጸድቋል!"})

        conn.close()
        return jsonify({"status": "ok"}), 200

    # 2. Handle Text Commands (/start)
    if "message" in update:
        chat_id = str(update["message"]["chat"]["id"])
        text = update["message"].get("text", "")

        if text.startswith("/start"):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM equb_members WHERE status='Approved'")
            approved_count = cursor.fetchone()[0]

            cursor.execute("SELECT total_target_amount, latest_draw_number, latest_draw_date, current_week, winner_name FROM equb_settings WHERE id=1")
            sett = cursor.fetchone()
            target_amount, draw_num, draw_date, curr_week, winner = sett if sett else (2000000, 'አልወጣም', '-', 1, '-')

            cursor.execute("SELECT ref_no, first_name, cycle_amount, share_count, paid_amount, status, weekly_paid_status FROM equb_members WHERE telegram_id=?", (chat_id,))
            member = cursor.fetchone()
            conn.close()

            if member:
                ref_no, name, cycle_amt, shares, paid_amt, status, w_paid = member
                total_cycle = cycle_amt * shares
                remaining = max(0, total_cycle - paid_amt)
                paid_str = "✅ ተከፍሏል" if w_paid == 1 else "❌ አልተከፈለም"

                if status == 'Pending':
                    msg = (
                        f"👋 <b>ሰላም {name}!</b>\n\n"
                        f"📌 <b>የመዝገብ ቁጥር:</b> {ref_no}\n"
                        f"⏳ <b>የምዝገባ ሁኔታ:</b> <code>በአድሚን በመረጋገጥ ላይ (Pending)</code>\n\n"
                        f"<i>መረጃዎ እና ክፍያዎ ተረጋግጦ ሲጸድቅ የዕቁብ ደብተርዎ ይከፈታል።</i>"
                    )
                elif status == 'Blocked':
                    msg = f"⛔ <b>ሰላም {name}፣</b>\n\nየአባልነት አካውንትዎ በአድሚን <b>ታግዷል (Blocked)</b>።"
                elif status == 'Cancelled':
                    msg = f"🚫 <b>ሰላም {name}፣</b>\n\nየዕቁብ ምዝገባዎ <b>ተሰርዟል (Cancelled)</b>።"
                else:
                    msg = (
                        f"📖 <b>የ KOKETI ዕቁብ ደብተር (Passbook)</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 <b>አባል:</b> {name} ({ref_no})\n"
                        f"👥 <b>ጠቅላላ አባላት:</b> {approved_count}\n"
                        f"📅 <b>የአሁኑ ሳምንት:</b> ሳምንት {curr_week}\n"
                        f"📌 <b>የዚህ ሳምንት ክፍያዎት:</b> {paid_str}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🎲 <b>የሳምንቱ የወጣው ዕጣ ቁጥር:</b> {draw_num}\n"
                        f"🏆 <b>የዕጣው ባለቤት:</b> {winner}\n"
                        f"📅 <b>የዕጣ ቀን:</b> {draw_date}\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"💰 <b>የዕቁብ ዙር (በአንድ ዕጣ):</b> {cycle_amt:,.2f} ብር\n"
                        f"🔢 <b>የዕጣ ብዛት:</b> {shares} ዕጣ\n"
                        f"💵 <b>ጠቅላላ ክፍያዎ:</b> {total_cycle:,.2f} ብር\n"
                        f"✅ <b>እስካሁን የከፈሉት:</b> {paid_amt:,.2f} ብር\n"
                        f"🔻 <b>ቀሪ እዳዎ:</b> {remaining:,.2f} ብር"
                    )
            else:
                msg = (
                    "👋 <b>እንኳን ወደ KOKETI KURT & LOUNGE የዕቁብ አገልግሎት በሰላም መጡ!</b>\n\n"
                    f"👥 <b>ተመዝጋቢ አባላት:</b> {approved_count}\n"
                    f"📅 <b>የአሁኑ ሳምንት:</b> ሳምንት {curr_week}\n\n"
                    "እባክዎን ከታች ያለውን ቁልፍ በመጫን ይመዝገቡ።"
                )

            reply_markup = {
                "inline_keyboard": [[
                    {"text": "📝 የዕቁብ ገጽ / መመዝገቢያ", "web_app": {"url": WEB_APP_URL}}
                ]]
            }

            if chat_id == str(ADMIN_ID):
                reply_markup["inline_keyboard"].append([
                    {"text": "⚙️ የአድሚን መቆጣጠሪያ ፓናል", "web_app": {"url": f"{WEB_APP_URL}/admin"}}
                ])

            send_telegram_message(chat_id, msg, reply_markup)

    return jsonify({"status": "ok"}), 200

# ----------------- APIs FOR USER & ADMIN -----------------

@app.route('/api/member_info/<telegram_id>', methods=['GET'])
def get_member_info(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equb_members WHERE telegram_id=?", (telegram_id,))
    member = cursor.fetchone()
    
    cursor.execute("SELECT registration_status, max_members FROM equb_settings WHERE id=1")
    settings = dict(cursor.fetchone())
    
    cursor.execute("SELECT COUNT(*) as count FROM equb_members WHERE status='Approved'")
    total_approved = cursor.fetchone()['count']
    
    conn.close()
    
    return jsonify({
        "member": dict(member) if member else None,
        "registration_status": settings.get("registration_status", "OPEN"),
        "max_members": settings.get("max_members", 100),
        "total_approved": total_approved
    })

# አዲስ አባል መመዝገቢያ API
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

        receipt_file = request.files.get('receipt')
        receipt_filename = '-'
        filepath = None

        if receipt_file:
            receipt_filename = f"reg_{ref_no}_{receipt_file.filename}"
            filepath = os.path.join(UPLOAD_FOLDER, receipt_filename)
            receipt_file.save(filepath)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO equb_members (
                ref_no, telegram_id, first_name, father_name, grand_name,
                phone_number, gps_location, region, payment_method, cycle_amount,
                share_count, paid_amount, status, receipt_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'Pending', ?)
        ''', (
            ref_no, telegram_id, first_name, father_name, grand_name,
            phone_number, gps_location, region, payment_method, cycle_amount,
            share_count, receipt_filename
        ))
        
        member_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # ለአድሚን በቴሌግራም መላኪያ መልእክትና Inline Buttons
        msg_admin = (
            f"🔔 <b>አዲስ አባል ተመዝግቧል!</b>\n\n"
            f"🆔 <b>Ref No:</b> {ref_no}\n"
            f"👤 <b>ስም:</b> {first_name} {father_name} {grand_name}\n"
            f"📞 <b>ስልክ:</b> {phone_number}\n"
            f"📍 <b>ክልል:</b> {region}\n"
            f"🔢 <b>የዕጣ ብዛት:</b> {share_count}\n"
            f"💵 <b>የዕጣ ዙር:</b> {cycle_amount:,.2f} ብር\n"
            f"💳 <b>ክፍያ መንገድ:</b> {payment_method}"
        )

        inline_markup = {
            "inline_keyboard": [[
                {"text": "✅ አጽድቅ (Approve)", "callback_data": f"approve_m_{member_id}"},
                {"text": "❌ ውድቅ አድርግ", "callback_data": f"reject_m_{member_id}"}
            ]]
        }

        if filepath and os.path.exists(filepath):
            send_telegram_photo(ADMIN_ID, filepath, msg_admin, inline_markup)
        else:
            send_telegram_message(ADMIN_ID, msg_admin, inline_markup)

        return jsonify({"status": "success", "message": "ምዝገባው ተጠናቅቋል!"}), 200

    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "ይህ መዝገብ ቁጥር አስቀድሞ አለ!"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ሳምንታዊ ክፍያ ስክሪንሹት መላኪያ API
@app.route('/api/upload_weekly_receipt', methods=['POST'])
def upload_weekly_receipt():
    telegram_id = request.form.get('telegram_id')
    receipt_file = request.files.get('receipt')

    if not receipt_file or not telegram_id:
        return jsonify({"status": "error", "message": "ምንም ፋይል ወይም አባል አልተመረጠም"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equb_members WHERE telegram_id=?", (telegram_id,))
    member = cursor.fetchone()
    conn.close()

    if not member:
        return jsonify({"status": "error", "message": "የተመዘገበ አባል አልተገኘም"}), 404

    filename = f"weekly_{member['ref_no']}_{receipt_file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    receipt_file.save(filepath)

    caption = (
        f"🧾 <b>አዲስ የሳምንታዊ ክፍያ ስክሪንሹት ደርሷል!</b>\n\n"
        f"👤 <b>አባል:</b> {member['first_name']} {member['father_name']}\n"
        f"🔢 <b>Ref No:</b> {member['ref_no']}\n"
        f"📞 <b>ስልክ:</b> {member['phone_number']}\n"
        f"🎲 <b>የዕጣ ብዛት:</b> {member['share_count']}"
    )

    inline_markup = {
        "inline_keyboard": [[
            {"text": "✅ ክፍያውን አጽድቅ (Approve Payment)", "callback_data": f"approve_pay_{member['id']}"}
        ]]
    }

    send_telegram_photo(ADMIN_ID, filepath, caption, inline_markup)
    return jsonify({"status": "success", "message": "ስክሪንሹቱ ለአድሚኑ በስኬት ተልኳል!"}), 200

# ----------------- ADMIN MANAGEMENT APIs -----------------

@app.route('/api/admin/members', methods=['GET'])
def get_admin_members():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equb_members ORDER BY id DESC")
    members = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM equb_settings WHERE id=1")
    settings = dict(cursor.fetchone())
    conn.close()
    
    return jsonify({"members": members, "settings": settings})

@app.route('/api/admin/change_status/<int:member_id>', methods=['POST'])
def change_status(member_id):
    data = request.json
    new_status = data.get('status')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE equb_members SET status=? WHERE id=?", (new_status, member_id))
    cursor.execute("SELECT telegram_id, first_name, ref_no FROM equb_members WHERE id=?", (member_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()

    if row and row[0]:
        if new_status == 'Approved':
            send_telegram_message(row[0], f"🎉 <b>እንኳን ደስ አለዎት {row[1]}!</b>\n\nየመዝገብ ቁጥርዎ <b>{row[2]}</b> ተረጋግጦ ጸድቋል።")
        elif new_status == 'Blocked':
            send_telegram_message(row[0], f"⛔ <b>ሰላም {row[1]}፣</b>\n\nየአባልነት አካውንትዎ በአድሚን ታግዷል (Blocked)።")
        elif new_status == 'Cancelled':
            send_telegram_message(row[0], f"🚫 <b>ሰላም {row[1]}፣</b>\n\nየዕቁብ ምዝገባዎ ተሰርዟል (Cancelled)።")

    return jsonify({"status": "success"})

@app.route('/api/admin/delete_member/<int:member_id>', methods=['DELETE'])
def delete_member(member_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM equb_members WHERE id=?", (member_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "አባሉ ሙሉ በሙሉ ተሰርዟል"})

@app.route('/api/admin/update_registration_settings', methods=['POST'])
def update_registration_settings():
    data = request.json
    max_m = data.get('max_members', 100)
    reg_s = data.get('registration_status', 'OPEN')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE equb_settings SET max_members=?, registration_status=? WHERE id=1", (max_m, reg_s))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/admin/update_guarantor/<int:member_id>', methods=['POST'])
def update_guarantor(member_id):
    data = request.json
    conn = sqlite3.connect(DB_PATH)
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
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE equb_members SET weekly_paid_status=? WHERE id=?", (status, member_id))
    cursor.execute("SELECT telegram_id, first_name FROM equb_members WHERE id=?", (member_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()

    if row and row[0]:
        msg_type = "✅ <b>የዚህ ሳምንት ዕቁብ ክፍያዎ ተመዝግቧል!</b> አመሰግናለሁ።" if status == 1 else "⚠️ <b>የዚህ ሳምንት ክፍያዎ አልተከፈለም ተብሎ ተስተካክሏል።</b>"
        send_telegram_message(row[0], f"👋 ሰላም {row[1]},\n\n{msg_type}")

    return jsonify({"status": "success"})

@app.route('/api/admin/send_direct_msg', methods=['POST'])
def send_direct_msg():
    data = request.json
    telegram_id = data.get('telegram_id')
    message = data.get('message')

    if not telegram_id or not message:
        return jsonify({"status": "error", "message": "መረጃው አልተሟላም"}), 400

    send_telegram_message(telegram_id, f"📩 <b>ከአድሚን የተላከ መልእክት፦</b>\n\n{message}")
    return jsonify({"status": "success"})

@app.route('/api/admin/notify_unpaid', methods=['POST'])
def notify_unpaid():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT current_week FROM equb_settings WHERE id=1")
    curr_week = cursor.fetchone()[0]

    cursor.execute("SELECT telegram_id, first_name, cycle_amount, share_count FROM equb_members WHERE status='Approved' AND weekly_paid_status=0 AND telegram_id != ''")
    unpaid_members = cursor.fetchall()
    conn.close()

    count = 0
    for m in unpaid_members:
        msg = (
            f"⚠️ <b>ማሳሰቢያ፦ የሳምንት {curr_week} የዕቁብ ክፍያ!</b>\n\n"
            f"ሰላም <b>{m[1]}</b>፣\n"
            f"የዚህ ሳምንት (ሳምንት {curr_week}) የዕቁብ ክፍያዎ እስካሁን አልተመዘገበም። እባክዎን በወቅቱ ክፍያውን በመፈጸም ዕቁብዎን ያጽኑ።\n\n"
            f"💰 ክፍያ መጠን፦ <b>{m[2] * m[3]:,.2f} ብር</b>"
        )
        send_telegram_message(m[0], msg)
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

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE equb_settings 
        SET latest_draw_number=?, latest_draw_date=?, current_week=?, winner_name=? 
        WHERE id=1
    ''', (draw_num, draw_date, week, winner))
    conn.commit()

    if broadcast:
        cursor.execute("SELECT first_name, weekly_paid_status FROM equb_members WHERE status='Approved'")
        all_members = cursor.fetchall()
        
        paid_list = [f"• {name} ✅" for name, paid in all_members if paid == 1]
        unpaid_list = [f"• {name} ❌" for name, paid in all_members if paid == 0]

        paid_text = "\n".join(paid_list) if paid_list else "የለም"
        unpaid_text = "\n".join(unpaid_list) if unpaid_list else "የለም"

        announcement = (
            f"📣 <b>የ KOKETI ዕቁብ ሳምንት {week} ሙሉ መረጃ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎲 <b>የወጣው ዕጣ ቁጥር:</b> <code>{draw_num}</code>\n"
            f"🏆 <b>የዕጣው ባለቤት:</b> <b>{winner}</b>\n"
            f"📆 <b>የወጣበት ቀን:</b> {draw_date}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>የከፈሉ አባላት፦</b>\n{paid_text}\n\n"
            f"❌ <b>ያልከፈሉ (የቀሩ) አባላት፦</b>\n{unpaid_text}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👏 ለባለዕጣው እንኳን ደስ አለዎት!"
        )

        cursor.execute("SELECT telegram_id FROM equb_members WHERE status='Approved' AND telegram_id != ''")
        users = cursor.fetchall()
        for u in users:
            send_telegram_message(u[0], announcement)

    conn.close()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
