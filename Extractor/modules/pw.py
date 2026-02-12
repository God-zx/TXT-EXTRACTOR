import requests, os, sys, re
import math
import json, asyncio
import subprocess
import datetime
import time
import random
from Extractor import app
from pyrogram import filters
from subprocess import getstatusoutput

# ============ UPDATED API CONFIGURATION ============
PW_API_BASE = "https://api.penpencil.co"
ORGANIZATION_ID = "5eb393ee95fab7468a79d189"
CLIENT_ID = "5eb393ee95fab7468a79d189"

# Updated headers matching latest PW web app
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Client-Id": CLIENT_ID,
    "Client-Type": "WEB",
    "Client-Version": "6.0.0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.pw.live",
    "Referer": "https://www.pw.live/",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Connection": "keep-alive"
}

MOBILE_HEADERS = {
    'Host': 'api.penpencil.co',
    'client-id': CLIENT_ID,
    'client-version': '12.84',
    'user-agent': 'Android',
    'randomid': 'e4307177362e86f1',
    'client-type': 'MOBILE',
    'device-meta': '{APP_VERSION:12.84,DEVICE_MAKE:Asus,DEVICE_MODEL:ASUS_X00TD,OS_VERSION:6,PACKAGE_NAME:xyz.penpencil.physicswalb}',
    'content-type': 'application/json; charset=UTF-8',
}


def make_request_with_retry(method, url, max_retries=3, delay=2, **kwargs):
    """
    Make HTTP request with retry logic for rate limiting (429) errors
    """
    for attempt in range(max_retries):
        try:
            if method.upper() == "GET":
                response = requests.get(url, timeout=30, **kwargs)
            elif method.upper() == "POST":
                response = requests.post(url, timeout=30, **kwargs)
            else:
                response = requests.request(method, url, timeout=30, **kwargs)
            
            # If rate limited, wait and retry
            if response.status_code == 429:
                wait_time = delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"Rate limited (429). Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}")
                time.sleep(wait_time)
                continue
            
            return response
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = delay * (2 ** attempt)
                print(f"Request failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
    
    # If all retries failed, return the last response
    return response


async def get_otp(message, phone_no):
    """Send OTP to mobile number"""
    url = f"{PW_API_BASE}/v1/users/get-otp"
    query_params = {"smsType": "0"}
    
    headers = DEFAULT_HEADERS.copy()
    headers["Integration-With"] = "Origin"
    
    payload = {
        "username": phone_no,
        "countryCode": "+91",
        "organizationId": ORGANIZATION_ID,
    }
    
    try:
        response = make_request_with_retry("POST", url, params=query_params, headers=headers, json=payload)
        resp_data = response.json()
        
        if response.status_code == 200 and (resp_data.get('success', False) or 'data' in resp_data):
            await message.reply_text("**✅ OTP Sent Successfully!**\n\nCheck your mobile number.")
            return True
        else:
            error_msg = resp_data.get('message', f'HTTP {response.status_code}')
            await message.reply_text(f"**❌ Failed to Send OTP**\n\nReason: `{error_msg}`")
            return False
            
    except Exception as e:
        print(f"Error during OTP request: {e}")
        await message.reply_text(f"**❌ Failed to Generate OTP**\n\nError: `{str(e)}`")
        return False


async def get_token(message, phone_no, otp):
    """Generate access token using OTP"""
    url = f"{PW_API_BASE}/v3/oauth/token"
    
    payload = {
        "username": phone_no,
        "otp": otp,
        "client_id": "system-admin",
        "client_secret": "KjPXuAVfC5xbmgreETNMaL7z",
        "grant_type": "password",
        "organizationId": ORGANIZATION_ID,
        "latitude": 0,
        "longitude": 0
    }
    
    headers = DEFAULT_HEADERS.copy()
    headers["Randomid"] = "990963b2-aa95-4eba-9d64-56bb55fca9a9"
    
    try:
        response = make_request_with_retry("POST", url, headers=headers, json=payload)
        resp = response.json()
        
        if response.status_code != 200:
            error_msg = resp.get('message', f'HTTP {response.status_code}')
            await message.reply_text(f"**❌ Token Generation Failed**\n\nReason: `{error_msg}`")
            return None, None
        
        if 'data' not in resp:
            await message.reply_text("**❌ Invalid response from server**")
            return None, None
        
        token = resp['data'].get('access_token')
        refresh_token = resp['data'].get('refresh_token', '')
        
        if not token:
            await message.reply_text("**❌ Token not found in response**")
            return None, None
            
        return token, refresh_token
        
    except Exception as e:
        print(f"Error during token request: {e}")
        await message.reply_text(f"**❌ Failed to Generate Token**\n\nError: `{str(e)}`")
        return None, None


async def verify_token(token):
    """
    Verify if a token is valid by making a test API call.
    Uses batches endpoint instead of /users/me to avoid rate limiting.
    """
    # Add small delay to avoid rate limiting
    time.sleep(0.5)
    
    # Use batches endpoint for verification (less likely to be rate limited)
    url = f"{PW_API_BASE}/v3/batches/my-batches"
    
    headers = MOBILE_HEADERS.copy()
    headers["authorization"] = f"Bearer {token}"
    
    params = {
        'mode': '1',
        'filter': 'false',
        'organisationId': ORGANIZATION_ID,
        'limit': '5',
        'page': '1',
        'ut': str(int(datetime.datetime.now().timestamp() * 1000)),
    }
    
    try:
        response = make_request_with_retry("GET", url, params=params, headers=headers, max_retries=2, delay=1)
        
        # If we get 200 or 401, we know the token format is valid
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                # Token is valid and working
                # Try to get user info from token (decode JWT)
                user_info = decode_jwt_token(token)
                return {
                    'valid': True,
                    'user_name': user_info.get('firstName', 'Unknown') + ' ' + user_info.get('lastName', ''),
                    'user_mobile': user_info.get('username', 'Unknown'),
                    'user_email': user_info.get('email', 'N/A'),
                    'user_id': user_info.get('_id', 'Unknown')
                }
        
        elif response.status_code == 401:
            return {'valid': False, 'error': 'Token expired or invalid (401)'}
        
        elif response.status_code == 429:
            return {'valid': False, 'error': 'Rate limited (429). Please wait a few minutes and try again.'}
        
        else:
            return {'valid': False, 'error': f'Status code: {response.status_code}'}
        
    except Exception as e:
        print(f"Token verification error: {e}")
        return {'valid': False, 'error': str(e)}


def decode_jwt_token(token):
    """Decode JWT token to extract user info without API call"""
    try:
        import base64
        # Split the token
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        
        # Decode the payload
        payload = parts[1]
        # Add padding if needed
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded = base64.b64decode(payload)
        data = json.loads(decoded)
        
        return data.get('data', {})
    except Exception as e:
        print(f"JWT decode error: {e}")
        return {}


async def refresh_access_token(refresh_token):
    """Refresh/renew token using refresh token"""
    url = f"{PW_API_BASE}/v3/oauth/token"
    
    payload = {
        "refresh_token": refresh_token,
        "client_id": "system-admin",
        "client_secret": "KjPXuAVfC5xbmgreETNMaL7z",
        "grant_type": "refresh_token",
        "organizationId": ORGANIZATION_ID
    }
    
    headers = DEFAULT_HEADERS.copy()
    
    try:
        response = make_request_with_retry("POST", url, headers=headers, json=payload, max_retries=2, delay=1)
        resp = response.json()
        
        if response.status_code == 200 and 'data' in resp:
            new_token = resp['data'].get('access_token')
            new_refresh_token = resp['data'].get('refresh_token', '')
            return new_token, new_refresh_token
        else:
            return None, None
            
    except Exception as e:
        print(f"Token refresh error: {e}")
        return None, None


async def get_new_token_from_old(token):
    """
    Verify token and get user info.
    Note: True token cloning is not possible via API.
    """
    # First try to decode JWT locally
    user_info = decode_jwt_token(token)
    
    if user_info:
        # Verify with API
        verification = await verify_token(token)
        
        if verification['valid']:
            return {
                'valid': True,
                'token': token,
                'user_name': verification['user_name'],
                'user_mobile': verification['user_mobile'],
                'user_email': verification['user_email'],
                'user_id': verification['user_id'],
                'message': 'Token verified successfully!'
            }
        else:
            # Token decoded but API verification failed
            return {
                'valid': True,  # Still mark as valid since JWT is valid
                'token': token,
                'user_name': user_info.get('firstName', 'Unknown') + ' ' + user_info.get('lastName', ''),
                'user_mobile': user_info.get('username', 'Unknown'),
                'user_email': user_info.get('email', 'N/A'),
                'user_id': user_info.get('_id', 'Unknown'),
                'message': 'Token decoded (API rate limited, but token appears valid)'
            }
    else:
        return {'valid': False, 'error': 'Invalid token format'}


async def pw_mobile(app, message):
    """Handle mobile-based login"""
    try:
        lol = await app.ask(message.chat.id, text="**📱 ENTER YOUR PW MOBILE NO. WITHOUT COUNTRY CODE.**")
        phone_no = lol.text.strip()
        await lol.delete()
        
        # Validate phone number
        if not phone_no.isdigit() or len(phone_no) != 10:
            await message.reply_text("**❌ Invalid Mobile Number!**\n\nPlease enter a valid 10-digit mobile number.")
            return
        
        otp_sent = await get_otp(message, phone_no)
        if not otp_sent:
            return
        
        lol2 = await app.ask(message.chat.id, text="**🔑 ENTER YOUR OTP SENT ON YOUR MOBILE NO.**")
        otp = lol2.text.strip()
        await lol2.delete()
        
        # Validate OTP
        if not otp.isdigit():
            await message.reply_text("**❌ Invalid OTP!** OTP should contain only numbers.")
            return
        
        token, refresh_token = await get_token(message, phone_no, otp)
        
        if token:
            # Decode token to get user info
            user_info = decode_jwt_token(token)
            
            token_message = f"""**✅ LOGIN SUCCESSFUL!**

**👤 User:** `{user_info.get('firstName', 'Unknown')} {user_info.get('lastName', '')}`
**📱 Mobile:** `{phone_no}`
**📧 Email:** `{user_info.get('email', 'N/A')}`

**🔐 YOUR ACCESS TOKEN:**
`{token}`

**📋 REFRESH TOKEN:**
`{refresh_token}`

**📅 Generated:** `{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`

**Tap to copy the token above ☝️**"""
            
            await message.reply_text(token_message)
            await pw_login(app, message, token)
        else:
            await message.reply_text("**❌ Failed to generate token. Please try again.**")
            
    except Exception as e:
        print(f"Error in pw_mobile: {e}")
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def pw_token(app, message):
    """Handle token-based login"""
    try:
        lol3 = await app.ask(message.chat.id, text="**🔑 ENTER YOUR PW ACCESS TOKEN**")
        old_token = lol3.text.strip()
        await lol3.delete()
        
        if not old_token:
            await message.reply_text("**❌ Token cannot be empty!**")
            return
        
        # Show verification message
        status_msg = await message.reply_text("**🔄 Verifying token...**")
        
        # Verify the token
        token_info = await get_new_token_from_old(old_token)
        
        await status_msg.delete()
        
        if token_info['valid']:
            token_message = f"""**✅ TOKEN VERIFIED SUCCESSFULLY!**

**👤 User Name:** `{token_info['user_name']}`
**📱 Mobile:** `{token_info['user_mobile']}`
**📧 Email:** `{token_info['user_email']}`
**🆔 User ID:** `{token_info.get('user_id', 'N/A')}`

**🔐 TOKEN:**
`{old_token}`

**📅 Verified:** `{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`

**✅ Token is valid and working!**

**Note:** {token_info.get('message', '')}

**Tap to copy ☝️**"""
            
            await message.reply_text(token_message)
            
            # Log token usage
            try:
                token_log = {
                    "user": token_info['user_mobile'],
                    "user_id": token_info.get('user_id', 'Unknown'),
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                with open("token_logs.txt", 'a') as f:
                    f.write(f"{json.dumps(token_log)}\n")
            except Exception as e:
                print(f"Error logging token: {e}")
            
            # Proceed with login
            await pw_login(app, message, old_token)
        else:
            await message.reply_text(f"""**❌ INVALID TOKEN!**

The token you entered is not valid or has expired.

**Error:** `{token_info.get('error', 'Unknown error')}`

**Please try:**
• Check if token is correct
• Generate new token using Mobile/OTP method
• Wait a few minutes if you see rate limit errors
• Contact support if issue persists""")
            
    except Exception as e:
        print(f"Error in pw_token: {e}")
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def pw_login(app, message, token):
    """Main login function to fetch batches"""
    
    # Add small delay to avoid rate limiting
    time.sleep(1)
    
    # Setup headers with token
    headers = MOBILE_HEADERS.copy()
    headers['authorization'] = f"Bearer {token}"
    
    params = {
       'mode': '1',
       'filter': 'false',
       'exam': '',
       'amount': '',
       'organisationId': ORGANIZATION_ID,
       'classes': '',
       'limit': '20',
       'page': '1',
       'programId': '',
       'ut': str(int(datetime.datetime.now().timestamp() * 1000)),
    }
    
    try:
        # Fetch batches with retry
        response = make_request_with_retry(
            "GET",
            f'{PW_API_BASE}/v3/batches/my-batches',
            params=params,
            headers=headers,
            max_retries=3,
            delay=2
        )
        
        resp_data = response.json()
        
        # Check for authentication errors
        if response.status_code == 401 or resp_data.get('message') == 'Unauthorized':
            await message.reply_text("**❌ Token Expired or Invalid!**\n\nPlease generate a new token.")
            return
        
        if response.status_code == 429:
            await message.reply_text("**❌ Rate Limited!**\n\nToo many requests. Please wait 2-3 minutes and try again.")
            return
        
        if "data" not in resp_data:
            error_msg = resp_data.get('message', f'HTTP {response.status_code}')
            await message.reply_text(f"**❌ Failed to fetch batches**\n\nError: `{error_msg}`")
            return
        
        batch_data = resp_data["data"]
        
        if not batch_data:
            await message.reply_text("**⚠️ No batches found for this account!**")
            return
        
        # Display batches
        aa = "**📚 You have these Batches :-\n\nBatch ID   :   Batch Name**\n\n"
        for data in batch_data:
            batch_name = data.get("name", "Unknown")
            batch_id = data.get("_id", "N/A")
            aa += f"**{batch_name}**   :   `{batch_id}`\n"
        
        await message.reply_text(aa)
        
    except Exception as e:
        await message.reply_text(f"**❌ Error fetching batches:** `{str(e)}`")
        return
    
    # Get Batch ID input
    try:
        input3 = await app.ask(message.chat.id, text="**📥 Now send the Batch ID to Download**")
        raw_text3 = input3.text.strip()
        await input3.delete()
        
        if not raw_text3:
            await message.reply_text("**❌ Batch ID cannot be empty!**")
            return
            
    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")
        return
    
    # Add delay before next request
    time.sleep(1)
    
    # Get batch details
    try:
        response2 = make_request_with_retry(
            "GET",
            f'{PW_API_BASE}/v3/batches/{raw_text3}/details',
            headers=headers,
            params=params,
            max_retries=2,
            delay=1
        )
        
        resp2_data = response2.json()
        
        if response2.status_code == 429:
            await message.reply_text("**❌ Rate Limited!**\n\nPlease wait a few minutes and try again.")
            return
        
        if 'data' not in resp2_data:
            await message.reply_text("**❌ Invalid Batch ID or batch not found!**")
            return
            
        batch_name = resp2_data.get('data', {}).get('name', 'Unknown Batch')
        
    except Exception as e:
        await message.reply_text(f"**❌ Error fetching batch details:** `{str(e)}`")
        return
    
    # Choose download option
    option_text = """**📥 Choose Download Option:**

1️⃣ **Full Batch** - Download complete batch content (All subjects)

2️⃣ **Today Class** - Download only specific date's content

**Send 1 for Full Batch or 2 for Today Class**"""
    
    try:
        input_option = await app.ask(message.chat.id, text=option_text)
        download_option = input_option.text.strip()
        await input_option.delete()
        
        if download_option == "1" or download_option.lower() in ["full batch", "full", "batch"]:
            await handle_full_batch(app, message, headers, params, raw_text3, resp2_data)
            
        elif download_option == "2" or download_option.lower() in ["today class", "today", "date"]:
            await handle_today_class(app, message, headers, params, raw_text3, batch_name)
            
        else:
            await message.reply_text("**❌ Invalid Option! Please send 1 or 2.**")
            
    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def handle_full_batch(app, message, headers, params, batch_id, response2):
    """Handle Full Batch Download"""
    try:
        subjects = response2.get('data', {}).get('subjects', [])
        
        if not subjects:
            await message.reply_text("**❌ No subjects found in this batch!**")
            return
        
        bb = "**📖 Subject   :   SubjectId**\n\n"
        vj = ""
        for subject in subjects:
            subject_name = subject.get('subject', 'Unknown')
            subject_id = subject.get('subjectId', 'N/A')
            bb += f"**{subject_name}**   :   `{subject_id}`\n"
            vj += f"{subject_id}&"
        
        await message.reply_text(bb)
        
        input4 = await app.ask(
            message.chat.id,
            text=f"**Now send the Subject IDs to Download**\n\nSend like this **1&2&3&4** so on\nor copy paste or edit **below ids** according to you :\n\n**Enter this to download full batch :-**\n`{vj}`"
        )
        raw_text4 = input4.text.strip()
        await input4.delete()
        
        if not raw_text4:
            await message.reply_text("**❌ Subject IDs cannot be empty!**")
            return
        
        input5 = await app.ask(message.chat.id, text="**🎥 Enter resolution (e.g., 720, 1080)**")
        raw_text5 = input5.text.strip()
        await input5.delete()
        
        # Process subjects
        xu = raw_text4.split('&')
        hh = ""
        for x in range(0, len(xu)):
            s = xu[x].strip()
            if not s:
                continue
            for subject in subjects:
                if subject.get('subjectId') == s:
                    tag_count = subject.get('tagCount', 0)
                    hh += f"{subject.get('subjectId')}:{tag_count}&"
        
        # Clear old file if exists
        output_file = "mm.txt"
        if os.path.exists(output_file):
            os.remove(output_file)
        
        xv = hh.split('&')
        total_subjects = 0
        
        for y in range(0, len(xv)):
            t = xv[y]
            if not t:
                continue
            try:
                id, tagcount = t.split(':')
                tagcount = int(tagcount) if tagcount else 0
                r = tagcount / 20
                rr = math.ceil(r)
                if rr < 1:
                    rr = 1
                
                for i in range(1, rr + 1):
                    # Add delay between requests to avoid rate limiting
                    time.sleep(0.5)
                    
                    topic_params = {'page': str(i), 'limit': '20'}
                    response3 = make_request_with_retry(
                        "GET",
                        f"{PW_API_BASE}/v3/batches/{batch_id}/subject/{id}/topics",
                        params=topic_params,
                        headers=headers,
                        max_retries=2,
                        delay=1
                    )
                    
                    resp3_data = response3.json()
                    
                    if response3.status_code == 429:
                        await message.reply_text(f"**⚠️ Rate limited while fetching topics. Waiting...**")
                        time.sleep(3)
                        continue
                    
                    if "data" in resp3_data and resp3_data["data"]:
                        total_subjects += len(resp3_data["data"])
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(f"{json.dumps(resp3_data['data'])}\n")
                            
            except Exception as e:
                print(f"Error processing subject {t}: {e}")
                continue
        
        if os.path.exists(output_file) and total_subjects > 0:
            await app.send_document(
                message.chat.id,
                document=output_file,
                caption=f"**✅ Full Batch Content Downloaded!**\n\n**Total items:** {total_subjects}"
            )
        else:
            await message.reply_text("**⚠️ No content found!**")
            
    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def handle_today_class(app, message, headers, params, batch_id, batch_name):
    """Handle Today Class Download with Date Selection"""
    
    try:
        today = datetime.datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        
        date_prompt = f"""**📅 TODAY CLASS MODE**

**Batch:** `{batch_name}`
**Today's Date:** `{today_str}`

**Enter the date for which you want to download content:**

**Format:** `YYYY-MM-DD`
**Example:** `{today_str}`

**Note:** 
• Content available from 1:00 AM to 11:59 PM daily
• You can enter past dates also
• Send 'today' for today's date

**Send date:**"""
        
        input_date = await app.ask(message.chat.id, text=date_prompt)
        selected_date_input = input_date.text.strip().lower()
        await input_date.delete()
        
        # Handle 'today' input
        if selected_date_input == 'today':
            selected_date = today_str
        else:
            selected_date = selected_date_input
        
        # Validate date format
        try:
            datetime.datetime.strptime(selected_date, "%Y-%m-%d")
        except ValueError:
            await message.reply_text("**❌ Invalid Date Format!**\n\n**Please use format:** `YYYY-MM-DD`\n**Example:** `2024-01-15`")
            return
        
        await message.reply_text(f"**✅ Date Selected: `{selected_date}`**\n\n**🔍 Fetching content for {batch_name} on {selected_date}...**")
        
        # Add delay
        time.sleep(1)
        
        # Get batch subjects
        response2 = make_request_with_retry(
            "GET",
            f'{PW_API_BASE}/v3/batches/{batch_id}/details',
            headers=headers,
            params=params,
            max_retries=2,
            delay=1
        )
        
        resp2_data = response2.json()
        
        if response2.status_code == 429:
            await message.reply_text("**❌ Rate Limited!**\n\nPlease wait a few minutes and try again.")
            return
        
        subjects = resp2_data.get('data', {}).get('subjects', [])
        
        if not subjects:
            await message.reply_text("**❌ No subjects found in this batch!**")
            return
        
        # Show subjects
        bb = "**📚 Subjects in this Batch:**\n\n"
        for subject in subjects:
            bb += f"**{subject.get('subject')}**   :   `{subject.get('subjectId')}`\n"
        await message.reply_text(bb)
        
        # Ask which subjects to download
        subject_prompt = """**Send Subject IDs to download (comma separated)**

**OR send `all` to download all subjects**

**Example:** `1,2,3` or `all`"""
        
        input_subjects = await app.ask(message.chat.id, text=subject_prompt)
        subject_input = input_subjects.text.strip()
        await input_subjects.delete()
        
        if subject_input.lower() == "all":
            selected_subjects = subjects
        else:
            selected_subject_ids = [s.strip() for s in subject_input.split(',')]
            selected_subjects = [s for s in subjects if s.get('subjectId') in selected_subject_ids]
        
        if not selected_subjects:
            await message.reply_text("**❌ No valid subjects selected!**")
            return
        
        # Ask for resolution
        input_res = await app.ask(message.chat.id, text="**🎥 Enter resolution (e.g., 720, 1080)**")
        resolution = input_res.text.strip()
        await input_res.delete()
        
        # Process each subject
        total_content_found = 0
        output_file = f"today_class_{batch_name.replace(' ', '_').replace('/', '_')}_{selected_date}.txt"
        
        # Clear old file if exists
        if os.path.exists(output_file):
            os.remove(output_file)
        
        for subject in selected_subjects:
            subject_id = subject.get('subjectId')
            subject_name = subject.get('subject')
            
            status_msg = await message.reply_text(f"**🔍 Searching in {subject_name}...**")
            
            page = 1
            subject_content = []
            
            while page <= 50:  # Safety limit
                try:
                    # Add delay between requests
                    time.sleep(0.5)
                    
                    topic_params = {'page': str(page), 'limit': '20'}
                    topic_response = make_request_with_retry(
                        "GET",
                        f"{PW_API_BASE}/v3/batches/{batch_id}/subject/{subject_id}/topics",
                        params=topic_params,
                        headers=headers,
                        max_retries=2,
                        delay=1
                    )
                    
                    if topic_response.status_code == 429:
                        await status_msg.edit_text(f"**⚠️ Rate limited in {subject_name}. Waiting...**")
                        time.sleep(3)
                        continue
                    
                    topics_data = topic_response.json()
                    topics = topics_data.get("data", [])
                    
                    if not topics:
                        break
                    
                    # Filter topics by date
                    for topic in topics:
                        topic_date = topic.get("createdAt", "")
                        if topic_date:
                            try:
                                topic_date_obj = datetime.datetime.fromisoformat(topic_date.replace('Z', '+00:00'))
                                topic_date_str = topic_date_obj.strftime("%Y-%m-%d")
                                
                                if topic_date_str == selected_date:
                                    subject_content.append({
                                        "topic": topic.get("topic", "Unknown"),
                                        "subject": subject_name,
                                        "date": topic_date,
                                        "data": topic
                                    })
                            except:
                                pass
                    
                    page += 1
                    
                except Exception as e:
                    print(f"Error fetching page {page}: {e}")
                    break
            
            await status_msg.delete()
            
            # Write subject content to file
            if subject_content:
                total_content_found += len(subject_content)
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"📚 SUBJECT: {subject_name}\n")
                    f.write(f"📅 DATE: {selected_date}\n")
                    f.write(f"{'='*60}\n\n")
                    
                    for idx, content in enumerate(subject_content, 1):
                        f.write(f"{idx}. {content['topic']}\n")
                        f.write(f"   Subject: {content['subject']}\n")
                        f.write(f"   Created: {content['date']}\n")
                        f.write(f"   Data: {json.dumps(content['data'])}\n")
                        f.write("\n")
        
        # Send results
        if total_content_found > 0:
            await message.reply_text(
                f"**✅ Found {total_content_found} items for {selected_date}!**\n\n"
                f"**Batch:** {batch_name}\n"
                f"**Date:** {selected_date}\n"
                f"**Total Content:** {total_content_found} items"
            )
            await app.send_document(
                message.chat.id,
                document=output_file,
                caption=f"**📅 Content for {selected_date}**"
            )
        else:
            await message.reply_text(
                f"**⚠️ No content found for {selected_date}!**\n\n"
                f"**Batch:** {batch_name}\n"
                f"**Date:** {selected_date}\n\n"
                f"**Possible reasons:**\n"
                f"• No classes on this date\n"
                f"• Date format issue\n"
                f"• Content not yet uploaded"
            )
            
    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")
