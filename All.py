import warnings
warnings.filterwarnings("ignore")

import os
import time
import base64
import hashlib
import random
import string
import socket
import re
import requests
import telebot
import phonenumbers
from datetime import datetime
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from faker import Faker
from gtts import gTTS
from phonenumbers import carrier, geocoder
from flask import Flask
from threading import Thread

# =========================================
# CONFIGURATION
# =========================================
bot = telebot.TeleBot("8954334041:AAFO-qdDkVmknsh_e4SatjpDzn6bqj4swVA")

fk = Faker()
user_tempmail = {}

API_KEYS = {
    "vt": "b2059cd3b9c6ca6d84bc11e1d272675454153d92a0dbc54052df99b31c7fd364",
    "serp": "6f75416d78ef4f8b69fa73181136f92625fd25706604b912d6db4d81ce0432b5",
    "shodan": "f8FhmHfYXrAuHRHT5VdjV3stISGzn39w",
    "ipinfo": "c5b71db5f62783",
    "urlscan": "019e52a8-932a-7662-9885-94e6a4673e31"
}

def safe_req(url, method='GET', **kwargs):
    try:
        return requests.request(method, url, timeout=20, **kwargs)
    except:
        return type('Response', (object,), {'status_code': 500, 'text': 'Error', 'json': lambda: {}})()

def process_command(cmd, data, chat_id, raw_text):
    d = data.strip()
    u = d if d.startswith("http") else "https://" + d
    dm = d.replace("http://", "").replace("https://", "").split('/')[0].split(':')[0]
    
    try:
        if re.match(r"^\+?[0-9]{10,20}$", raw_text.replace(" ", "").replace("-", "")):
            p = phonenumbers.parse(raw_text, None)
            return f"📞 *Phone Info:*\nCountry: {geocoder.description_for_number(p, 'en')}\nCarrier: {carrier.name_for_number(p, 'en')}"

        if cmd in ["/start", "/help"]:
            return "⚡ *All OSINT Commands:*\n/ss, /sub, /whois, /shodan, /scan, /mac, /ipinfo, /myip, /vt, /urlscan, /serp, /pwned, /pass, /encode, /decode, /fake, /tempmail, /inbox, /qr, /speak, /short, /ping, /age\n*(Or type a Phone No)*"

        req_target = ["/ss", "/qr", "/speak", "/encode", "/decode", "/pwned", "/short", "/ping", "/sub", "/whois", "/mac", "/shodan", "/scan", "/age", "/vt", "/ipinfo", "/urlscan", "/serp"]
        if cmd in req_target and not d:
            return "⚠️ Please provide a target link, IP, or text!"

        if cmd == "/ss":
            return f"PIC:https://api.microlink.io/?url={quote(u)}&screenshot=true&meta=false&embed=screenshot.url"
            
        elif cmd == "/qr":
            return f"PIC:https://api.qrserver.com/v1/create-qr-code/?size=512x512&data={quote(d)}"
            
        elif cmd == "/speak":
            file_name = f"audio_{chat_id}.mp3"
            gTTS(d, lang='bn').save(file_name)
            return f"AUD:{file_name}"
            
        elif cmd == "/fake":
            return f"👤 *Fake ID:*\nName: {fk.name()}\nEmail: {fk.email()}\nPhone: {fk.phone_number()}\nAddress: {fk.address()}"
            
        elif cmd == "/pass":
            pwd = ''.join(random.choice(string.ascii_letters + string.digits + '!@#$%^&*') for _ in range(16))
            return f"🔐 *Secure Password:*\n`{pwd}`"
            
        elif cmd == "/encode":
            return f"🔒 *Encoded:*\n`{base64.b64encode(d.encode()).decode()}`"
            
        elif cmd == "/decode":
            return f"🔓 *Decoded:*\n`{base64.b64decode(d.encode()).decode()}`"
            
        elif cmd == "/pwned":
            h = hashlib.sha1(d.encode()).hexdigest().upper()
            res = safe_req(f"https://api.pwnedpasswords.com/range/{h[:5]}")
            count = next((int(line.split(':')[1]) for line in res.text.splitlines() if line.startswith(h[5:])), 0)
            return f"⚠️ *Leaked:* {count} times!" if count else "✅ *Safe password!*"
            
        elif cmd == "/short":
            res = safe_req(f"https://tinyurl.com/api-create.php?url={quote(d)}")
            return f"🔗 *Short URL:* {res.text}"
            
        elif cmd == "/ping":
            res = safe_req(f"https://{dm}")
            return f"📡 *{dm} is UP!*" if res.status_code < 500 else "❌ DOWN or Unreachable!"
            
        elif cmd == "/sub":
            res = safe_req(f"https://crt.sh/?q=%.{dm}&output=json")
            if res.status_code == 200 and res.text:
                subs = sorted(set([e.get('name_value', '') for e in res.json() if isinstance(e, dict)]))[:15]
                return "**Subdomains:**\n" + "\n".join(subs) if subs else "❌ No subdomains found"
            return "❌ API Error"
            
        elif cmd == "/whois":
            res = safe_req(f"https://api.hackertarget.com/whois/?q={dm}")
            return f"📝 *WHOIS:*\n{res.text[:1500]}" if res.status_code == 200 else "❌ Error"
            
        elif cmd == "/mac":
            mac = d.replace("-", ":").replace(".", ":")
            res = safe_req(f"https://api.macvendors.com/{mac}")
            return f"🖥️ *Vendor:* {res.text}" if res.status_code == 200 else "❌ Unknown MAC"
            
        elif cmd == "/shodan":
            try: ip = socket.gethostbyname(dm)
            except: return "❌ Invalid Host"
            res = safe_req(f"https://api.shodan.io/shodan/host/{ip}?key={API_KEYS['shodan']}")
            if res.status_code == 200:
                j = res.json()
                ports = ', '.join(str(p) for p in j.get('ports', [])[:10])
                return f"🌍 *Shodan:* {j.get('ip_str')}\nCountry: {j.get('country_name')}\nORG: {j.get('org')}\nPorts: {ports}"
            return "❌ Shodan Error"
            
        elif cmd == "/scan":
            try: ip = socket.gethostbyname(dm)
            except: return "❌ Invalid target"
            open_ports = []
            def check_port(p):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(0.5)
                        if s.connect_ex((ip, p)) == 0: open_ports.append(p)
                except: pass
            with ThreadPoolExecutor(10) as executor:
                executor.map(check_port, [21, 22, 23, 25, 53, 80, 110, 443, 3306, 3389, 8080])
            return f"🔓 *Open Ports:* {sorted(open_ports)}" if open_ports else "🔒 No common open ports"
            
        elif cmd == "/age":
            try:
                dob = datetime.strptime(d, "%Y-%m-%d")
                t = datetime.today()
                age = t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))
                return f"🎂 *Age:* {age} years"
            except: return "❌ Use YYYY-MM-DD format"
            
        elif cmd == "/vt":
            res = safe_req(f"https://www.virustotal.com/api/v3/domains/{dm}", headers={"x-apikey": API_KEYS["vt"]})
            if res.status_code == 200:
                s = res.json().get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                return f"🛡️ *VirusTotal:*\nMalicious: {s.get('malicious')}\nSuspicious: {s.get('suspicious')}\nHarmless: {s.get('harmless')}"
            return "❌ API Error"
            
        elif cmd == "/ipinfo":
            res = safe_req(f"https://ipinfo.io/{dm}/json?token={API_KEYS['ipinfo']}")
            if res.status_code == 200:
                j = res.json()
                return f"📍 *IP Info:*\nIP: {j.get('ip')}\nCity: {j.get('city')}\nCountry: {j.get('country')}\nORG: {j.get('org')}"
            return "❌ Not Found"
            
        elif cmd == "/urlscan":
            h = {"API-Key": API_KEYS["urlscan"], "Content-Type": "application/json"}
            res = safe_req("https://urlscan.io/api/v1/scan/", method="POST", json={"url": u, "visibility": "public"}, headers=h)
            if res.status_code == 200:
                return f"✅ *Submitted!*\nResult: {res.json().get('result', '')}"
            return "❌ API Error"
            
        elif cmd == "/serp":
            res = safe_req(f"https://serpapi.com/search?q={quote(d)}&api_key={API_KEYS['serp']}")
            if res.status_code == 200:
                results = res.json().get('organic_results', [])[:3]
                if results:
                    reply = "🔍 *Google Results:*\n\n"
                    for r in results: reply += f"🔹 {r.get('title')}\n{r.get('link')}\n\n"
                    return reply
            return "❌ No results"
            
        elif cmd == "/tempmail":
            res = safe_req("https://api.guerrillamail.com/ajax.php?f=get_email_address&ip=127.0.0.1&agent=Bot")
            if res.status_code == 200:
                j = res.json()
                user_tempmail[chat_id] = {'email': j.get('email_addr'), 'sid': j.get('sid_token')}
                return f"📧 *Temp Email:* `{user_tempmail[chat_id]['email']}`\n*(Use /inbox to check)*"
            return "❌ API Error"
            
        elif cmd == "/inbox":
            if chat_id not in user_tempmail: return "⚠️ Run `/tempmail` first"
            res = safe_req(f"https://api.guerrillamail.com/ajax.php?f=get_email_list&sid_token={user_tempmail[chat_id]['sid']}")
            if res.status_code == 200:
                emails = res.json().get('list', [])
                if emails:
                    reply = "📥 *Inbox:*\n\n"
                    for em in emails[:3]: reply += f"*From:* {em.get('mail_from')}\n*Sub:* {em.get('mail_subject')}\n\n"
                    return reply
                return "📭 Inbox is empty."
            return "❌ API Error"
            
        elif cmd == "/myip":
            res = safe_req("https://api.ipify.org?format=json")
            if res.status_code == 200: return f"🌐 *Server IP:* {res.json().get('ip')}"
            return "❌ Error"

        return "❌ Command not found."
        
    except Exception as e:
        return "❌ System Error or Request Timeout."

# =========================================
# WEB SERVER & MESSAGE HANDLER
# =========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

@bot.message_handler(func=lambda m: True)
def handle_msg(m):
    text = m.text.strip()
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    data = parts[1] if len(parts) > 1 else ""
    
    is_phone = bool(re.match(r"^\+?[0-9]{10,20}$", text.replace(" ", "").replace("-", "")))
    if not cmd.startswith("/") and not is_phone:
        return
        
    wait_msg = bot.reply_to(m, "🔄 Processing...")
    reply = process_command(cmd, data, m.chat.id, text)
    
    try:
        if reply.startswith("PIC:"):
            bot.send_photo(m.chat.id, reply[4:], reply_to_message_id=m.message_id)
            bot.delete_message(m.chat.id, wait_msg.message_id)
        elif reply.startswith("AUD:"):
            file_path = reply[4:]
            with open(file_path, 'rb') as audio:
                bot.send_audio(m.chat.id, audio, reply_to_message_id=m.message_id)
            os.remove(file_path)
            bot.delete_message(m.chat.id, wait_msg.message_id)
        else:
            bot.edit_message_text(reply, m.chat.id, wait_msg.message_id, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception:
        bot.edit_message_text("❌ Error sending message.", m.chat.id, wait_msg.message_id)

if __name__ == "__main__":
    server_thread = Thread(target=run_server)
    server_thread.start()
    print("✅ Web Server and Bot are ONLINE...")
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception:
            time.sleep(3)
