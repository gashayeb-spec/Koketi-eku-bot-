import os
import sqlite3
import random
import string
import requests
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder='.', static_folder='.')

# ================= Configuration =================
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # <-- እዚህ ላይ የቦትህን Token ተካ
ADMIN_CHAT_ID = "YOUR_ADMIN_CHAT_ID"    # <-- እዚህ ላይ የአድሚኑን Telegram Chat ID ተካ
WEBAPP_URL = "https://your-domain.com"  # <-- እዚህ ላይ የዌብሳይትህን አድራሻ (Domain/Render/ngrok URL) ተካ
DATABASE = 'database.db'

# ================= Database Initialization =================
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Members Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_no TEXT UNIQUE,
            telegram_id TEXT,
            first_name TEXT,
            father_name TEXT,
            grand_name TEXT,
            phone_number TEXT,
            region_select TEXT,
            gps_location TEXT,
            share_count INTEGER,
            cycle_amount REAL,
            paid_amount REAL DEFAULT 0,
            payment_method TEXT,
            receipt_path TEXT,
            referred_by TEXT,
            status TEXT DEFAULT 'Pending',
            weekly_paid_status INTEGER DEFAULT 0,
            member_cheque TEXT DEFAULT '-',
            guarantor_name TEXT DEFAULT '-',
            guarantor_cheque TEXT DEFAULT '-',
            collateral_item TEXT DEFAULT '-'
        )
    ''')

    # Settings Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            admin_password TEXT DEFAULT 'Koketi2026@',
            max_members INTEGER DEFAULT 100,
            registration_status TEXT DEFAULT 'OPEN',
            current_week INTEGER DEFAULT 1,
            latest_draw_number TEXT DEFAULT '',
            latest_draw_date TEXT DEFAULT '',
            winner_name TEXT DEFAULT '',
            current_otp TEXT DEFAULT ''
        )
    ''')

    cursor.execute('''
        INSERT OR IGNORE INTO settings (id, admin_password, max_members, registration_status, current_week)
        VALUES (1, 'Koketi2026@', 100, 'OPEN', 1)
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ================= Helper Functions =================
def send_telegram_msg(chat_id, text, reply_markup=None):
    if not BOT_TOKEN or "YOUR_TELEGRAM" in BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")

def send_telegram_photo(chat_id, photo_path, caption, reply_markup=None):
    if not BOT_TOKEN or "YOUR_TELEGRAM" in BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
            if reply_markup:
                import json
                data['reply_markup'] = json.dumps(reply_markup)
            requests.post(url, data=data, files=files, timeout=10)
    except Exception as e:
        print(f"Telegram photo error: {e}")

# ================= Routes & Web Pages =================
@app.route('/')
def index_page():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ================= Public Frontend APIs =================
@app.route('/api/member_info/<telegram_id>', methods=['GET'])
def get_member_info(telegram_id):
    conn = get_db()
    cursor = conn.cursor()
    
    members = cursor.execute('SELECT * FROM members WHERE telegram_id = ?', (telegram_id,)).fetchall()
    settings = cursor.execute('SELECT * FROM settings WHERE id = 1').fetchone()
    total_approved = cursor.execute("SELECT COUNT(*) FROM members WHERE status = 'Approved'").fetchone()[0]
    
    conn.close()

    members_list = [dict(m) for m in members]
    return jsonify({
        'members': members_list,
        'settings': dict(settings) if settings else {},
        'total_approved': total_approved
    })

@app.route('/api/register', methods=['POST'])
def register():
    conn = get_db()
    cursor = conn.cursor()
    
    settings = cursor.execute('SELECT * FROM settings WHERE id = 1').fetchone()
    total_approved = cursor.execute("SELECT COUNT(*) FROM members WHERE status = 'Approved'").fetchone()[0]
    
    if settings['registration_status'] == 'CLOSED' or total_approved >= settings['max_members']:
        conn.close()
        return jsonify({'message': 'ምዝገባው ተዘግቷል!'}), 400

    ref_no = request.form.get('ref_no')
    telegram_id = request.form.get('telegram_id')
    first_name = request.form.get('first_name')
    father_name = request.form.get('father_name')
    grand_name = request.form.get('grand_name')
    phone_number = request.form.get('phone_number')
    region_select = request.form.get('region_select')
    gps_location = request.form.get('gps_location')
    share_count = int(request.form.get('share_count', 1))
    cycle_amount = float(request.form.get('cycle_amount', 5000))
    payment_method = request.form.get('payment_method')
    referred_by = request.form.get('referred_by', '-')

    receipt = request.files.get('receipt')
    receipt_filename = '-'
    if receipt:
        receipt_filename = f"reg_{ref_no}_{secure_filename(receipt.filename)}"
        receipt.save(os.path.join(app.config['UPLOAD_FOLDER'], receipt_filename))

    cursor.execute('''
        INSERT INTO members (ref_no, telegram_id, first_name, father_name, grand_name, phone_number,
                             region_select, gps_location, share_count, cycle_amount, payment_method,
                             receipt_path, referred_by, status, weekly_paid_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', 0)
    ''', (ref_no, telegram_id, first_name, father_name, grand_name, phone_number,
          region_select, gps_location, share_count, cycle_amount, payment_method,
          receipt_filename, referred_by))

    member_id = cursor.lastrowid
    conn.commit()
    conn.close()

    caption = f"<b>📝 አዲስ የምዝገባ ማመልከቻ!</b>\n\n" \
              f"👤 <b>ስም:</b> {first_name} {father_name}\n" \
              f"📌 <b>Ref No:</b> {ref_no}\n" \
              f"📞 <b>ስልክ:</b> {phone_number}\n" \
              f"🎲 <b>ዕጣ:</b> {share_count}\n" \
              f"💵 <b>ክፍያ:</b> {payment_method}\n" \
              f"🔗 <b>Invited By:</b> {referred_by}"

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ አጽድቅ (Approve)", "callback_data": f"approve_reg_{member_id}"},
                {"text": "❌ ውድቅ አድርግ (Reject)", "callback_data": f"reject_reg_{member_id}"}
            ]
        ]
    }

    if receipt_filename != '-':
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], receipt_filename)
        send_telegram_photo(ADMIN_CHAT_ID, photo_path, caption, reply_markup)
    else:
        send_telegram_msg(ADMIN_CHAT_ID, caption, reply_markup)

    return jsonify({'message': 'ምዝገባው ተልኳል!'}), 200

@app.route('/api/upload_weekly_receipt', methods=['POST'])
def upload_weekly_receipt():
    member_id = request.form.get('member_id')
    receipt = request.files.get('receipt')

    if not member_id or not receipt:
        return jsonify({'message': 'ጎደሎ መረጃ!'}), 400

    conn = get_db()
    cursor = conn.cursor()
    member = cursor.execute('SELECT * FROM members WHERE id = ?', (member_id,)).fetchone()

    if not member:
        conn.close()
        return jsonify({'message': 'አባሉ አልተገኘም!'}), 404

    receipt_filename = f"weekly_{member['ref_no']}_{secure_filename(receipt.filename)}"
    photo_path = os.path.join(app.config['UPLOAD_FOLDER'], receipt_filename)
    receipt.save(photo_path)

    cursor.execute('UPDATE members SET receipt_path = ? WHERE id = ?', (receipt_filename, member_id))
    conn.commit()
    conn.close()

    caption = f"<b>🧾 አዲስ ሳምንታዊ የክፍያ ስክሪንሹት!</b>\n\n" \
              f"👤 <b>ስም:</b> {member['first_name']} {member['father_name']}\n" \
              f"📌 <b>Ref No:</b> {member['ref_no']}\n" \
              f"🎲 <b>ዕጣ:</b> {member['share_count']}"

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ ክፍያውን አጽድቅ", "callback_data": f"approve_pay_{member_id}"},
                {"text": "❌ ውድቅ አድርግ", "callback_data": f"reject_pay_{member_id}"}
            ]
        ]
    }

    send_telegram_photo(ADMIN_CHAT_ID, photo_path, caption, reply_markup)
    return jsonify({'message': 'ስክሪንሹቱ ተልኳል!'}), 200

# ================= Admin APIs =================
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    password = data.get('password')

    conn = get_db()
    settings = conn.cursor().execute('SELECT admin_password FROM settings WHERE id = 1').fetchone()
    conn.close()

    if settings and settings['admin_password'] == password:
        return jsonify({'message': 'Login successful!'}), 200
    return jsonify({'message': 'ትክክል ያልሆነ የይለፍ ቃል!'}), 401

@app.route('/api/admin/request_otp', methods=['POST'])
def request_otp():
    otp = ''.join(random.choices(string.digits, k=6))
    conn = get_db()
    conn.cursor().execute('UPDATE settings SET current_otp = ? WHERE id = 1', (otp,))
    conn.commit()
    conn.close()

    send_telegram_msg(ADMIN_CHAT_ID, f"<b>🔑 የአድሚን ፓስወርድ መቀየሪያ OTP፦</b> <code>{otp}</code>")
    return jsonify({'message': 'OTP ወደ አድሚን ቴሌግራም ተልኳል!'}), 200

@app.route('/api/admin/reset_password', methods=['POST'])
def reset_password():
    data = request.json
    otp = data.get('otp')
    new_password = data.get('new_password')

    conn = get_db()
    cursor = conn.cursor()
    settings = cursor.execute('SELECT current_otp FROM settings WHERE id = 1').fetchone()

    if settings and settings['current_otp'] == otp and len(new_password) >= 6:
        cursor.execute('UPDATE settings SET admin_password = ?, current_otp = "" WHERE id = 1', (new_password,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'ፓስወርድ በስኬት ተቀይሯል!'}), 200
    
    conn.close()
    return jsonify({'message': 'ትክክል ያልሆነ OTP ወይም ደካማ ፓስወርድ!'}), 400

@app.route('/api/admin/members', methods=['GET'])
def admin_members():
    conn = get_db()
    cursor = conn.cursor()

    members = cursor.execute('SELECT * FROM members ORDER BY id DESC').fetchall()
    settings = cursor.execute('SELECT * FROM settings WHERE id = 1').fetchone()

    total_registered = len(members)
    total_approved = sum(1 for m in members if m['status'] == 'Approved')
    total_pending = sum(1 for m in members if m['status'] == 'Pending')
    total_blocked = sum(1 for m in members if m['status'] == 'Blocked')
    total_paid_sum = sum(m['paid_amount'] for m in members if m['paid_amount'])

    conn.close()

    return jsonify({
        'members': [dict(m) for m in members],
        'settings': dict(settings) if settings else {},
        'stats': {
            'total_registered': total_registered,
            'total_approved': total_approved,
            'total_pending': total_pending,
            'total_blocked': total_blocked,
            'total_paid_sum': total_paid_sum
        }
    })

@app.route('/api/admin/change_status/<int:member_id>', methods=['POST'])
def change_status(member_id):
    new_status = request.json.get('status')
    conn = get_db()
    cursor = conn.cursor()
    
    member = cursor.execute('SELECT * FROM members WHERE id = ?', (member_id,)).fetchone()
    if member:
        cursor.execute('UPDATE members SET status = ? WHERE id = ?', (new_status, member_id))
        conn.commit()
        
        if new_status == 'Approved' and member['telegram_id']:
            send_telegram_msg(member['telegram_id'], f"🎉 <b>እንኳን ደስ አለዎት!</b>\n\nበ KOKETI ዕቁብ የ Ref No: <b>{member['ref_no']}</b> አካውንትዎ በአድሚኑ ጸድቋል!")
        elif new_status in ['Blocked', 'Cancelled'] and member['telegram_id']:
            send_telegram_msg(member['telegram_id'], f"⚠️ <b>የአካውንት ማሳወቂያ!</b>\n\nየ Ref No: <b>{member['ref_no']}</b> አካውንትዎ ሁኔታ ወደ <b>{new_status}</b> ተቀይሯል።")

    conn.close()
    return jsonify({'message': 'ሁኔታው ተቀይሯል!'})

@app.route('/api/admin/delete_member/<int:member_id>', methods=['DELETE'])
def delete_member(member_id):
    conn = get_db()
    conn.cursor().execute('DELETE FROM members WHERE id = ?', (member_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'አባሉ ተሰርዟል!'})

@app.route('/api/admin/toggle_payment/<int:member_id>', methods=['POST'])
def toggle_payment(member_id):
    weekly_paid_status = request.json.get('weekly_paid_status')
    conn = get_db()
    cursor = conn.cursor()
    
    member = cursor.execute('SELECT * FROM members WHERE id = ?', (member_id,)).fetchone()
    if member:
        single_cycle_total = member['cycle_amount'] * member['share_count']
        
        if weekly_paid_status == 1 and member['weekly_paid_status'] == 0:
            new_paid = member['paid_amount'] + single_cycle_total
            cursor.execute('UPDATE members SET weekly_paid_status = 1, paid_amount = ? WHERE id = ?', (new_paid, member_id))
            if member['telegram_id']:
                send_telegram_msg(member['telegram_id'], f"✅ <b>የክፍያ ማረጋገጫ!</b>\n\nለ Ref No: <b>{member['ref_no']}</b> የዚህ ሳምንት ክፍያ በስኬት ተረጋግጧል!")
        elif weekly_paid_status == 0 and member['weekly_paid_status'] == 1:
            new_paid = max(0, member['paid_amount'] - single_cycle_total)
            cursor.execute('UPDATE members SET weekly_paid_status = 0, paid_amount = ? WHERE id = ?', (new_paid, member_id))

        conn.commit()

    conn.close()
    return jsonify({'message': 'የክፍያ ሁኔታው ተስተካክሏል!'})

@app.route('/api/admin/update_guarantor/<int:member_id>', methods=['POST'])
def update_guarantor(member_id):
    data = request.json
    conn = get_db()
    conn.cursor().execute('''
        UPDATE members SET member_cheque = ?, guarantor_name = ?, guarantor_cheque = ?, collateral_item = ?
        WHERE id = ?
    ''', (data.get('member_cheque'), data.get('guarantor_name'), data.get('guarantor_cheque'), data.get('collateral_item'), member_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'የዋስትና መረጃው ተመዝግቧል!'})

@app.route('/api/admin/update_registration_settings', methods=['POST'])
def update_registration_settings():
    data = request.json
    conn = get_db()
    conn.cursor().execute('UPDATE settings SET max_members = ?, registration_status = ? WHERE id = 1',
                          (data.get('max_members'), data.get('registration_status')))
    conn.commit()
    conn.close()
    return jsonify({'message': 'የምዝገባ ገደቡ ተስተካክሏል!'})

@app.route('/api/admin/notify_unpaid', methods=['POST'])
def notify_unpaid():
    conn = get_db()
    unpaid_members = conn.cursor().execute("SELECT * FROM members WHERE status = 'Approved' AND weekly_paid_status = 0").fetchall()
    conn.close()

    count = 0
    for m in unpaid_members:
        if m['telegram_id']:
            msg = f"⚠️ <b>አጣዳፊ የክፍያ ማሳሰቢያ!</b>\n\n" \
                  f"ሰላም {m['first_name']}፣ የ Ref No: <b>{m['ref_no']}</b> የዚህ ሳምንት የዕቁብ ክፍያ አልተከፈለም። " \
                  f"እባክዎን ክፍያውን ፈጽመው ስክሪንሹት በቦቱ ይላኩ።"
            send_telegram_msg(m['telegram_id'], msg)
            count += 1

    return jsonify({'notified_count': count})

@app.route('/api/admin/update_draw', methods=['POST'])
def update_draw():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE settings SET latest_draw_number = ?, latest_draw_date = ?, current_week = ?, winner_name = ?
        WHERE id = 1
    ''', (data.get('draw_number'), data.get('draw_date'), data.get('current_week'), data.get('winner_name')))

    if data.get('broadcast'):
        members = cursor.execute("SELECT * FROM members WHERE status = 'Approved'").fetchall()
        
        draw_msg = f"📢 <b>የ KOKETI ዕቁብ ማስታወቂያ (ሳምንት {data.get('current_week')})!</b>\n\n" \
                   f"🎲 <b>የወጣው ዕጣ ቁጥር:</b> {data.get('draw_number')}\n" \
                   f"🏆 <b>የዕጣው ባለቤት:</b> {data.get('winner_name')}\n" \
                   f"📅 <b>ቀን:</b> {data.get('draw_date')}\n\n" \
                   f"መልካም እድል ለሁሉም አባላት!"

        for m in members:
            if m['telegram_id']:
                send_telegram_msg(m['telegram_id'], draw_msg)
        
        cursor.execute("UPDATE members SET weekly_paid_status = 0")

    conn.commit()
    conn.close()
    return jsonify({'message': 'የዕጣ መረጃው ተመዝግቧል!'})

@app.route('/api/admin/send_direct_msg', methods=['POST'])
def send_direct_msg():
    data = request.json
    send_telegram_msg(data.get('telegram_id'), f"📩 <b>ከአድሚኑ የተላከ መልእክት፦</b>\n\n{data.get('message')}")
    return jsonify({'message': 'መልእክቱ ተልቋል!'})

# ================= Telegram Webhook / Message & Callback Handler =================
@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    data = request.json
    
    # 1. Handle Messages (including /start command)
    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        if text.startswith("/start"):
            ref_code = "-"
            parts = text.split()
            if len(parts) > 1 and parts[1].startswith("ref_"):
                ref_code = parts[1].replace("ref_", "")

            welcome_text = "<b>🍷 እንኳን ወደ KOKETI KURT & LOUNGE የዲጂታል ዕቁብ ቦት በደህና መጡ!</b>\n\n" \
                           "እባክዎን ከታች ያለውን <b>'📱 የዕቁብ ገጽ ክፈት'</b> የሚለውን ባተን በመጫን ይመዝገቡ ወይም የዕቁብ ደብተርዎን ይመልከቱ።"

            webapp_link = f"{WEBAPP_URL}/?ref={ref_code}" if ref_code != "-" else WEBAPP_URL

            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "📱 የዕቁብ ገጽ ክፈት (Open WebApp)", "web_app": {"url": webapp_link}}
                    ]
                ]
            }
            send_telegram_msg(chat_id, welcome_text, reply_markup)

    # 2. Handle Inline Button Callbacks (Approve / Reject)
    elif "callback_query" in data:
        cb = data["callback_query"]
        cb_id = cb["id"]
        cb_data = cb["data"]

        conn = get_db()
        cursor = conn.cursor()

        # Handle Approve Registration
        if cb_data.startswith("approve_reg_"):
            m_id = int(cb_data.split("_")[2])
            m = cursor.execute('SELECT * FROM members WHERE id = ?', (m_id,)).fetchone()
            if m and m['status'] != 'Approved':
                cursor.execute("UPDATE members SET status = 'Approved' WHERE id = ?", (m_id,))
                conn.commit()
                send_telegram_msg(ADMIN_CHAT_ID, f"✅ ምዝገባ Ref No: {m['ref_no']} በስኬት ጸድቋል!")
                if m['telegram_id']:
                    send_telegram_msg(m['telegram_id'], f"🎉 <b>እንኳን ደስ አለዎት!</b>\n\nየ Ref No: <b>{m['ref_no']}</b> አባልነትዎ ጸድቋል!")

        # Handle Reject Registration
        elif cb_data.startswith("reject_reg_"):
            m_id = int(cb_data.split("_")[2])
            m = cursor.execute('SELECT * FROM members WHERE id = ?', (m_id,)).fetchone()
            if m:
                cursor.execute("UPDATE members SET status = 'Cancelled' WHERE id = ?", (m_id,))
                conn.commit()
                send_telegram_msg(ADMIN_CHAT_ID, f"❌ ምዝገባ Ref No: {m['ref_no']} ውድቅ ተደርጓል!")
                if m['telegram_id']:
                    send_telegram_msg(m['telegram_id'], f"❌ <b>የምዝገባ ውድቅ ማሳወቂያ!</b>\n\nየ Ref No: <b>{m['ref_no']}</b> ምዝገባዎ በስህተት ወይም በጎደሎ መረጃ ምክንያት ውድቅ ተደርጓል።")

        # Handle Approve Payment
        elif cb_data.startswith("approve_pay_"):
            m_id = int(cb_data.split("_")[2])
            m = cursor.execute('SELECT * FROM members WHERE id = ?', (m_id,)).fetchone()
            if m and m['weekly_paid_status'] == 0:
                add_amount = m['cycle_amount'] * m['share_count']
                new_paid = m['paid_amount'] + add_amount
                cursor.execute("UPDATE members SET weekly_paid_status = 1, paid_amount = ? WHERE id = ?", (new_paid, m_id))
                conn.commit()
                send_telegram_msg(ADMIN_CHAT_ID, f"✅ የክፍያ ስክሪንሹት Ref No: {m['ref_no']} ጸድቋል!")
                if m['telegram_id']:
                    send_telegram_msg(m['telegram_id'], f"✅ <b>የክፍያ ማረጋገጫ!</b>\n\nለ Ref No: <b>{m['ref_no']}</b> የላኩት ስክሪንሹት ተቀባይነት አግኝቶ ተመዝግቧል።")

        # Handle Reject Payment
        elif cb_data.startswith("reject_pay_"):
            m_id = int(cb_data.split("_")[2])
            m = cursor.execute('SELECT * FROM members WHERE id = ?', (m_id,)).fetchone()
            if m:
                send_telegram_msg(ADMIN_CHAT_ID, f"❌ የክፍያ ስክሪንሹት Ref No: {m['ref_no']} ውድቅ ተደርጓል!")
                if m['telegram_id']:
                    send_telegram_msg(m['telegram_id'], f"❌ <b>የክፍያ ውድቅ ማሳወቂያ!</b>\n\nለ Ref No: <b>{m['ref_no']}</b> የላኩት ስክሪንሹት ተቀባይነት አላገኘም። እባክዎን ትክክለኛውን ደረሰኝ እንደገና ይላኩ።")

        conn.close()
        requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", json={"callback_query_id": cb_id})

    return "OK", 200

# ================= Run Server =================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
