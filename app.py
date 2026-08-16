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
            weekly_paid_status INTEGER DEFAULT 0, -- 0 = አልከፈለም, 1 = ከፍሏል
            member_cheque TEXT,
            guarantor_name TEXT,
            guarantor_cheque TEXT,
            collateral_item TEXT,
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
            winner_name TEXT DEFAULT '-'
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
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        print(f"Telegram error: {e}")
        return None

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/admin')
def admin_page():
    return send_from_directory('.', 'admin.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    update = request.json
    if update and "message" in update:
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

            # አድሚኑም ቢሆን የራሱ እቁብተኛ አካውንት ይኖረዋል
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
                        f"<i>መረጃዎ ተረጋግጦ ሲጸድቅ ዲጂታል የዕቁብ ደብተርዎ ይከፈታል።</i>"
                    )
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
                    {"text": "📝 የዕቁብ መመዝገቢያ ፎርም", "web_app": {"url": WEB_APP_URL}}
                ]]
            }

            # አድሚን ከሆነ የመቆጣጠሪያ ፓናሉን አብሮ ያያል
            if chat_id == str(ADMIN_ID):
                reply_markup["inline_keyboard"].append([
                    {"text": "⚙️ የአድሚን መቆጣጠሪያ ፓናል", "web_app": {"url": f"{WEB_APP_URL}/admin"}}
                ])

            send_telegram_message(chat_id, msg, reply_markup)

    return jsonify({"status": "ok"}), 200

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

@app.route('/api/admin/approve/<int:member_id>', methods=['POST'])
def approve_member(member_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE equb_members SET status='Approved' WHERE id=?", (member_id,))
    cursor.execute("SELECT telegram_id, first_name, ref_no FROM equb_members WHERE id=?", (member_id,))
    row = cursor.fetchone()
    conn.commit()
    conn.close()

    if row and row[0]:
        send_telegram_message(row[0], f"🎉 <b>እንኳን ደስ አለዎት {row[1]}!</b>\n\nየመዝገብ ቁጥርዎ <b>{row[2]}</b> ተረጋግጧል። አሁን /start በማለት የዕቁብ ደብተርዎን ማየት ይችላሉ።")

    return jsonify({"status": "success"})

@app.route('/api/admin/toggle_payment/<int:member_id>', methods=['POST'])
def toggle_payment(member_id):
    data = request.json
    status = data.get('weekly_paid_status', 0)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE equb_members SET weekly_paid_status=? WHERE id=?", (status, member_id))
    cursor.execute("SELECT telegram_id, first_name, cycle_amount, share_count FROM equb_members WHERE id=?", (member_id,))
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
        
        paid_list = []
        unpaid_list = []
        for name, paid in all_members:
            if paid == 1:
                paid_list.append(f"• {name} ✅")
            else:
                unpaid_list.append(f"• {name} ❌")

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
            f"👏 ለባለዕጣው እንኳን ደስ አለዎት! ቀጣዩን ዝርዝር በ /start ማየት ይችላሉ።"
        )

        cursor.execute("SELECT telegram_id FROM equb_members WHERE status='Approved' AND telegram_id != ''")
        users = cursor.fetchall()
        for u in users:
            send_telegram_message(u[0], announcement)

    conn.close()
    return jsonify({"status": "success"})

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
        share_count = int(data.get('share_count', 1))
        paid_amount = float(data.get('paid_amount', 0))
        member_cheque = data.get('member_cheque', '')
        guarantor_name = data.get('guarantor_name', '')
        guarantor_cheque = data.get('guarantor_cheque', '')
        collateral_item = data.get('collateral_item', '')

        cursor.execute('''
            INSERT INTO equb_members (
                ref_no, telegram_id, first_name, father_name, grand_name,
                phone_number, gps_location, region, payment_method, cycle_amount,
                share_count, paid_amount, member_cheque, guarantor_name,
                guarantor_cheque, collateral_item, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
        ''', (
            ref_no, telegram_id, first_name, father_name, grand_name,
            phone_number, gps_location, region, payment_method, cycle_amount,
            share_count, paid_amount, member_cheque, guarantor_name,
            guarantor_cheque, collateral_item
        ))
        
        conn.commit()
        conn.close()

        msg_admin = (
            f"🔔 <b>አዲስ አባል ተመዝግቧል!</b>\n\n"
            f"🆔 <b>Ref:</b> {ref_no}\n"
            f"👤 <b>ስም:</b> {first_name} {father_name}\n"
            f"📞 <b>ስልክ:</b> {phone_number}\n"
            f"🔢 <b>የዕጣ ብዛት:</b> {share_count}\n"
            f"💵 <b>ዙር:</b> {cycle_amount:,.2f} ብር"
        )
        send_telegram_message(ADMIN_ID, msg_admin)

        return jsonify({"status": "success", "message": "ምዝገባው ተጠናቅቋል!"}), 200

    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "ይህ መዝገብ ቁጥር አስቀድሞ አለ!"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
