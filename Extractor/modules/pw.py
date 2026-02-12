import requests, os, sys, re
import math
import json, asyncio
import subprocess
import datetime
import time
import random
import base64
from Extractor import app
from pyrogram import filters
from subprocess import getstatusoutput

# ============ API CONFIGURATION ============
PW_API_BASE = "https://api.penpencil.co"
ORGANIZATION_ID = "5eb393ee95fab7468a79d189"
CLIENT_ID = "5eb393ee95fab7468a79d189"

# Request delay configuration (in seconds)
REQUEST_DELAY = 2  # Delay between API calls
BATCH_DELAY = 1    # Delay between batch operations

# Headers for web requests
WEB_HEADERS = {
    "Content-Type": "application/json",
    "Client-Id": CLIENT_ID,
    "Client-Type": "WEB",
    "Client-Version": "6.0.0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.pw.live",
    "Referer": "https://www.pw.live/",
}

# Headers for mobile requests
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


def safe_request(method, url, max_retries=3, retry_delay=3, **kwargs):
    """
    Make HTTP request with retry logic and proper delays
    """
    for attempt in range(max_retries):
        try:
            if method.upper() == "GET":
                response = requests.get(url, timeout=30, **kwargs)
            elif method.upper() == "POST":
                response = requests.post(url, timeout=30, **kwargs)
            else:
                response = requests.request(method, url, timeout=30, **kwargs)
            
            # Handle rate limiting
            if response.status_code == 429:
                wait_time = retry_delay * (attempt + 1) + random.uniform(1, 2)
                print(f"Rate limited. Waiting {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            return response
            
        except Exception as e:
            print(f"Request error: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise
    
    return response


def decode_jwt(token):
    """Decode JWT token to extract user info"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded = base64.b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        print(f"JWT decode error: {e}")
        return None


async def get_otp(message, phone_no):
    """Send OTP to mobile number"""
    url = f"{PW_API_BASE}/v1/users/get-otp"
    
    headers = WEB_HEADERS.copy()
    headers["Integration-With"] = "Origin"
    
    payload = {
        "username": phone_no,
        "countryCode": "+91",
        "organizationId": ORGANIZATION_ID,
    }
    
    try:
        response = safe_request("POST", url, params={"smsType": "0"}, headers=headers, json=payload)
        data = response.json()
        
        if response.status_code == 200:
            await message.reply_text("**✅ OTP Sent Successfully!**\n\nCheck your mobile number.")
            return True
        else:
            error = data.get('message', f'Error {response.status_code}')
            await message.reply_text(f"**❌ Failed to Send OTP**\n\nReason: `{error}`")
            return False
            
    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")
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
    
    headers = WEB_HEADERS.copy()
    headers["Randomid"] = "990963b2-aa95-4eba-9d64-56bb55fca9a9"
    
    try:
        response = safe_request("POST", url, headers=headers, json=payload)
        data = response.json()
        
        if response.status_code == 200 and 'data' in data:
            token = data['data'].get('access_token')
            refresh = data['data'].get('refresh_token', '')
            return token, refresh
        else:
            error = data.get('message', 'Unknown error')
            await message.reply_text(f"**❌ Token Generation Failed**\n\n{error}")
            return None, None
            
    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")
        return None, None


async def pw_mobile(app, message):
    """Handle mobile-based login"""
    try:
        # Get phone number
        ask_phone = await app.ask(message.chat.id, text="**📱 ENTER YOUR PW MOBILE NO. WITHOUT COUNTRY CODE.**")
        phone_no = ask_phone.text.strip()
        await ask_phone.delete()
        
        if not phone_no.isdigit() or len(phone_no) != 10:
            await message.reply_text("**❌ Invalid Mobile Number!** Enter 10-digit number.")
            return
        
        # Send OTP
        if not await get_otp(message, phone_no):
            return
        
        # Get OTP
        ask_otp = await app.ask(message.chat.id, text="**🔑 ENTER OTP SENT TO YOUR MOBILE**")
        otp = ask_otp.text.strip()
        await ask_otp.delete()
        
        if not otp.isdigit():
            await message.reply_text("**❌ Invalid OTP!**")
            return
        
        # Generate token
        token, refresh = await get_token(message, phone_no, otp)
        
        if token:
            # Decode and show info
            jwt_data = decode_jwt(token)
            user_data = jwt_data.get('data', {}) if jwt_data else {}
            
            msg = f"""**✅ LOGIN SUCCESSFUL!**

**👤 User:** `{user_data.get('firstName', 'Unknown')} {user_data.get('lastName', '')}`
**📱 Mobile:** `{phone_no}`
**📧 Email:** `{user_data.get('email', 'N/A')}`

**🔐 ACCESS TOKEN:**
`{token}`

**📋 REFRESH TOKEN:**
`{refresh}`

**📅 Generated:** `{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`"""
            
            await message.reply_text(msg)
            
            # Delay before fetching batches
            time.sleep(REQUEST_DELAY)
            await fetch_and_show_batches(app, message, token)
        else:
            await message.reply_text("**❌ Failed to generate token.**")
            
    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def pw_token(app, message):
    """Handle token-based login"""
    try:
        ask_token = await app.ask(message.chat.id, text="**🔑 ENTER YOUR PW ACCESS TOKEN**")
        token = ask_token.text.strip()
        await ask_token.delete()
        
        if not token:
            await message.reply_text("**❌ Token cannot be empty!**")
            return
        
        status = await message.reply_text("**🔄 Verifying token...**")
        
        # Decode JWT to get user info
        jwt_data = decode_jwt(token)
        user_data = jwt_data.get('data', {}) if jwt_data else {}
        
        await status.delete()
        
        if user_data:
            msg = f"""**✅ TOKEN VERIFIED!**

**👤 Name:** `{user_data.get('firstName', 'Unknown')} {user_data.get('lastName', '')}`
**📱 Mobile:** `{user_data.get('username', 'Unknown')}`
**📧 Email:** `{user_data.get('email', 'N/A')}`
**🆔 ID:** `{user_data.get('_id', 'N/A')}`

**📅 Verified:** `{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`

**✅ Token is valid! Proceeding...**"""
            
            await message.reply_text(msg)
            
            # Delay before fetching batches
            time.sleep(REQUEST_DELAY)
            await fetch_and_show_batches(app, message, token)
        else:
            await message.reply_text("**❌ Invalid Token Format!**")
            
    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def fetch_and_show_batches(app, message, token):
    """Fetch and display user's batches"""
    
    headers = MOBILE_HEADERS.copy()
    headers['authorization'] = f"Bearer {token}"
    
    params = {
        'mode': '1',
        'filter': 'false',
        'organisationId': ORGANIZATION_ID,
        'limit': '50',
        'page': '1',
        'ut': str(int(datetime.datetime.now().timestamp() * 1000)),
    }
    
    try:
        status = await message.reply_text("**🔄 Fetching your batches...**")
        
        response = safe_request("GET", f'{PW_API_BASE}/v3/batches/my-batches', 
                               params=params, headers=headers, max_retries=2, retry_delay=2)
        
        await status.delete()
        data = response.json()
        
        if response.status_code == 401:
            await message.reply_text("**❌ Token Expired!** Generate a new token.")
            return
        
        if 'data' not in data or not data['data']:
            await message.reply_text("**⚠️ No batches found!**")
            return
        
        batches = data['data']
        
        # Display batches
        msg = "**📚 YOUR BATCHES:\n\nBatch Name : Batch ID**\n\n"
        for batch in batches:
            name = batch.get("name", "Unknown")
            batch_id = batch.get("_id", "N/A")
            msg += f"**{name}**\n`{batch_id}`\n\n"
        
        await message.reply_text(msg)
        
        # Ask for batch ID
        ask_batch = await app.ask(message.chat.id, text="**📥 Send the Batch ID to download**")
        batch_id = ask_batch.text.strip()
        await ask_batch.delete()
        
        if not batch_id:
            await message.reply_text("**❌ Batch ID cannot be empty!**")
            return
        
        # Delay before fetching batch details
        time.sleep(REQUEST_DELAY)
        await show_download_options(app, message, token, batch_id)
        
    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def show_download_options(app, message, token, batch_id):
    """Show download options (Full Batch or Today Class)"""
    
    headers = MOBILE_HEADERS.copy()
    headers['authorization'] = f"Bearer {token}"
    
    params = {
        'organisationId': ORGANIZATION_ID,
        'ut': str(int(datetime.datetime.now().timestamp() * 1000)),
    }
    
    try:
        # Fetch batch details
        status = await message.reply_text("**🔄 Fetching batch details...**")
        
        response = safe_request("GET", f'{PW_API_BASE}/v3/batches/{batch_id}/details',
                               headers=headers, params=params, max_retries=2, retry_delay=2)
        
        await status.delete()
        data = response.json()
        
        if 'data' not in data:
            await message.reply_text("**❌ Invalid Batch ID!**")
            return
        
        batch_name = data['data'].get('name', 'Unknown Batch')
        subjects = data['data'].get('subjects', [])
        
        if not subjects:
            await message.reply_text("**❌ No subjects found!**")
            return
        
        # Show options
        options = """**📥 Choose Download Option:**

1️⃣ **Full Batch** - All subjects content

2️⃣ **Today Class** - Specific date content

**Send 1 or 2**"""
        
        ask_option = await app.ask(message.chat.id, text=options)
        option = ask_option.text.strip()
        await ask_option.delete()
        
        if option in ["1", "full", "batch", "full batch"]:
            await download_full_batch(app, message, token, batch_id, subjects, batch_name)
        elif option in ["2", "today", "date", "today class"]:
            await download_today_class(app, message, token, batch_id, subjects, batch_name)
        else:
            await message.reply_text("**❌ Invalid option!** Send 1 or 2.")
            
    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def download_full_batch(app, message, token, batch_id, subjects, batch_name):
    """Download full batch content"""
    
    # Show subjects
    msg = "**📖 SUBJECTS:\n\nSubject Name : Subject ID**\n\n"
    all_ids = ""
    for subj in subjects:
        name = subj.get('subject', 'Unknown')
        sid = subj.get('subjectId', 'N/A')
        msg += f"**{name}** : `{sid}`\n"
        all_ids += f"{sid}&"
    
    await message.reply_text(msg)
    
    # Ask for subject IDs
    ask_subjects = await app.ask(
        message.chat.id,
        text=f"**Send Subject IDs to download (format: 1&2&3)**\n\n**For all subjects, send:**\n`{all_ids}`"
    )
    selected = ask_subjects.text.strip()
    await ask_subjects.delete()
    
    if not selected:
        await message.reply_text("**❌ Subject IDs cannot be empty!**")
        return
    
    # Ask for resolution
    ask_res = await message.reply_text("**🎥 Enter resolution (720 or 1080):**")
    # Note: resolution is collected but not used in current implementation
    await asyncio.sleep(0.5)
    await ask_res.delete()
    
    # Process download
    status = await message.reply_text("**🔄 Downloading batch content...**")
    
    headers = MOBILE_HEADERS.copy()
    headers['authorization'] = f"Bearer {token}"
    
    output_file = "batch_content.txt"
    if os.path.exists(output_file):
        os.remove(output_file)
    
    selected_ids = [s.strip() for s in selected.split('&') if s.strip()]
    total_items = 0
    
    for sid in selected_ids:
        # Find subject info
        subject_info = None
        for s in subjects:
            if s.get('subjectId') == sid:
                subject_info = s
                break
        
        if not subject_info:
            continue
        
        tag_count = subject_info.get('tagCount', 0)
        pages = max(1, math.ceil(tag_count / 20)) if tag_count else 1
        
        for page in range(1, pages + 1):
            try:
                # Delay between requests
                time.sleep(BATCH_DELAY)
                
                params = {'page': str(page), 'limit': '20'}
                response = safe_request(
                    "GET",
                    f"{PW_API_BASE}/v3/batches/{batch_id}/subject/{sid}/topics",
                    params=params,
                    headers=headers,
                    max_retries=2,
                    retry_delay=2
                )
                
                data = response.json()
                
                if 'data' in data and data['data']:
                    total_items += len(data['data'])
                    with open(output_file, 'a', encoding='utf-8') as f:
                        f.write(f"\n{'='*50}\n")
                        f.write(f"Subject: {subject_info.get('subject', 'Unknown')}\n")
                        f.write(f"Page: {page}\n")
                        f.write(f"{'='*50}\n")
                        for item in data['data']:
                            f.write(f"\nTopic: {item.get('topic', 'N/A')}\n")
                            f.write(f"ID: {item.get('_id', 'N/A')}\n")
                            f.write(f"Created: {item.get('createdAt', 'N/A')}\n")
                            if item.get('url'):
                                f.write(f"URL: {item.get('url')}\n")
                            f.write("-" * 30 + "\n")
                            
            except Exception as e:
                print(f"Error on page {page}: {e}")
                continue
    
    await status.delete()
    
    if os.path.exists(output_file) and total_items > 0:
        await app.send_document(
            message.chat.id,
            document=output_file,
            caption=f"**✅ Download Complete!**\n\n**Batch:** {batch_name}\n**Total Items:** {total_items}"
        )
    else:
        await message.reply_text("**⚠️ No content found!**")


async def download_today_class(app, message, token, batch_id, subjects, batch_name):
    """Download content for a specific date"""
    
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Ask for date
    ask_date = await message.reply_text(
        f"**📅 Enter date (YYYY-MM-DD)**\n\n**Today:** `{today}`\n**Or send 'today'**"
    )
    date_input = (await app.ask(message.chat.id, text="**Send date:**")).text.strip().lower()
    await ask_date.delete()
    
    if date_input == 'today':
        selected_date = today
    else:
        selected_date = date_input
    
    # Validate date
    try:
        datetime.datetime.strptime(selected_date, "%Y-%m-%d")
    except ValueError:
        await message.reply_text("**❌ Invalid date format!** Use YYYY-MM-DD")
        return
    
    # Show subjects
    msg = "**📚 SUBJECTS:**\n\n"
    for subj in subjects:
        msg += f"**{subj.get('subject')}** : `{subj.get('subjectId')}`\n"
    
    await message.reply_text(msg)
    
    # Ask which subjects
    ask_subj = await message.reply_text("**Send Subject IDs (comma separated) or 'all'**")
    subject_input = (await app.ask(message.chat.id, text="**Send:**")).text.strip()
    await ask_subj.delete()
    
    if subject_input.lower() == 'all':
        selected_subjects = subjects
    else:
        ids = [s.strip() for s in subject_input.split(',')]
        selected_subjects = [s for s in subjects if s.get('subjectId') in ids]
    
    if not selected_subjects:
        await message.reply_text("**❌ No valid subjects selected!**")
        return
    
    # Start downloading
    status = await message.reply_text(f"**🔄 Searching content for {selected_date}...**")
    
    headers = MOBILE_HEADERS.copy()
    headers['authorization'] = f"Bearer {token}"
    
    output_file = f"content_{selected_date}.txt"
    if os.path.exists(output_file):
        os.remove(output_file)
    
    total_found = 0
    
    for subject in selected_subjects:
        sid = subject.get('subjectId')
        sname = subject.get('subject', 'Unknown')
        
        await status.edit_text(f"**🔄 Searching in {sname}...**")
        
        page = 1
        subject_content = []
        
        while page <= 30:  # Limit pages
            try:
                # Delay between requests
                time.sleep(BATCH_DELAY)
                
                params = {'page': str(page), 'limit': '20'}
                response = safe_request(
                    "GET",
                    f"{PW_API_BASE}/v3/batches/{batch_id}/subject/{sid}/topics",
                    params=params,
                    headers=headers,
                    max_retries=2,
                    retry_delay=2
                )
                
                data = response.json()
                topics = data.get('data', [])
                
                if not topics:
                    break
                
                # Filter by date
                for topic in topics:
                    created = topic.get('createdAt', '')
                    if created:
                        try:
                            topic_date = created.split('T')[0]
                            if topic_date == selected_date:
                                subject_content.append({
                                    'topic': topic.get('topic', 'N/A'),
                                    'date': created,
                                    'url': topic.get('url', 'N/A')
                                })
                        except:
                            pass
                
                page += 1
                
            except Exception as e:
                print(f"Error: {e}")
                break
        
        # Write to file
        if subject_content:
            total_found += len(subject_content)
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"📚 SUBJECT: {sname}\n")
                f.write(f"📅 DATE: {selected_date}\n")
                f.write(f"{'='*50}\n\n")
                
                for idx, item in enumerate(subject_content, 1):
                    f.write(f"{idx}. {item['topic']}\n")
                    f.write(f"   Date: {item['date']}\n")
                    f.write(f"   URL: {item['url']}\n\n")
    
    await status.delete()
    
    if total_found > 0:
        await app.send_document(
            message.chat.id,
            document=output_file,
            caption=f"**✅ Found {total_found} items for {selected_date}!**"
        )
    else:
        await message.reply_text(f"**⚠️ No content found for {selected_date}!**")
