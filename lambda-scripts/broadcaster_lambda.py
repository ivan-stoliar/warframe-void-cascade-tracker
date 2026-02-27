import json
import os
import urllib.request
from datetime import datetime, timezone

# 1. Configuration
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

def send_telegram_message(chat_id, text):
    data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode('utf-8')
    req = urllib.request.Request(TELEGRAM_API_URL, data=data, headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Telegram error: {e}")

def supabase_request(endpoint, method='GET', payload=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        'apikey': SUPABASE_KEY, 'Authorization': f"Bearer {SUPABASE_KEY}",
        'Content-Type': 'application/json', 'Prefer': 'return=representation'
    }
    data = json.dumps(payload).encode('utf-8') if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Supabase error: {e}")
        return None

def calculate_eta(expiry_str):
    if not expiry_str: return "Unknown"
    try:
        expiry_dt = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
        diff = expiry_dt - datetime.now(timezone.utc)
        minutes = int(diff.total_seconds() // 60)
        if minutes <= 0: return "Expiring soon"
        return f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 else f"{minutes}m"
    except: return "Active"

def lambda_handler(event, context):
    # 2. Fetch PC Fissures
    api_url = "https://api.warframestat.us/pc/fissures"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0'}

    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            fissures = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"API Error: {e}")
        return {'statusCode': 403}

    # 3. Filter for Void Cascade (Tuvul Commons)
    cascades = [f for f in fissures if 'Cascade' in f.get('missionType', '') or 'Tuvul' in f.get('node', '')]

    for f in cascades:
        f_id = f['id']

        # 4. Duplicate Check
        if supabase_request(f"alert_history?fissure_id=eq.{f_id}"):
            continue

        # 5. HIGH-ACCURACY Steel Path Detection
        # We check flags, text, AND Enemy Level (Steel Path is always 100+)
        is_sp = (
            f.get('isHard') is True or
            f.get('hard') is True or
            "Steel Path" in f.get('tier', '') or
            "Hard" in f.get('missionKey', '') or
            f.get('minEnemyLevel', 0) >= 100  # THE ULTIMATE LEVEL CHECK
        )

        # DEBUG LOG: See what the levels are
        print(f"DEBUG - ID: {f_id} | Levels: {f.get('minEnemyLevel')}-{f.get('maxEnemyLevel')} | SP Detected: {is_sp}")

        node = f.get('node', 'Tuvul Commons')
        tier = f.get('tier', 'Unknown')
        enemy = f.get('enemy', 'Unknown')
        eta = calculate_eta(f.get('expiry'))

        # 6. Format Message
        header = "🚨 <b>STEEL PATH: VOID CASCADE</b> 🚨" if is_sp else "🚨 <b>VOID CASCADE ACTIVE</b> 🚨"

        message = (
            f"{header}\n\n"
            f"📍 <b>Node:</b> {node}\n"
            f"👾 <b>Faction:</b> {enemy}\n"
            f"💎 <b>Tier:</b> {tier} Relics\n"
            f"⏳ <b>Ends in:</b> {eta}"
        )

        # 7. Log to SQL
        supabase_request("alert_history", method="POST", payload={
            "fissure_id": f_id,
            "mission_type": "Void Cascade",
            "fissure_tier": tier,
            "node": node,
            "enemy_faction": enemy,
            "is_steel_path": bool(is_sp),
            "activation_time": f.get('activation'),
            "expiry_time": f.get('expiry')
        })

        # 8. Broadcast
        active_users = supabase_request("subscribers?status=eq.active")
        if active_users:
            for user in active_users:
                send_telegram_message(user['chat_id'], message)

    return {'statusCode': 200}
