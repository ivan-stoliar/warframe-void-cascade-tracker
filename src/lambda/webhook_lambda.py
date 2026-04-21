import json
import os
import urllib.request
import logging
from urllib.error import HTTPError

TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def send_telegram_message(chat_id, text):
    data = json.dumps({"chat_id": chat_id, "text": text}).encode('utf-8')
    req = urllib.request.Request(TELEGRAM_API_URL, data=data, headers={'Content-Type': 'application/json'})
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
        logger.error(f"Supabase HTTP error: {e.code} - {error_body}")
        return None
    except Exception as e:
        logger.error(f"Supabase request failed: {e}")
        return None

def lambda_handler(event, context):
    try:

        body = json.loads(event.get('body', '{}'))

        if 'message' not in body:
            return {'statusCode': 200, 'body': 'OK'}

        message = body['message']
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        username = message['chat'].get('username', 'Unknown')

        # /start
        if text == '/start':

            user_check = supabase_request(f"subscribers?chat_id=eq.{chat_id}")

            if not user_check:

                new_user = {
                    "chat_id": chat_id,
                    "tg_username": username,
                    "status": "inactive",
                    "is_permanent": False
                }
                supabase_request("subscribers", method='POST', payload=new_user)

                welcome_text = (
                    "Welcome to the Warframe Cascade Bot! 🚀\n\n"
                    "Your account is currently INACTIVE.\n"
                    "To activate your alerts, please use your access code by typing:\n"
                    "/redeem YOUR_CODE"
                )
            else:
                status = user_check[0].get('status', 'inactive')
                welcome_text = f"Welcome back! Your account is currently {status.upper()}."

            send_telegram_message(chat_id, welcome_text)

        # /redeem
        elif text.startswith('/redeem'):
            parts = text.split()
            if len(parts) < 2:
                send_telegram_message(chat_id, "Please provide a code. Format: /redeem YOUR_CODE")
                return {'statusCode': 200, 'body': 'OK'}

            code = parts[1]

            user_check = supabase_request(f"subscribers?chat_id=eq.{chat_id}")
            if not user_check:
                send_telegram_message(chat_id, "Please type /start first to register your account before redeeming a code!")
                return {'statusCode': 200, 'body': 'OK'}


            code_check = supabase_request(f"access_codes?code=eq.{code}&is_used=eq.false")

            if code_check:
                code_data = code_check[0]
                code_type = code_data.get('code_type', '')

                is_perm = 'lifetime' in code_type

                supabase_request(f"access_codes?id=eq.{code_data['id']}", method='PATCH', payload={
                    "is_used": True,
                    "redeemed_chat_id": chat_id
                })

                supabase_request(f"subscribers?chat_id=eq.{chat_id}", method='PATCH', payload={
                    "status": "active",
                    "is_permanent": is_perm
                })

                send_telegram_message(chat_id, f"✅ Code redeemed! Your alerts are now ACTIVE.\nPermanent Account: {is_perm}")
            else:
                send_telegram_message(chat_id, "❌ Invalid or already used code.")

        else:
            send_telegram_message(chat_id, "I only understand /start and /redeem right now!")

        return {
            'statusCode': 200,
            'body': json.dumps('Success')
        }

    except Exception as e:
        logger.error(f"Critical System Error: {str(e)}")
        return {
           'statusCode': 200,
            'body': json.dumps('Error processed securely')
        }
