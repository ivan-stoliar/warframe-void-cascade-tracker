import json
import os
import urllib.request
from datetime import datetime, timezone

# ── Configuration ──────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
SUPABASE_URL   = os.environ.get('SUPABASE_URL')
SUPABASE_KEY   = os.environ.get('SUPABASE_KEY')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"


# ── Helpers ────────────────────────────────────────────────────────────────────
def send_telegram_message(chat_id, text):
    data = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }).encode('utf-8')
    req = urllib.request.Request(
        TELEGRAM_API_URL, data=data,
        headers={'Content-Type': 'application/json'}
    )
    try:
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Telegram error: {e}")


def supabase_request(endpoint, method='GET', payload=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f"Bearer {SUPABASE_KEY}",
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
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
    if not expiry_str:
        return "Unknown"
    try:
        expiry_dt = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
        diff      = expiry_dt - datetime.now(timezone.utc)
        minutes   = int(diff.total_seconds() // 60)
        if minutes <= 0:
            return "Expiring soon"
        return f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 else f"{minutes}m"
    except:
        return "Active"


def is_void_cascade(f):
    """Return True if this fissure is any kind of Void Cascade mission."""
    return (
        'Cascade' in f.get('missionType', '')  or
        'Cascade' in f.get('missionKey',  '')  or
        'Tuvul'   in f.get('node',        '')
    )


def is_steel_path(f):
    """Return True if this fissure is Steel Path difficulty."""
    return (
        f.get('isHard') is True                          or
        f.get('hard')   is True                          or
        str(f.get('isHard', '')).lower() == 'true'       or
        'Steel Path' in str(f.get('tier',       ''))     or
        'Hard'       in str(f.get('missionKey', ''))     or
        f.get('minEnemyLevel', 0) >= 100
    )


# ── Main handler ───────────────────────────────────────────────────────────────
def lambda_handler(event, context):

    # 1. Fetch all PC fissures
    api_url = "https://api.warframestat.us/pc/fissures"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0'}

    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            fissures = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"API Error: {e}")
        return {'statusCode': 403}

# --- START OF MOCK TEST DATA ---
    # Comment out your real 'fissures = json.loads(...)' line and use this:
    # fissures = [{
    #     "id": "MOCK_TEST_ID_001",
    #     "node": "Tuvul Commons (Zariman)",
    #     "missionType": "Void Cascade",
    #     "enemy": "Grineer/Corpus Crossfire",
    #     "tier": "Omnia",
    #     # "minEnemyLevel": 110,  # This triggers our Steel Path logic
    #     # "maxEnemyLevel": 115,
    #     "isHard": True,
    #     "expiry": "2026-02-27T23:59:59Z", # Ends at midnight
    #     "activation": "2026-02-27T12:00:00Z"
    # }]
    # --- END OF MOCK TEST DATA ---

# 3. UNIVERSAL TARGET FILTERING
    # Add any mission or node name to this list to track it!
    targets = ['Cascade', 'Tuvul']

    matches = [
        f for f in fissures
        if any(term.lower() in f.get('missionType', '').lower() or
               term.lower() in f.get('node', '').lower() for term in targets)
    ]

    print(f"DEBUG — Found {len(matches)} matching fissures.")

# CASCADE LOGIC

    # 2. Debug: log every Steel Path fissure so you can verify field names
    # sp_fissures = [f for f in fissures if f.get('isHard') is True]
    # print(f"DEBUG — All SP fissures in feed: {json.dumps(sp_fissures, indent=2)}")

    # 3. Filter for Void Cascade — catches normal AND Steel Path nodes
    # cascades = [f for f in fissures if is_void_cascade(f)]

    # Failsafe: also catch any SP fissure that has 'Cascade' anywhere in its keys
    # extra_sp = [
    #     f for f in fissures
    #     if f not in cascades
    #     and is_steel_path(f)
    #     and 'Cascade' in str(f.get('missionKey', ''))
    # ]
    # cascades.extend(extra_sp)

    # print(f"DEBUG — Cascade fissures found: {len(cascades)}")
    # for c in cascades:
    #     print(f"  node={c.get('node')} | missionType={c.get('missionType')} | isHard={c.get('isHard')}")



    # # 4. Process each Cascade
    # for f in cascades:
    #     f_id = f['id']

    #     # Duplicate check — skip if already alerted
    #     if supabase_request(f"alert_history?fissure_id=eq.{f_id}"):
    #         print(f"Skipping already-alerted fissure: {f_id}")
    #         continue

    #     sp = is_steel_path(f)
    #     print(f"DEBUG — Processing {f_id} | SP={sp} | levels={f.get('minEnemyLevel')}-{f.get('maxEnemyLevel')}")

    #     node   = f.get('node',   'Tuvul Commons')
    #     tier   = f.get('tier',   'Unknown')
    #     enemy  = f.get('enemy',  'Unknown')
    #     eta    = calculate_eta(f.get('expiry'))

    #     # 5. Build message
    #     if sp:
    #         header = "🚨 <b>STEEL PATH: VOID CASCADE ACTIVE</b> 🦾 Time to farm steel essense!"
    #     else:
    #         header = "🔵 <b>NORMAL VOID CASCADE ACTIVE</b> 💎 Relics are waiting for you!"

    #     message = (
    #         f"{header}\n\n"
    #         f"📍 <b>Node:</b> {node}\n"
    #         f"👾 <b>Faction:</b> {enemy}\n"
    #         f"💎 <b>Tier:</b> {tier} Relics\n"
    #         f"⏳ <b>Ends in:</b> {eta}"
    #     )

    #     # 6. Log to Supabase first (prevents double-send on Lambda retry)
    #     supabase_request("alert_history", method="POST", payload={
    #         "fissure_id":      f_id,
    #         "mission_type":    "Void Cascade",
    #         "fissure_tier":    tier,
    #         "node":            node,
    #         "enemy_faction":   enemy,
    #         "is_steel_path":   bool(sp),
    #         "activation_time": f.get('activation'),
    #         "expiry_time":     f.get('expiry')
    #     })

    #     # 7. Broadcast to all active subscribers
    #     active_users = supabase_request("subscribers?status=eq.active")
    #     if active_users:
    #         print(f"Broadcasting to {len(active_users)} users...")
    #         for user in active_users:
    #             send_telegram_message(user['chat_id'], message)
    #     else:
    #         print("No active subscribers found.")

    # CASCADE LOGIC CLOSE

# 4. Process each match
    for f in matches:
        f_id = f['id']

        # Duplicate check — skip if already alerted
        if supabase_request(f"alert_history?fissure_id=eq.{f_id}"):
            print(f"Skipping already-alerted fissure: {f_id}")
            continue

        sp = is_steel_path(f)
        node = f.get('node', 'Unknown Node')
        tier = f.get('tier', 'Unknown')
        enemy = f.get('enemy', 'Unknown')
        mission_type = f.get('missionType', 'Unknown Mission').upper()
        eta = calculate_eta(f.get('expiry'))

        print(f"DEBUG — Processing {f_id} | SP={sp} | level={f.get('minEnemyLevel')}")

        # 5. Build message with your specific headers
        if sp:
            header = f"🚨 <b>STEEL PATH: {mission_type} ACTIVE</b> 🦾 Time to farm steel essence!"
        else:
            header = f"🔵 <b>NORMAL {mission_type} ACTIVE</b> 💎 Relics are waiting for you!"

        message = (
            f"{header}\n\n"
            f"📍 <b>Node:</b> {node}\n"
            f"👾 <b>Faction:</b> {enemy}\n"
            f"💎 <b>Tier:</b> {tier} Relics\n"
            f"⏳ <b>Ends in:</b> {eta}\n"

        )

        # 6. Log to Supabase
        supabase_request("alert_history", method="POST", payload={
            "fissure_id": f_id,
            "mission_type": mission_type,
            "fissure_tier": tier,
            "node": node,
            "enemy_faction": enemy,
            "is_steel_path": bool(sp),
            "activation_time": f.get('activation'),
            "expiry_time": f.get('expiry')
        })

        # 7. Broadcast to all active subscribers
        active_users = supabase_request("subscribers?status=eq.active")
        if active_users:
            print(f"Broadcasting to {len(active_users)} users...")
            for user in active_users:
                send_telegram_message(user['chat_id'], message)
        else:
            print("No active subscribers found.")



    return {'statusCode': 200}
