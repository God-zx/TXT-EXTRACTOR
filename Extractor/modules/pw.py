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


def get_auth_headers(token):
    """Generate authentication headers with token"""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.pw.live/",
        "Authorization": f"Bearer {token}",
        "Randomid": "990963b2-aa95-4eba-9d64-56bb55fca9a9",
        "Origin": "https://www.pw.live",
        "Client-Id": CLIENT_ID,
        "Client-Type": "WEB",
        "Client-Version": "6.0.0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }


async def fetch_and_show_batches(app, message, token):
    """Fetch and display user's batches using multiple API endpoints with enhanced error handling"""

    headers = get_auth_headers(token)

    try:
        status = await message.reply_text("**🔄 Fetching your batches...**")

        all_batches = []
        batches_found = False

        # Comprehensive list of API endpoints to try
        endpoints_to_try = [
            # Endpoint 1: Primary my-batches endpoint
            {
                'url': f"{PW_API_BASE}/v3/batches/my-batches",
                'params': {
                    'mode': '1',
                    'filter': 'false',
                    'organisationId': ORGANIZATION_ID,
                    'limit': '100',
                    'page': '1',
                },
                'name': 'v3/my-batches (mode=1)'
            },
            # Endpoint 2: purchased-batches endpoint
            {
                'url': f"{PW_API_BASE}/batch-service/v1/batches/purchased-batches",
                'params': {
                    'amount': 'paid',
                    'page': '1',
                    'type': 'ALL'
                },
                'name': 'batch-service/purchased-batches'
            },
            # Endpoint 3: Alternative my-batches without mode
            {
                'url': f"{PW_API_BASE}/v3/batches/my-batches",
                'params': {
                    'organisationId': ORGANIZATION_ID,
                    'limit': '100',
                    'page': '1'
                },
                'name': 'v3/my-batches (no mode)'
            },
            # Endpoint 4: v2 batches endpoint
            {
                'url': f"{PW_API_BASE}/v2/batches/my-batches",
                'params': {
                    'organisationId': ORGANIZATION_ID,
                    'page': '1'
                },
                'name': 'v2/my-batches'
            },
            # Endpoint 5: User batches with filter
            {
                'url': f"{PW_API_BASE}/v3/batches/my-batches",
                'params': {
                    'filter': 'true',
                    'organisationId': ORGANIZATION_ID,
                    'limit': '100'
                },
                'name': 'v3/my-batches (filtered)'
            },
            # Endpoint 6: All batches endpoint
            {
                'url': f"{PW_API_BASE}/v1/batches",
                'params': {
                    'organizationId': ORGANIZATION_ID,
                    'page': '1',
                    'limit': '100'
                },
                'name': 'v1/batches'
            }
        ]

        for endpoint in endpoints_to_try:
            if batches_found and len(all_batches) > 0:
                break

            try:
                print(f"\n=== Trying endpoint: {endpoint['name']} ===")
                print(f"URL: {endpoint['url']}")
                print(f"Params: {endpoint['params']}")
                
                response = safe_request("GET", endpoint['url'], params=endpoint['params'], 
                                       headers=headers, max_retries=2, retry_delay=2)

                if response.status_code == 401:
                    await status.edit_text("**❌ Token Expired!** Please generate a new token.")
                    return
                
                if response.status_code == 403:
                    print(f"Access forbidden for {endpoint['name']}")
                    continue

                data = response.json()
                print(f"Response status: {response.status_code}")
                print(f"Response preview: {json.dumps(data, indent=2)[:800]}")

                # Parse batches from different response structures
                batches = []

                # Try multiple data extraction patterns
                if data.get('success') == True or response.status_code == 200:
                    # Pattern 1: data.data (most common)
                    if 'data' in data and isinstance(data['data'], dict) and 'data' in data['data']:
                        if isinstance(data['data']['data'], list):
                            batches = data['data']['data']
                    
                    # Pattern 2: data as list
                    elif 'data' in data and isinstance(data['data'], list):
                        batches = data['data']
                    
                    # Pattern 3: data.batches
                    elif 'data' in data and isinstance(data['data'], dict) and 'batches' in data['data']:
                        batches = data['data']['batches']
                    
                    # Pattern 4: data.results
                    elif 'data' in data and isinstance(data['data'], dict) and 'results' in data['data']:
                        batches = data['data']['results']
                    
                    # Pattern 5: Direct results
                    elif 'results' in data:
                        batches = data['results']
                    
                    # Pattern 6: batches key
                    elif 'batches' in data:
                        batches = data['batches']

                if batches and len(batches) > 0:
                    print(f"✓ Found {len(batches)} batches from {endpoint['name']}")
                    batches_found = True
                    
                    for batch in batches:
                        # Extract batch info with multiple fallbacks
                        batch_info = {
                            'name': batch.get('name', batch.get('batchName', batch.get('title', 'Unknown'))),
                            'slug': batch.get('slug', batch.get('batchSlug', batch.get('_id', 'N/A'))),
                            '_id': batch.get('_id', batch.get('id', batch.get('batchId', 'N/A'))),
                            'startDate': batch.get('startDate', batch.get('start', '')),
                            'endDate': batch.get('endDate', batch.get('end', '')),
                            'expiryDate': batch.get('expiryDate', batch.get('expiry', '')),
                            'thumbnail': batch.get('thumbnail', batch.get('image', '')),
                            'class': batch.get('class', batch.get('standard', '')),
                            'target': batch.get('target', batch.get('exam', '')),
                            'subjectCount': batch.get('subjectCount', 0),
                            'lectureCount': batch.get('lectureCount', 0)
                        }
                        
                        # Avoid duplicates
                        if not any(b['_id'] == batch_info['_id'] for b in all_batches):
                            all_batches.append(batch_info)
                else:
                    print(f"✗ No batches found in {endpoint['name']}")

            except Exception as e:
                print(f"Error with endpoint {endpoint['name']}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue

        await status.delete()

        if not all_batches or len(all_batches) == 0:
            error_msg = """**⚠️ NO BATCHES FOUND!**

**Possible reasons:**
1. No purchased batches in your account
2. Token might be expired or invalid
3. No active subscriptions

**Solutions:**
✓ Check if you have active PW subscriptions
✓ Try generating a fresh token
✓ Verify your PW account has purchased courses

**Need help?** Contact PW support or check your account on pw.live"""
            
            await message.reply_text(error_msg)
            return

        # Display batches with enhanced formatting
        msg = f"**📚 YOUR BATCHES ({len(all_batches)} FOUND):**\n\n"
        
        for idx, batch in enumerate(all_batches, 1):
            name = batch["name"]
            batch_id = batch["_id"]
            slug = batch["slug"]
            class_info = batch.get("class", "")
            target = batch.get("target", "")
            
            msg += f"{idx}. **{name}**\n"
            msg += f"   📋 ID: `{batch_id}`\n"
            msg += f"   🔗 Slug: `{slug}`\n"
            
            if class_info:
                msg += f"   🎓 Class: {class_info}\n"
            if target:
                msg += f"   🎯 Target: {target}\n"
            
            msg += "\n"

        # Split message if too long
        if len(msg) > 4000:
            parts = [msg[i:i+3800] for i in range(0, len(msg), 3800)]
            for part in parts:
                await message.reply_text(part)
        else:
            await message.reply_text(msg)

        # Ask for batch selection
        ask_batch = await app.ask(
            message.chat.id, 
            text="**📥 SEND BATCH NUMBER (1, 2, 3...) OR BATCH ID/SLUG**\n\nExample: `1` or `batch-id` or `batch-slug`"
        )
        batch_input = ask_batch.text.strip()
        await ask_batch.delete()

        if not batch_input:
            await message.reply_text("**❌ Batch selection cannot be empty!**")
            return

        # Find batch by number, ID or slug
        selected_batch = None

        # Try to parse as number first
        try:
            batch_num = int(batch_input)
            if 1 <= batch_num <= len(all_batches):
                selected_batch = all_batches[batch_num - 1]
                print(f"Selected batch by number: {batch_num}")
        except ValueError:
            # Not a number, try to match by ID or slug
            batch_input_lower = batch_input.lower()
            for batch in all_batches:
                if (batch_input == batch['_id'] or 
                    batch_input == batch['slug'] or 
                    batch_input_lower == batch['slug'].lower() or
                    batch_input in batch['name'].lower()):
                    selected_batch = batch
                    print(f"Selected batch by ID/slug/name: {batch['name']}")
                    break

        if not selected_batch:
            await message.reply_text("**❌ Batch not found!**\n\nPlease check the number/ID/Slug and try again.")
            return

        # Delay before fetching batch details
        time.sleep(REQUEST_DELAY)
        await show_download_options(app, message, token, selected_batch)

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Critical error in fetch_and_show_batches: {error_trace}")
        await message.reply_text(f"**❌ Error fetching batches:**\n\n`{str(e)}`\n\nPlease try again or contact support.")


async def show_download_options(app, message, token, batch):
    """Show download options (Full Batch or Today Class) with enhanced batch details fetching"""

    batch_id = batch['_id']
    batch_slug = batch['slug']
    batch_name = batch['name']

    headers = get_auth_headers(token)

    try:
        # Fetch batch details using multiple endpoints
        status = await message.reply_text("**🔄 Fetching batch details...**")

        batch_data = None
        subjects = []

        # Try multiple endpoints for batch details
        detail_endpoints = [
            # Endpoint 1: Using slug
            {
                'url': f"{PW_API_BASE}/v3/batches/{batch_slug}/details",
                'identifier': batch_slug,
                'type': 'slug',
                'name': 'v3/batches/slug/details'
            },
            # Endpoint 2: Using ID
            {
                'url': f"{PW_API_BASE}/v3/batches/{batch_id}/details",
                'identifier': batch_id,
                'type': 'id',
                'name': 'v3/batches/id/details'
            },
            # Endpoint 3: v2 endpoint with slug
            {
                'url': f"{PW_API_BASE}/v2/batches/{batch_slug}",
                'identifier': batch_slug,
                'type': 'slug',
                'name': 'v2/batches/slug'
            },
            # Endpoint 4: v2 endpoint with ID
            {
                'url': f"{PW_API_BASE}/v2/batches/{batch_id}",
                'identifier': batch_id,
                'type': 'id',
                'name': 'v2/batches/id'
            },
            # Endpoint 5: v1 endpoint
            {
                'url': f"{PW_API_BASE}/v1/batches/{batch_id}",
                'identifier': batch_id,
                'type': 'id',
                'name': 'v1/batches/id'
            }
        ]

        for endpoint in detail_endpoints:
            if batch_data:
                break

            try:
                print(f"\n=== Trying detail endpoint: {endpoint['name']} ===")
                print(f"URL: {endpoint['url']}")
                
                response = safe_request("GET", endpoint['url'], headers=headers, max_retries=2, retry_delay=2)
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"Response preview: {json.dumps(data, indent=2)[:500]}")
                    
                    # Extract batch data from response
                    if 'data' in data:
                        if isinstance(data['data'], dict):
                            batch_data = data['data']
                        elif isinstance(data['data'], list) and len(data['data']) > 0:
                            batch_data = data['data'][0]
                    elif isinstance(data, dict) and '_id' in data:
                        batch_data = data
                    
                    if batch_data:
                        print(f"✓ Successfully fetched batch details from {endpoint['name']}")
                        break
                else:
                    print(f"✗ Failed with status {response.status_code}")
                    
            except Exception as e:
                print(f"Error with {endpoint['name']}: {str(e)}")
                continue

        if not batch_data:
            await status.edit_text("**❌ Could not fetch batch details!**\n\nTrying alternative method...")
            
            # Last resort: Try to fetch subjects directly
            try:
                # Try subjects endpoint directly
                subjects_url = f"{PW_API_BASE}/v2/batches/{batch_slug}/subjects"
                response = safe_request("GET", subjects_url, headers=headers, max_retries=2)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data:
                        subjects = data['data']
                        print(f"✓ Fetched subjects directly: {len(subjects)} subjects")
            except Exception as e:
                print(f"Failed to fetch subjects directly: {e}")

        # Extract subjects from batch data
        if batch_data and not subjects:
            subjects = batch_data.get('subjects', [])
            if not subjects:
                subjects = batch_data.get('subjectDetails', [])
            if not subjects:
                subjects = batch_data.get('batchSubjects', [])

        await status.delete()

        if not subjects or len(subjects) == 0:
            error_msg = f"""**❌ NO SUBJECTS FOUND!**

**Batch:** {batch_name}
**Batch ID:** `{batch_id}`

**This could mean:**
• Batch has no content yet
• Invalid batch ID/Slug
• Access denied to batch content

**Try:**
✓ Select a different batch
✓ Contact PW support
✓ Verify batch access on pw.live"""
            
            await message.reply_text(error_msg)
            return

        # Store batch info for later use
        batch_info = {
            'id': batch_id,
            'slug': batch_slug,
            'name': batch_name,
            'subjects': subjects,
            'data': batch_data
        }

        # Show subjects info
        subjects_msg = f"**📚 BATCH: {batch_name}**\n\n"
        subjects_msg += f"**Found {len(subjects)} subjects:**\n\n"
        
        for idx, subj in enumerate(subjects[:5], 1):  # Show first 5
            name = subj.get('subject', subj.get('name', 'Unknown'))
            subjects_msg += f"{idx}. {name}\n"
        
        if len(subjects) > 5:
            subjects_msg += f"\n...and {len(subjects) - 5} more subjects\n"
        
        await message.reply_text(subjects_msg)

        # Show download options
        options = f"""**📥 DOWNLOAD OPTIONS:**

**1️⃣ FULL BATCH** 
└─ Download all subjects content

**2️⃣ TODAY'S CLASS**
└─ Download specific date content

**3️⃣ BATCH BY SUBJECT**
└─ Download specific subject(s)

**Send:** `1`, `2`, or `3`"""

        ask_option = await app.ask(message.chat.id, text=options)
        option = ask_option.text.strip().lower()
        await ask_option.delete()

        if option in ["1", "full", "batch", "full batch", "all"]:
            await download_full_batch(app, message, token, batch_info)
        elif option in ["2", "today", "date", "today class", "class"]:
            await download_today_class(app, message, token, batch_info)
        elif option in ["3", "subject", "subjects", "by subject"]:
            await download_by_subject(app, message, token, batch_info)
        else:
            await message.reply_text("**❌ Invalid option!** Send 1, 2, or 3.")

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in show_download_options: {error_trace}")
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def download_full_batch(app, message, token, batch_info):
    """Download full batch content with enhanced subject handling"""

    batch_slug = batch_info['slug']
    batch_name = batch_info['name']
    subjects = batch_info['subjects']

    # Show subjects with details
    msg = "**📖 AVAILABLE SUBJECTS:**\n\n"
    for idx, subj in enumerate(subjects, 1):
        name = subj.get('subject', subj.get('name', 'Unknown'))
        sid = subj.get('_id', subj.get('id', 'N/A'))
        slug = subj.get('slug', 'N/A')
        lecture_count = subj.get('lectureCount', subj.get('videoCount', 0))
        
        msg += f"**{idx}. {name}**\n"
        msg += f"   ID: `{sid}`\n"
        msg += f"   Slug: `{slug}`\n"
        if lecture_count:
            msg += f"   📹 Videos: {lecture_count}\n"
        msg += "\n"

    # Split if too long
    if len(msg) > 4000:
        parts = [msg[i:i+3800] for i in range(0, len(msg), 3800)]
        for part in parts:
            await message.reply_text(part)
    else:
        await message.reply_text(msg)

    # Ask for subject selection
    ask_subjects = await app.ask(
        message.chat.id,
        text="""**SELECT SUBJECTS:**

**Options:**
• Send `all` - Download all subjects
• Send numbers - Example: `1,2,3`
• Send slugs - Example: `physics&chemistry`

**Your choice:**"""
    )
    selected = ask_subjects.text.strip()
    await ask_subjects.delete()

    if not selected:
        await message.reply_text("**❌ Selection cannot be empty!**")
        return

    # Process selection
    selected_subjects = []
    if selected.lower() == 'all':
        selected_subjects = subjects
    else:
        # Try to parse as numbers first
        try:
            nums = [int(x.strip()) for x in selected.replace(',', ' ').split()]
            for num in nums:
                if 1 <= num <= len(subjects):
                    selected_subjects.append(subjects[num - 1])
        except ValueError:
            # Try as slugs
            slugs = [s.strip() for s in selected.replace(',', '&').split('&') if s.strip()]
            for slug in slugs:
                for subj in subjects:
                    if subj.get('slug', '').lower() == slug.lower():
                        selected_subjects.append(subj)
                        break

    if not selected_subjects:
        await message.reply_text("**❌ No valid subjects selected!**")
        return

    # Start download
    status = await message.reply_text(f"**🔄 Downloading {len(selected_subjects)} subject(s)...**")

    headers = get_auth_headers(token)

    output_file = f"batch_{batch_slug[:20]}.txt"
    if os.path.exists(output_file):
        os.remove(output_file)

    total_items = 0

    for subject in selected_subjects:
        subject_slug = subject.get('slug', '')
        subject_id = subject.get('_id', '')
        subject_name = subject.get('subject', subject.get('name', 'Unknown'))
        
        if not subject_slug and not subject_id:
            print(f"Skipping {subject_name} - no slug or ID")
            continue

        await status.edit_text(f"**🔄 Downloading: {subject_name}...**")

        # Determine pagination
        tag_count = subject.get('tagCount', subject.get('topicCount', 0))
        lecture_count = subject.get('lectureCount', subject.get('videoCount', 0))
        total_count = max(tag_count, lecture_count)
        
        pages = max(1, math.ceil(total_count / 20)) if total_count else 10  # Default 10 pages

        subject_items = []

        for page in range(1, min(pages + 1, 50)):  # Max 50 pages safety limit
            try:
                time.sleep(BATCH_DELAY)

                # Try multiple API endpoints for topics
                topics = []
                
                # Endpoint 1: v2/batches with subject slug
                if subject_slug:
                    url = f"{PW_API_BASE}/v2/batches/{batch_slug}/subject/{subject_slug}/topics"
                    params = {'page': page}
                    
                    response = safe_request("GET", url, params=params, headers=headers, max_retries=2, retry_delay=2)
                    
                    if response.status_code == 200:
                        data = response.json()
                        topics = data.get('data', [])
                
                # Endpoint 2: Fallback with subject ID if slug failed
                if not topics and subject_id:
                    url = f"{PW_API_BASE}/v2/batches/{batch_slug}/subject/{subject_id}/contents"
                    params = {'page': page}
                    
                    response = safe_request("GET", url, params=params, headers=headers, max_retries=2, retry_delay=2)
                    
                    if response.status_code == 200:
                        data = response.json()
                        topics = data.get('data', [])

                if not topics:
                    if page == 1:
                        print(f"No topics found for {subject_name} on first page")
                    break

                total_items += len(topics)
                subject_items.extend(topics)

            except Exception as e:
                print(f"Error on page {page} for {subject_name}: {e}")
                if page > 3:  # Continue if we got some pages
                    break
                continue

        # Write subject content to file
        if subject_items:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"📚 SUBJECT: {subject_name}\n")
                f.write(f"📊 Total Items: {len(subject_items)}\n")
                f.write(f"{'='*70}\n\n")

                for idx, topic in enumerate(subject_items, 1):
                    f.write(f"{idx}. 📖 Topic: {topic.get('name', 'N/A')}\n")
                    f.write(f"   ID: {topic.get('_id', 'N/A')}\n")
                    f.write(f"   Slug: {topic.get('slug', 'N/A')}\n")

                    # Videos
                    videos = topic.get('videos', topic.get('videoResources', []))
                    if videos:
                        f.write(f"   🎥 Videos: {len(videos)}\n")
                        for v in videos[:5]:  # First 5 videos
                            f.write(f"      • {v.get('topic', v.get('name', 'N/A'))}\n")
                            video_url = v.get('url', v.get('videoUrl', ''))
                            if video_url:
                                f.write(f"        URL: {video_url}\n")

                    # Notes
                    notes = topic.get('notes', topic.get('noteResources', []))
                    if notes:
                        f.write(f"   📝 Notes: {len(notes)}\n")

                    # DPP/Exercises
                    exercises = topic.get('exercises', topic.get('dpp', []))
                    if exercises:
                        f.write(f"   📋 DPP/Exercises: {len(exercises)}\n")

                    f.write("-" * 70 + "\n")

    await status.delete()

    if os.path.exists(output_file) and total_items > 0:
        caption = f"""**✅ DOWNLOAD COMPLETE!**

**📚 Batch:** {batch_name}
**📊 Subjects:** {len(selected_subjects)}
**📝 Total Topics:** {total_items}

**Generated:** {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""

        await app.send_document(
            message.chat.id,
            document=output_file,
            caption=caption
        )
        
        # Cleanup
        try:
            os.remove(output_file)
        except:
            pass
    else:
        await message.reply_text("**⚠️ No content found or download failed!**")


async def download_by_subject(app, message, token, batch_info):
    """Download specific subject(s) - same as download_full_batch but with better naming"""
    await download_full_batch(app, message, token, batch_info)


async def download_today_class(app, message, token, batch_info):
    """Download content for a specific date with enhanced date handling"""

    batch_slug = batch_info['slug']
    batch_name = batch_info['name']
    subjects = batch_info['subjects']

    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # Ask for date
    date_msg = f"""**📅 ENTER DATE**

**Format:** YYYY-MM-DD
**Example:** 2024-01-15

**Quick options:**
• Send `today` for today ({today})
• Send `yesterday` for yesterday

**Your input:**"""

    ask_date_text = await message.reply_text(date_msg)
    date_response = await app.ask(message.chat.id, text="**Date:**")
    date_input = date_response.text.strip().lower()
    await ask_date_text.delete()
    await date_response.delete()

    # Process date input
    if date_input == 'today':
        selected_date = today
    elif date_input == 'yesterday':
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        selected_date = yesterday
    else:
        selected_date = date_input

    # Validate date format
    try:
        date_obj = datetime.datetime.strptime(selected_date, "%Y-%m-%d")
    except ValueError:
        await message.reply_text("**❌ Invalid date format!**\n\nUse YYYY-MM-DD format (e.g., 2024-01-15)")
        return

    # Show subjects
    msg = "**📚 SELECT SUBJECTS:**\n\n"
    for idx, subj in enumerate(subjects, 1):
        name = subj.get('subject', subj.get('name', 'Unknown'))
        msg += f"{idx}. {name}\n"

    msg += f"\n**Send:** Numbers (1,2,3) or `all`"

    await message.reply_text(msg)

    # Ask which subjects
    ask_subj = await message.reply_text("**Your selection:**")
    subject_response = await app.ask(message.chat.id, text="**Subjects:**")
    subject_input = subject_response.text.strip()
    await ask_subj.delete()
    await subject_response.delete()

    # Process subject selection
    if subject_input.lower() == 'all':
        selected_subjects = subjects
    else:
        try:
            nums = [int(x.strip()) for x in subject_input.replace(',', ' ').split()]
            selected_subjects = []
            for num in nums:
                if 1 <= num <= len(subjects):
                    selected_subjects.append(subjects[num - 1])
        except ValueError:
            await message.reply_text("**❌ Invalid subject selection!**")
            return

    if not selected_subjects:
        await message.reply_text("**❌ No valid subjects selected!**")
        return

    # Start searching
    status = await message.reply_text(f"**🔍 Searching for classes on {selected_date}...**")

    headers = get_auth_headers(token)

    output_file = f"classes_{selected_date}.txt"
    if os.path.exists(output_file):
        os.remove(output_file)

    total_found = 0
    all_results = []

    for subject in selected_subjects:
        subject_slug = subject.get('slug', '')
        subject_id = subject.get('_id', '')
        subject_name = subject.get('subject', subject.get('name', 'Unknown'))

        await status.edit_text(f"**🔍 Searching in {subject_name}...**")

        subject_content = []
        page = 1
        max_pages = 20  # Reasonable limit for date search

        while page <= max_pages:
            try:
                time.sleep(BATCH_DELAY)

                # Fetch topics
                topics = []
                
                if subject_slug:
                    url = f"{PW_API_BASE}/v2/batches/{batch_slug}/subject/{subject_slug}/topics"
                    params = {'page': page}
                    
                    response = safe_request("GET", url, params=params, headers=headers, max_retries=2, retry_delay=2)
                    
                    if response.status_code == 200:
                        data = response.json()
                        topics = data.get('data', [])

                if not topics:
                    break

                # Filter by date
                for topic in topics:
                    videos = topic.get('videos', topic.get('videoResources', []))
                    
                    for video in videos:
                        video_date = video.get('date', video.get('createdAt', ''))
                        
                        if video_date:
                            try:
                                # Parse date - handle multiple formats
                                if 'T' in video_date:
                                    v_date = video_date.split('T')[0]
                                elif ' ' in video_date:
                                    v_date = video_date.split(' ')[0]
                                else:
                                    v_date = video_date[:10]
                                
                                # Match date
                                if v_date == selected_date:
                                    teachers = video.get('teachers', video.get('faculty', []))
                                    teacher_name = 'Unknown'
                                    if teachers and len(teachers) > 0:
                                        teacher = teachers[0]
                                        if isinstance(teacher, dict):
                                            teacher_name = teacher.get('firstName', '') + ' ' + teacher.get('lastName', '')
                                            teacher_name = teacher_name.strip() or 'Unknown'
                                        elif isinstance(teacher, str):
                                            teacher_name = teacher
                                    
                                    video_info = {
                                        'subject': subject_name,
                                        'topic': topic.get('name', 'N/A'),
                                        'video_topic': video.get('topic', video.get('name', 'N/A')),
                                        'date': video_date,
                                        'url': video.get('url', video.get('videoUrl', 'N/A')),
                                        'duration': video.get('videoDetails', {}).get('duration', 
                                                    video.get('duration', 'N/A')),
                                        'teacher': teacher_name,
                                        'video_id': video.get('_id', video.get('id', 'N/A'))
                                    }
                                    
                                    subject_content.append(video_info)
                                    total_found += 1
                            except Exception as e:
                                print(f"Date parsing error: {e}")
                                continue

                page += 1

            except Exception as e:
                print(f"Error searching in {subject_name}: {e}")
                break

        if subject_content:
            all_results.extend(subject_content)

    await status.delete()

    if total_found > 0:
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"{'='*70}\n")
            f.write(f"📅 CLASSES FOR: {selected_date}\n")
            f.write(f"📚 Batch: {batch_name}\n")
            f.write(f"🎥 Total Videos: {total_found}\n")
            f.write(f"{'='*70}\n\n")

            # Group by subject
            subjects_dict = {}
            for item in all_results:
                subj = item['subject']
                if subj not in subjects_dict:
                    subjects_dict[subj] = []
                subjects_dict[subj].append(item)

            for subject_name, videos in subjects_dict.items():
                f.write(f"\n{'─'*70}\n")
                f.write(f"📚 SUBJECT: {subject_name}\n")
                f.write(f"🎥 Videos: {len(videos)}\n")
                f.write(f"{'─'*70}\n\n")

                for idx, video in enumerate(videos, 1):
                    f.write(f"{idx}. 📖 {video['topic']}\n")
                    f.write(f"   🎥 Video: {video['video_topic']}\n")
                    f.write(f"   👨‍🏫 Teacher: {video['teacher']}\n")
                    f.write(f"   ⏱️ Duration: {video['duration']}\n")
                    f.write(f"   📅 Date: {video['date']}\n")
                    f.write(f"   🔗 URL: {video['url']}\n")
                    f.write(f"   🆔 Video ID: {video['video_id']}\n")
                    f.write("\n")

        caption = f"""**✅ CLASSES FOUND!**

**📅 Date:** {selected_date}
**📚 Batch:** {batch_name}
**🎥 Total Videos:** {total_found}
**📊 Subjects:** {len(subjects_dict)}

**Generated:** {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""

        await app.send_document(
            message.chat.id,
            document=output_file,
            caption=caption
        )
        
        # Cleanup
        try:
            os.remove(output_file)
        except:
            pass
    else:
        await message.reply_text(f"**⚠️ NO CLASSES FOUND FOR {selected_date}!**\n\nTry a different date or check if classes were scheduled.")
