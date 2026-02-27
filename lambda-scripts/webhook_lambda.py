
import json
import os
import urllib.request
from urllib.error import HTTPError

# 1. Grab your secret keys from AWS Environment Variables
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

def send_telegram_message(chat_id, text):
    """Sends a message back to the user via Telegram."""
    data = json.dumps({"chat_id": chat_id, "text": text}).encode('utf-8')
    req = urllib.request.Request(TELEGRAM_API_URL, data=data, headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"Telegram error: {e}")

def supabase_request(endpoint, method='GET', payload=None):
    """Handles REST API calls to your Supabase database."""
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
    except HTTPError as e:
        print(f"Supabase error: {e.read().decode()}")
        return None
    except Exception as e:
        print(f"Supabase request failed: {e}")
        return None

def lambda_handler(event, context):
    """The main brain of the AWS Lambda function."""
    try:
        # Parse the incoming message from Telegram
        body = json.loads(event.get('body', '{}'))

        # Ignore non-message events
        if 'message' not in body:
            return {'statusCode': 200, 'body': 'OK'}

        message = body['message']
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        username = message['chat'].get('username', 'Unknown')

        # --- COMMAND: /start ---
        if text == '/start':
            # Check if user already exists in the database
            user_check = supabase_request(f"subscribers?chat_id=eq.{chat_id}")

            if not user_check:
                # Insert brand new user as inactive
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

        # --- COMMAND: /redeem ---
        elif text.startswith('/redeem'):
            parts = text.split()
            if len(parts) < 2:
                send_telegram_message(chat_id, "Please provide a code. Format: /redeem YOUR_CODE")
                return {'statusCode': 200, 'body': 'OK'}

            code = parts[1]

            # Look up the code in the database
            code_check = supabase_request(f"access_codes?code=eq.{code}&is_used=eq.false")

            if code_check:
                code_data = code_check[0]
                code_type = code_data.get('code_type', '')

                # Check if the word "lifetime" is in the code_type
                is_perm = 'lifetime' in code_type

                # Mark code as used
                supabase_request(f"access_codes?id=eq.{code_data['id']}", method='PATCH', payload={
                    "is_used": True,
                    "redeemed_chat_id": chat_id
                })

                # Update the subscriber's status AND their permanent flag
                supabase_request(f"subscribers?chat_id=eq.{chat_id}", method='PATCH', payload={
                    "status": "active",
                    "is_permanent": is_perm
                })

                send_telegram_message(chat_id, f"✅ Code redeemed! Your alerts are now ACTIVE.\nPermanent Account: {is_perm}")
            else:
                send_telegram_message(chat_id, "❌ Invalid or already used code.")

        # --- UNKNOWN COMMAND ---
        else:
            send_telegram_message(chat_id, "I only understand /start and /redeem right now!")

        # Always return a 200 success code so Telegram doesn't keep retrying
        return {
            'statusCode': 200,
            'body': json.dumps('Success')
        }

    except Exception as e:
        print(f"Critical System Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps('Error processing request')
        }
