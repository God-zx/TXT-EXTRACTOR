import requests, os, sys, re
import math
import json, asyncio
import subprocess
import datetime
from Extractor import app
from pyrogram import filters
from subprocess import getstatusoutput

# ============ UPDATED API CONFIGURATION ============
# These are the latest working configurations for PW API
PW_API_BASE = "https://api.penpencil.co"
ORGANIZATION_ID = "5eb393ee95fab7468a79d189"
CLIENT_ID = "5eb393ee95fab7468a79d189"

# Updated headers with latest client version
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Client-Id": CLIENT_ID,
    "Client-Type": "WEB",
    "Client-Version": "6.0.0",  # Updated from 2.6.12
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.pw.live",
    "Referer": "https://www.pw.live/"
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
        response = requests.post(url, params=query_params, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        resp_data = response.json()
        
        # Check if OTP was sent successfully
        if resp_data.get('success', False) or 'data' in resp_data:
            await message.reply_text("**✅ OTP Sent Successfully!**\n\nCheck your mobile number.")
            return True
        else:
            error_msg = resp_data.get('message', 'Unknown error')
            await message.reply_text(f"**❌ Failed to Send OTP**\n\nReason: `{error_msg}`")
            return False
            
    except requests.exceptions.RequestException as e:
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
    headers["Sec-Ch-Ua"] = '"Not A(Brand";v="99", "Google Chrome";v="120", "Chromium";v="120"'
    headers["Sec-Ch-Ua-Mobile"] = "?0"
    headers["Sec-Ch-Ua-Platform"] = '"Windows"'
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        resp = r.json()
        
        # Validate response structure
        if 'data' not in resp:
            error_msg = resp.get('message', 'Invalid response from server')
            await message.reply_text(f"**❌ Token Generation Failed**\n\nReason: `{error_msg}`")
            return None, None
        
        token = resp['data'].get('access_token')
        refresh_token = resp['data'].get('refresh_token', '')
        
        if not token:
            await message.reply_text("**❌ Token not found in response**")
            return None, None
            
        return token, refresh_token
        
    except requests.exceptions.RequestException as e:
        print(f"Error during token request: {e}")
        await message.reply_text(f"**❌ Failed to Generate Token**\n\nError: `{str(e)}`")
        return None, None


async def verify_token(token):
    """Verify if a token is valid by making a test API call"""
    url = f"{PW_API_BASE}/v3/users/me"
    
    headers = DEFAULT_HEADERS.copy()
    headers["Authorization"] = f"Bearer {token}"
    
    try:
        r = requests.get(url, headers=headers, timeout=30)
        
        if r.status_code == 200:
            user_data = r.json()
            if 'data' in user_data:
                return {
                    'valid': True,
                    'user_name': user_data['data'].get('name', 'Unknown'),
                    'user_mobile': user_data['data'].get('mobile', 'Unknown'),
                    'user_email': user_data['data'].get('email', 'N/A'),
                    'user_id': user_data['data'].get('_id', 'Unknown')
                }
        
        # Token is invalid
        return {'valid': False, 'error': f'Status code: {r.status_code}'}
        
    except Exception as e:
        print(f"Token verification error: {e}")
        return {'valid': False, 'error': str(e)}


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
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        resp = r.json()
        
        if 'data' in resp:
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
    This function verifies the token and returns user info.
    """
    # First verify the token
    verification = await verify_token(token)
    
    if verification['valid']:
        return {
            'valid': True,
            'token': token,  # Same token (can't truly clone)
            'user_name': verification['user_name'],
            'user_mobile': verification['user_mobile'],
            'user_email': verification['user_email'],
            'user_id': verification.get('user_id', 'Unknown'),
            'message': 'Token verified successfully. Note: Same token returned as true cloning is not supported by API.'
        }
    else:
        return {'valid': False, 'error': verification.get('error', 'Unknown error')}


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
            # Verify the token before displaying
            verification = await verify_token(token)
            
            if verification['valid']:
                token_message = f"""**✅ LOGIN SUCCESSFUL!**

**👤 User:** `{verification['user_name']}`
**📱 Mobile:** `{phone_no}`
**📧 Email:** `{verification['user_email']}`

**🔐 YOUR ACCESS TOKEN:**
`{token}`

**📋 REFRESH TOKEN:**
`{refresh_token}`

**📅 Generated:** `{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}`

**Tap to copy the token above ☝️**"""
                
                await message.reply_text(token_message)
                await pw_login(app, message, token)
            else:
                await message.reply_text("**❌ Token verification failed after generation.**")
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
            
            # Proceed with login using the verified token
            await pw_login(app, message, old_token)
        else:
            await message.reply_text(f"""**❌ INVALID TOKEN!**

The token you entered is not valid or has expired.

**Error:** `{token_info.get('error', 'Unknown error')}`

**Please try:**
• Check if token is correct
• Generate new token using Mobile/OTP method
• Contact support if issue persists""")
            
    except Exception as e:
        print(f"Error in pw_token: {e}")
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def pw_login(app, message, token):
    """Main login function to fetch batches"""
    
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
        # Fetch batches
        response = requests.get(
            f'{PW_API_BASE}/v3/batches/my-batches',
            params=params,
            headers=headers,
            timeout=30
        ).json()
        
        # Check for authentication errors
        if response.get('statusCode') == 401 or response.get('message') == 'Unauthorized':
            await message.reply_text("**❌ Token Expired or Invalid!**\n\nPlease generate a new token.")
            return
        
        if "data" not in response:
            error_msg = response.get('message', 'Unknown error')
            await message.reply_text(f"**❌ Failed to fetch batches**\n\nError: `{error_msg}`")
            return
        
        batch_data = response["data"]
        
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
    
    # Get batch details
    try:
        response2 = requests.get(
            f'{PW_API_BASE}/v3/batches/{raw_text3}/details',
            headers=headers,
            params=params,
            timeout=30
        ).json()
        
        if 'data' not in response2:
            await message.reply_text("**❌ Invalid Batch ID or batch not found!**")
            return
            
        batch_name = response2.get('data', {}).get('name', 'Unknown Batch')
        
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
            await handle_full_batch(app, message, headers, params, raw_text3, response2)
            
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
                    topic_params = {'page': str(i), 'limit': '20'}
                    response3 = requests.get(
                        f"{PW_API_BASE}/v3/batches/{batch_id}/subject/{id}/topics",
                        params=topic_params,
                        headers=headers,
                        timeout=30
                    ).json()
                    
                    if "data" in response3 and response3["data"]:
                        total_subjects += len(response3["data"])
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(f"{json.dumps(response3['data'])}\n")
                            
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
        
        # Convert date to timestamp for API
        date_obj = datetime.datetime.strptime(selected_date, "%Y-%m-%d")
        start_of_day = int(date_obj.replace(hour=0, minute=0, second=0).timestamp() * 1000)
        end_of_day = int(date_obj.replace(hour=23, minute=59, second=59).timestamp() * 1000)
        
        # Get batch subjects
        response2 = requests.get(
            f'{PW_API_BASE}/v3/batches/{batch_id}/details',
            headers=headers,
            params=params,
            timeout=30
        ).json()
        
        subjects = response2.get('data', {}).get('subjects', [])
        
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
                    topic_params = {'page': str(page), 'limit': '20'}
                    topic_response = requests.get(
                        f"{PW_API_BASE}/v3/batches/{batch_id}/subject/{subject_id}/topics",
                        params=topic_params,
                        headers=headers,
                        timeout=30
                    ).json()
                    
                    topics = topic_response.get("data", [])
                    if not topics:
                        break
                    
                    # Filter topics by date
                    for topic in topics:
                        topic_date = topic.get("createdAt", "")
                        if topic_date:
                            try:
                                # Try to parse from date string
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


# Legacy code reference (kept for reference)
"""
params1 = {'page': '1','tag': '','contentType': 'videos'}
response3 = requests.get(f'{PW_API_BASE}/v3/batches/{raw_text3}/subject/{t}/contents', params=params1, headers=headers).json()["data"]

params2 = {'page': '1','tag': '','contentType': 'notes'}
response4 = requests.get(f'{PW_API_BASE}/v3/batches/{raw_text3}/subject/{t}/contents', params=params2, headers=headers).json()["data"]
"""
