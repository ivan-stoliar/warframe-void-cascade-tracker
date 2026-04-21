import json
import os
import urllib.request
import logging
import urllib.error
from datetime import datetime, timezone

# Configuration
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
SUPABASE_URL   = os.environ['SUPABASE_URL']
SUPABASE_KEY   = os.environ['SUPABASE_KEY']
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Helpers
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
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        logger.error(f"Telegram HTTP Error: {e.code} - {error_body}")
    except Exception as e:
        logger.error(f"General Telegram error: {e}")


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
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        logger.error(f"Supabase HTTP Error: {e.code} - {error_body}")
        return None
    except Exception as e:
        logger.error(f"General Supabase error: {e}")
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
    except Exception as e:
        logger.error(f"Error parsing date {expiry_str}: {e}")
        return "Active"


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


# Main handler
def lambda_handler(event, context):
    api_url = "https://api.warframestat.us/pc/fissures"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0'}

    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            fissures = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        logger.error(f"Warframe API HTTP Error: {e.code}")
        return {'statusCode': 403}
    except Exception as e:
        logger.error(f"Warframe API Error: {e}")
        return {'statusCode': 403}

    # Any mission can be added here
    targets = ['Cascade', 'Tuvul']

    matches = [
        f for f in fissures
        if any(term.lower() in f.get('missionType', '').lower() or
               term.lower() in f.get('node', '').lower() for term in targets)
    ]

    logger.info(f"Found {len(matches)} matching fissures.")

    # Each match processed
    for f in matches:
        f_id = f['id']

        if supabase_request(f"alert_history?fissure_id=eq.{f_id}"):
            logger.info(f"Skipping already-alerted fissure: {f_id}")
            continue

        sp = is_steel_path(f)
        node = f.get('node', 'Unknown Node')
        tier = f.get('tier', 'Unknown')
        enemy = f.get('enemy', 'Unknown')
        mission_type = f.get('missionType', 'Unknown Mission').upper()
        eta = calculate_eta(f.get('expiry'))

        logger.info(f"Processing {f_id} | SP={sp} | level={f.get('minEnemyLevel')}")

        # Telegram message
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

        # Log to Supabase
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

        # Broadcasted to all active subscribers
        active_users = supabase_request("subscribers?status=eq.active")
        if active_users:
            logger.info(f"Broadcasting to {len(active_users)} users...")
            for user in active_users:
                send_telegram_message(user['chat_id'], message)
        else:
            logger.info("No active subscribers found.")

    return {'statusCode': 200}
