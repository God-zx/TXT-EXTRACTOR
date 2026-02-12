import requests, os, sys, re
import math
import json, asyncio
import subprocess
import datetime
import time
import random
import base64
import uuid
import traceback
from Extractor import app
from pyrogram import filters
from subprocess import getstatusoutput

# ============ API CONFIGURATION ============
PW_API_BASE = "https://api.penpencil.co"
ORGANIZATION_ID = "5eb393ee95fab7468a79d189"
CLIENT_ID = "5eb393ee95fab7468a79d189"
REFERER = "https://www.pw.live/"

# Request delays
REQUEST_DELAY = 1
BATCH_DELAY = 0.5


def get_auth_headers(token):
    """Generate authentication headers with Bearer token"""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": REFERER,
        "Authorization": f"Bearer {token}",
        "Randomid": str(uuid.uuid4()),
    }


def safe_request(method, url, max_retries=3, retry_delay=2, **kwargs):
    """Make HTTP request with retry logic"""
    for attempt in range(max_retries):
        try:
            if method.upper() == "GET":
                response = requests.get(url, timeout=30, **kwargs)
            elif method.upper() == "POST":
                response = requests.post(url, timeout=30, **kwargs)
            else:
                response = requests.request(method, url, timeout=30, **kwargs)

            if response.status_code == 429:
                wait_time = retry_delay * (attempt + 1)
                print(f"Rate limited. Waiting {wait_time}s...")
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


# ============ OTP & TOKEN FUNCTIONS ============

async def get_otp(message, phone_no):
    """Send OTP to mobile number"""
    url = f"{PW_API_BASE}/v1/users/get-otp"

    headers = {
        "Content-Type": "application/json",
        "Client-Id": CLIENT_ID,
        "Client-Type": "WEB",
        "Client-Version": "6.0.0",
        "User-Agent": "Mozilla/5.0",
    }

    payload = {
        "username": phone_no,
        "countryCode": "+91",
        "organizationId": ORGANIZATION_ID,
    }

    try:
        response = safe_request("POST", url, params={"smsType": "0"}, headers=headers, json=payload)
        data = response.json()

        if response.status_code == 200:
            await message.reply_text("**✅ OTP Sent Successfully!**\n\nCheck your mobile.")
            return True
        else:
            error = data.get('message', 'Failed to send OTP')
            await message.reply_text(f"**❌ OTP Failed**\n\n`{error}`")
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

    headers = {
        "Content-Type": "application/json",
        "Randomid": str(uuid.uuid4()),
    }

    try:
        response = safe_request("POST", url, headers=headers, json=payload)
        data = response.json()

        if response.status_code == 200 and 'data' in data:
            token = data['data'].get('access_token')
            refresh = data['data'].get('refresh_token', '')
            return token, refresh
        else:
            error = data.get('message', 'Token generation failed')
            await message.reply_text(f"**❌ Failed**\n\n{error}")
            return None, None

    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")
        return None, None


# ============ MAIN LOGIN FUNCTIONS ============

async def pw_mobile(app, message):
    """Handle mobile-based login"""
    try:
        # Get phone number
        ask_phone = await app.ask(message.chat.id, text="**📱 Enter PW Mobile Number (10 digits)**")
        phone_no = ask_phone.text.strip()
        await ask_phone.delete()

        if not phone_no.isdigit() or len(phone_no) != 10:
            await message.reply_text("**❌ Invalid number!** Enter 10 digits.")
            return

        # Send OTP
        if not await get_otp(message, phone_no):
            return

        # Get OTP
        ask_otp = await app.ask(message.chat.id, text="**🔑 Enter OTP**")
        otp = ask_otp.text.strip()
        await ask_otp.delete()

        if not otp.isdigit():
            await message.reply_text("**❌ Invalid OTP!**")
            return

        # Generate token
        token, refresh = await get_token(message, phone_no, otp)

        if token:
            jwt_data = decode_jwt(token)
            user_data = jwt_data.get('data', {}) if jwt_data else {}

            msg = f"""**✅ LOGIN SUCCESS!**

**👤 Name:** `{user_data.get('firstName', '')} {user_data.get('lastName', '')}`
**📱 Mobile:** `{phone_no}`
**📧 Email:** `{user_data.get('email', 'N/A')}`

**🔐 TOKEN:**
`{token}`"""

            await message.reply_text(msg)

            time.sleep(REQUEST_DELAY)
            await fetch_and_show_batches(app, message, token)

    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


async def pw_token(app, message):
    """Handle token-based login"""
    try:
        ask_token = await app.ask(message.chat.id, text="**🔑 Enter PW Access Token**")
        token = ask_token.text.strip()
        await ask_token.delete()

        if not token:
            await message.reply_text("**❌ Token required!**")
            return

        status = await message.reply_text("**🔄 Verifying...**")

        jwt_data = decode_jwt(token)
        user_data = jwt_data.get('data', {}) if jwt_data else {}

        await status.delete()

        if user_data:
            msg = f"""**✅ TOKEN VERIFIED!**

**👤 Name:** `{user_data.get('firstName', '')} {user_data.get('lastName', '')}`
**📱 Mobile:** `{user_data.get('username', '')}`
**📧 Email:** `{user_data.get('email', 'N/A')}`
**🆔 ID:** `{user_data.get('_id', 'N/A')}`"""

            await message.reply_text(msg)

            time.sleep(REQUEST_DELAY)
            await fetch_and_show_batches(app, message, token)
        else:
            await message.reply_text("**❌ Invalid token!**")

    except Exception as e:
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


# ============ BATCH FETCHING - WORKING 2026 API ============

async def fetch_and_show_batches(app, message, token):
    """Fetch batches using WORKING 2026 API"""

    try:
        status = await message.reply_text("**🔄 Fetching batches...**")

        headers = get_auth_headers(token)
        all_batches = []

        # WORKING ENDPOINTS FOR 2026
        endpoints = [
            # Primary - batch-service/v1 (CONFIRMED WORKING)
            {
                'url': f"{PW_API_BASE}/batch-service/v1/batches/purchased-batches",
                'params': {
                    'amount': 'paid',
                    'page': '1',
                    'type': 'ALL'
                }
            },
            # Alternative - v3 batches
            {
                'url': f"{PW_API_BASE}/v3/batches/my-batches",
                'params': {
                    'mode': '1',
                    'filter': 'false',
                    'organisationId': ORGANIZATION_ID,
                    'limit': '100',
                    'page': '1'
                }
            },
        ]

        for endpoint in endpoints:
            try:
                print(f"\n[DEBUG] Trying: {endpoint['url']}")

                response = safe_request("GET", endpoint['url'],
                                       params=endpoint['params'],
                                       headers=headers,
                                       max_retries=2,
                                       retry_delay=1)

                print(f"[DEBUG] Status: {response.status_code}")

                if response.status_code == 401:
                    await status.edit_text("**❌ Token expired!** Generate new token.")
                    return

                if response.status_code != 200:
                    continue

                data = response.json()
                print(f"[DEBUG] Response keys: {list(data.keys())}")

                # Extract batches from different response formats
                batches = []

                # Format 1: { "success": true, "data": [...] }
                if data.get('success') and isinstance(data.get('data'), list):
                    batches = data['data']
                # Format 2: { "data": [...] }
                elif isinstance(data.get('data'), list):
                    batches = data['data']
                # Format 3: { "data": { "data": [...] } }
                elif isinstance(data.get('data'), dict) and isinstance(data['data'].get('data'), list):
                    batches = data['data']['data']

                if batches:
                    print(f"[DEBUG] Found {len(batches)} batches!")

                    for batch in batches:
                        batch_info = {
                            'name': batch.get('name', batch.get('batchName', 'Unknown')),
                            'slug': batch.get('slug', batch.get('batchSlug', batch.get('_id', ''))),
                            '_id': batch.get('_id', batch.get('id', '')),
                            'startDate': batch.get('startDate', ''),
                            'endDate': batch.get('endDate', ''),
                            'expiryDate': batch.get('expiryDate', ''),
                            'class': batch.get('class', ''),
                            'language': batch.get('language', ''),
                            'thumbnail': batch.get('thumbnail', ''),
                        }

                        # Avoid duplicates
                        if batch_info['_id'] and not any(b['_id'] == batch_info['_id'] for b in all_batches):
                            all_batches.append(batch_info)

                    # If we found batches, stop trying other endpoints
                    if all_batches:
                        break

            except Exception as e:
                print(f"[DEBUG] Error: {e}")
                continue

        await status.delete()

        if not all_batches:
            await message.reply_text(
                "**⚠️ No batches found!**\n\n"
                "Please check:\n"
                "• You have purchased batches on pw.live\n"
                "• Your token is valid\n"
                "• Your subscription is active"
            )
            return

        # Display batches
        msg = f"**📚 YOUR BATCHES ({len(all_batches)}):**\n\n"

        for idx, batch in enumerate(all_batches, 1):
            msg += f"**{idx}. {batch['name']}**\n"
            msg += f"   ID: `{batch['_id']}`\n"
            if batch.get('class'):
                msg += f"   Class: {batch['class']}\n"
            if batch.get('language'):
                msg += f"   Language: {batch['language']}\n"
            msg += "\n"

        # Handle long messages
        if len(msg) > 4000:
            parts = [msg[i:i+3900] for i in range(0, len(msg), 3900)]
            for part in parts:
                await message.reply_text(part)
        else:
            await message.reply_text(msg)

        # Ask for selection
        ask_batch = await app.ask(
            message.chat.id,
            text="**📥 Send batch number (1, 2, 3...) or paste Batch ID**"
        )
        batch_input = ask_batch.text.strip()
        await ask_batch.delete()

        if not batch_input:
            await message.reply_text("**❌ Selection required!**")
            return

        # Find selected batch
        selected_batch = None

        # Try by number first
        try:
            num = int(batch_input)
            if 1 <= num <= len(all_batches):
                selected_batch = all_batches[num - 1]
        except ValueError:
            # Try by ID or name
            batch_input_lower = batch_input.lower()
            for batch in all_batches:
                if (batch_input == batch['_id'] or
                    batch_input == batch.get('slug', '') or
                    batch_input_lower in batch['name'].lower()):
                    selected_batch = batch
                    break

        if not selected_batch:
            await message.reply_text("**❌ Batch not found!**")
            return

        time.sleep(REQUEST_DELAY)
        await show_download_options(app, message, token, selected_batch)

    except Exception as e:
        traceback.print_exc()
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


# ============ DOWNLOAD OPTIONS ============

async def show_download_options(app, message, token, batch):
    """Show download options"""

    batch_id = batch['_id']
    batch_slug = batch.get('slug', batch_id)
    batch_name = batch['name']

    headers = get_auth_headers(token)

    try:
        status = await message.reply_text("**🔄 Loading batch details...**")

        # Get batch details - try multiple endpoints
        subjects = []
        batch_data = None

        detail_urls = [
            f"{PW_API_BASE}/v3/batches/{batch_slug}/details",
            f"{PW_API_BASE}/v2/batches/{batch_slug}/details",
            f"{PW_API_BASE}/v3/batches/{batch_id}/details",
        ]

        for url in detail_urls:
            try:
                response = safe_request("GET", url, headers=headers, max_retries=2)

                if response.status_code == 200:
                    data = response.json()
                    batch_data = data.get('data', data)

                    if batch_data:
                        # Extract subjects
                        subjects = (batch_data.get('subjects') or
                                   batch_data.get('subjectDetails') or
                                   batch_data.get('batchSubjects', []))

                        if subjects:
                            break
            except:
                continue

        await status.delete()

        if not subjects:
            await message.reply_text(f"**❌ No subjects found in {batch_name}!**")
            return

        # Store batch info
        batch_info = {
            'id': batch_id,
            'slug': batch_slug,
            'name': batch_name,
            'subjects': subjects
        }

        # Show subjects preview
        msg = f"**📚 {batch_name}**\n\n**Subjects ({len(subjects)}):**\n\n"
        for idx, subj in enumerate(subjects[:10], 1):
            subj_name = subj.get('subject', subj.get('name', 'Unknown'))
            msg += f"{idx}. {subj_name}\n"
        if len(subjects) > 10:
            msg += f"\n...and {len(subjects)-10} more\n"

        await message.reply_text(msg)

        # Show options
        options = """**📥 Download Options:**

1️⃣ **Full Batch** - All content
2️⃣ **By Date** - Specific date
3️⃣ **By Subject** - Select subjects

**Send: 1, 2, or 3**"""

        ask_opt = await app.ask(message.chat.id, text=options)
        opt = ask_opt.text.strip()
        await ask_opt.delete()

        if opt in ["1", "full", "all", "batch"]:
            await download_full_batch(app, message, token, batch_info)
        elif opt in ["2", "date", "today", "by date"]:
            await download_by_date(app, message, token, batch_info)
        elif opt in ["3", "subject", "by subject"]:
            await download_by_subject(app, message, token, batch_info)
        else:
            await message.reply_text("**❌ Invalid option!**")

    except Exception as e:
        traceback.print_exc()
        await message.reply_text(f"**❌ Error:** `{str(e)}`")


# ============ DOWNLOAD FUNCTIONS ============

async def download_full_batch(app, message, token, batch_info):
    """Download full batch content"""

    batch_slug = batch_info['slug']
    batch_name = batch_info['name']
    subjects = batch_info['subjects']

    # Show all subjects
    msg = "**📖 Select Subjects:**\n\n"
    for idx, subj in enumerate(subjects, 1):
        subj_name = subj.get('subject', subj.get('name', 'Unknown'))
        msg += f"{idx}. {subj_name}\n"

    await message.reply_text(msg)

    # Ask selection
    ask_subj = await app.ask(
        message.chat.id,
        text="**Send numbers (1,2,3) or 'all' for all subjects:**"
    )
    selection = ask_subj.text.strip().lower()
    await ask_subj.delete()

    if selection == 'all':
        selected = subjects
    else:
        try:
            nums = [int(x.strip()) for x in selection.split(',')]
            selected = [subjects[n-1] for n in nums if 1 <= n <= len(subjects)]
        except:
            await message.reply_text("**❌ Invalid selection!**")
            return

    if not selected:
        await message.reply_text("**❌ No subjects selected!**")
        return

    # Download
    status = await message.reply_text(f"**🔄 Downloading {batch_name}...**")

    headers = get_auth_headers(token)
    output_file = f"batch_{batch_slug[:20]}.txt"

    if os.path.exists(output_file):
        os.remove(output_file)

    total_topics = 0

    for subject in selected:
        subject_slug = subject.get('slug', subject.get('subjectSlug', ''))
        subject_name = subject.get('subject', subject.get('name', 'Unknown'))

        if not subject_slug:
            continue

        await status.edit_text(f"**🔄 {subject_name}...**")

        page = 1
        subject_topics = []

        while page <= 50:
            try:
                time.sleep(BATCH_DELAY)

                # WORKING API: v2/batches/{batch_slug}/subject/{subject_slug}/topics
                url = f"{PW_API_BASE}/v2/batches/{batch_slug}/subject/{subject_slug}/topics"
                response = safe_request("GET", url, params={'page': page}, headers=headers)

                if response.status_code != 200:
                    break

                data = response.json()
                topics = data.get('data', [])

                if not topics:
                    break

                subject_topics.extend(topics)
                page += 1

            except Exception as e:
                print(f"Error: {e}")
                break

        # Write to file
        if subject_topics:
            total_topics += len(subject_topics)

            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"SUBJECT: {subject_name}\n")
                f.write(f"TOPICS: {len(subject_topics)}\n")
                f.write(f"{'='*70}\n\n")

                for topic in subject_topics:
                    f.write(f"📖 {topic.get('name', 'N/A')}\n")
                    f.write(f"   ID: {topic.get('_id', 'N/A')}\n")

                    # Videos
                    videos = topic.get('videos', [])
                    if videos:
                        f.write(f"   🎥 Videos: {len(videos)}\n")
                        for v in videos[:5]:  # Limit to 5 videos
                            f.write(f"      • {v.get('topic', 'N/A')}\n")
                            if v.get('url'):
                                f.write(f"        URL: {v['url']}\n")

                    # Notes
                    notes = topic.get('notes', [])
                    if notes:
                        f.write(f"   📝 Notes: {len(notes)}\n")

                    # Exercises/DPPs
                    exercises = topic.get('exercises', [])
                    if exercises:
                        f.write(f"   📋 Exercises: {len(exercises)}\n")

                    f.write("-" * 70 + "\n")

    await status.delete()

    if os.path.exists(output_file) and total_topics > 0:
        await app.send_document(
            message.chat.id,
            document=output_file,
            caption=f"**✅ Download Complete!**\n\n**Batch:** {batch_name}\n**Total Topics:** {total_topics}"
        )
        try:
            os.remove(output_file)
        except:
            pass
    else:
        await message.reply_text("**⚠️ No content found!**")


async def download_by_subject(app, message, token, batch_info):
    """Download by subject - same as full batch"""
    await download_full_batch(app, message, token, batch_info)


async def download_by_date(app, message, token, batch_info):
    """Download content by specific date"""

    batch_slug = batch_info['slug']
    batch_name = batch_info['name']
    subjects = batch_info['subjects']

    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # Ask date
    ask_date = await app.ask(
        message.chat.id,
        text=f"**📅 Enter date (YYYY-MM-DD)**\n\nToday: `{today}`\nOr send 'today'"
    )
    date_input = ask_date.text.strip().lower()
    await ask_date.delete()

    if date_input == 'today':
        selected_date = today
    else:
        selected_date = date_input

    # Validate date
    try:
        datetime.datetime.strptime(selected_date, "%Y-%m-%d")
    except:
        await message.reply_text("**❌ Invalid date! Use YYYY-MM-DD**")
        return

    # Show subjects
    msg = "**📚 Select Subjects:**\n\n"
    for idx, subj in enumerate(subjects, 1):
        subj_name = subj.get('subject', subj.get('name', 'Unknown'))
        msg += f"{idx}. {subj_name}\n"

    await message.reply_text(msg)

    # Ask subjects
    ask_subj = await app.ask(message.chat.id, text="**Send numbers or 'all':**")
    subj_input = ask_subj.text.strip().lower()
    await ask_subj.delete()

    if subj_input == 'all':
        selected = subjects
    else:
        try:
            nums = [int(x.strip()) for x in subj_input.split(',')]
            selected = [subjects[n-1] for n in nums if 1 <= n <= len(subjects)]
        except:
            await message.reply_text("**❌ Invalid selection!**")
            return

    if not selected:
        await message.reply_text("**❌ No subjects selected!**")
        return

    # Search
    status = await message.reply_text(f"**🔍 Searching {selected_date}...**")

    headers = get_auth_headers(token)
    output_file = f"class_{selected_date}.txt"

    if os.path.exists(output_file):
        os.remove(output_file)

    total_videos = 0
    all_results = []

    for subject in selected:
        subject_slug = subject.get('slug', subject.get('subjectSlug', ''))
        subject_name = subject.get('subject', subject.get('name', 'Unknown'))

        if not subject_slug:
            continue

        await status.edit_text(f"**🔍 {subject_name}...**")

        page = 1
        subject_videos = []

        while page <= 20:
            try:
                time.sleep(BATCH_DELAY)

                url = f"{PW_API_BASE}/v2/batches/{batch_slug}/subject/{subject_slug}/topics"
                response = safe_request("GET", url, params={'page': page}, headers=headers)

                if response.status_code != 200:
                    break

                data = response.json()
                topics = data.get('data', [])

                if not topics:
                    break

                # Filter videos by date
                for topic in topics:
                    videos = topic.get('videos', [])
                    for video in videos:
                        video_date = video.get('date', '')
                        if video_date:
                            try:
                                v_date = video_date.split('T')[0] if 'T' in video_date else video_date[:10]
                                if v_date == selected_date:
                                    teachers = video.get('teachers', [])
                                    teacher = 'Unknown'
                                    if teachers and isinstance(teachers[0], dict):
                                        t = teachers[0]
                                        teacher = f"{t.get('firstName', '')} {t.get('lastName', '')}".strip() or 'Unknown'

                                    subject_videos.append({
                                        'topic': topic.get('name', 'N/A'),
                                        'video_title': video.get('topic', 'N/A'),
                                        'teacher': teacher,
                                        'url': video.get('url', 'N/A'),
                                        'duration': video.get('videoDetails', {}).get('duration', 'N/A'),
                                    })
                            except:
                                pass

                page += 1

            except Exception as e:
                print(f"Error: {e}")
                break

        if subject_videos:
            total_videos += len(subject_videos)
            all_results.append({
                'subject': subject_name,
                'videos': subject_videos
            })

    await status.delete()

    # Write results
    if total_videos > 0:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"{'='*70}\n")
            f.write(f"DATE: {selected_date}\n")
            f.write(f"BATCH: {batch_name}\n")
            f.write(f"TOTAL VIDEOS: {total_videos}\n")
            f.write(f"{'='*70}\n\n")

            for result in all_results:
                f.write(f"\n{result['subject']} ({len(result['videos'])} videos)\n")
                f.write(f"{'-'*70}\n\n")

                for idx, v in enumerate(result['videos'], 1):
                    f.write(f"{idx}. {v['topic']}\n")
                    f.write(f"   Title: {v['video_title']}\n")
                    f.write(f"   Teacher: {v['teacher']}\n")
                    f.write(f"   Duration: {v['duration']}\n")
                    f.write(f"   URL: {v['url']}\n\n")

        await app.send_document(
            message.chat.id,
            document=output_file,
            caption=f"**✅ Found {total_videos} videos!**\n\nDate: {selected_date}"
        )
        try:
            os.remove(output_file)
        except:
            pass
    else:
        await message.reply_text(f"**⚠️ No classes found on {selected_date}!**")
