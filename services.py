# services.py (Final corrected full version)

import os
import io
import logging
import uuid
import threading
import re
from datetime import datetime, date
from typing import List, Dict, Optional, Any
from google.cloud import storage
from PIL import Image
from moviepy.editor import VideoFileClip
from urllib.parse import unquote
from database import get_db_connection, execute_query, execute_query_one
from utils.email_utils import send_passenger_complain_email
from dotenv import load_dotenv
from fastapi import UploadFile, HTTPException
import asyncio

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'sanchalak-media-bucket1')
PROJECT_ID = os.getenv('PROJECT_ID', 'sanchalak-423912')

# ========== MEDIA UPLOAD UTILS =============

def get_gcs_client():
    try:
        return storage.Client(project=PROJECT_ID)
    except Exception as e:
        raise RuntimeError(f"Failed to create GCS client: {e}")

def get_valid_filename(filename):
    filename = re.sub(r'[^\w\s-]', '', filename).strip()
    return re.sub(r'[-\s]+', '-', filename)

def sanitize_timestamp(raw_timestamp):
    return get_valid_filename(unquote(raw_timestamp)).replace(":", "_")

def process_media_file_upload(file_content, file_format, complain_id, media_type):
    try:
        created_at = datetime.now().strftime("%Y-%m-%d_%H:%M:%S.%f")
        unique_id = str(uuid.uuid4())[:5]
        full_file_name = f"rail_sathi_complain_{complain_id}_{sanitize_timestamp(created_at)}_{unique_id}.{file_format}"
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)

        if media_type == "image":
            img = Image.open(io.BytesIO(file_content))
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            buffer.seek(0)
            blob = bucket.blob(f"rail_sathi_complain_images/{full_file_name}")
            blob.upload_from_file(buffer, content_type='image/jpeg')
        elif media_type == "video":
            temp_dir = "/tmp/rail_sathi_temp"
            os.makedirs(temp_dir, exist_ok=True)
            raw_path = os.path.join(temp_dir, full_file_name)
            compressed_path = os.path.join(temp_dir, f"compressed_{full_file_name}")
            with open(raw_path, 'wb') as f:
                f.write(file_content)
            try:
                clip = VideoFileClip(raw_path)
                clip.write_videofile(compressed_path, codec='libx264', bitrate='5000k')
                clip.close()
            except Exception as e:
                print(f"Error compressing video: {e}")
            blob = bucket.blob(f"rail_sathi_complain_videos/{full_file_name}")
            with open(compressed_path, 'rb') as f:
                blob.upload_from_file(f, content_type='video/mp4')
            os.remove(raw_path)
            os.remove(compressed_path)
        else:
            return None
        return blob.public_url if blob else None
    except Exception as e:
        logger.error(f"Error processing media: {e}")
        return None

def upload_file_thread(file_obj, complain_id, user):
    try:
        file_content = file_obj.read()
        ext = os.path.splitext(file_obj.filename)[1].lstrip('.').lower()
        content_type = getattr(file_obj, 'content_type', 'application/octet-stream')
        media_type = "image" if content_type.startswith("image") else "video" if content_type.startswith("video") else None
        if not media_type:
            return
        url = process_media_file_upload(file_content, ext, complain_id, media_type)
        if url:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rail_sathi_railsathicomplainmedia
                (complain_id, media_type, media_url, created_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (complain_id, media_type, url, user, datetime.now(), datetime.now()))
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Thread upload failed: {e}")

async def upload_file_async(file_obj: UploadFile, complain_id: int, user: str):
    try:
        content_type = file_obj.content_type
        save_dir = "uploads/images" if content_type.startswith("image") else "uploads/videos"
        os.makedirs(save_dir, exist_ok=True)
        file_content = await file_obj.read()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{complain_id}_{timestamp}_{file_obj.filename}"
        with open(os.path.join(save_dir, filename), "wb") as f:
            f.write(file_content)
        return True
    except Exception as e:
        logger.error(f"Upload async error: {e}")
        return False

# ========== COMPLAINT FUNCTIONS =============

def validate_and_process_train_data(data):
    conn = get_db_connection()
    try:
        if data.get("train_id"):
            train = execute_query_one(conn, "SELECT * FROM trains_traindetails WHERE id = %s", (data['train_id'],))
            if train:
                data['train_number'] = train['train_no']
                data['train_name'] = train['train_name']
        elif data.get("train_number"):
            train = execute_query_one(conn, "SELECT * FROM trains_traindetails WHERE train_no = %s", (data['train_number'],))
            if train:
                data['train_id'] = train['id']
                data['train_name'] = train['train_name']
        return data
    finally:
        conn.close()

def create_complaint(data):
    data = validate_and_process_train_data(data)
    conn = get_db_connection()
    try:
        now = datetime.now()
        complain_date = data.get("complain_date") or str(date.today())
        if isinstance(complain_date, str):
            try:
                complain_date = datetime.strptime(complain_date, "%Y-%m-%d").date()
            except:
                complain_date = date.today()

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO rail_sathi_railsathicomplain
            (pnr_number, is_pnr_validated, name, mobile_number, complain_type,
             complain_description, complain_date, complain_status, train_id, train_number,
             train_name, coach, berth_no, created_by, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING complain_id
        """, (
            data.get('pnr_number'), data.get('is_pnr_validated', 'not-attempted'),
            data.get('name'), data.get('mobile_number'), data.get('complain_type'),
            data.get('complain_description'), complain_date, data.get('complain_status', 'pending'),
            data.get('train_id'), data.get('train_number'), data.get('train_name'),
            data.get('coach'), data.get('berth_no'), data.get('created_by'), now, now
        ))
        complain_id = cursor.fetchone()[0]
        conn.commit()
        complaint = get_complaint_by_id(complain_id)
        threading.Thread(target=send_passenger_complain_email, args=({
            'complain_id': complain_id,
            'description': data.get('complain_description', ''),
            'user_phone_number': data.get('mobile_number', ''),
            'passenger_name': data.get('name', '')
        },)).start()
        return complaint
    finally:
        conn.close()

def get_complaint_by_id(complain_id):
    conn = get_db_connection()
    try:
        complaint = execute_query_one(conn, """
            SELECT c.*, t.train_no, t.train_name, t.depot as train_depot
            FROM rail_sathi_railsathicomplain c
            LEFT JOIN trains_traindetails t ON c.train_id = t.id
            WHERE c.complain_id = %s
        """, (complain_id,))
        if not complaint:
            return None
        media_files = execute_query(conn, """
            SELECT id, media_type, media_url, created_at, updated_at, created_by, updated_by
            FROM rail_sathi_railsathicomplainmedia WHERE complain_id = %s
        """, (complain_id,))
        complaint['rail_sathi_complain_media_files'] = media_files or []
        return complaint
    finally:
        conn.close()

def get_complaints_by_date(complain_date: date, mobile_number: str):
    conn = get_db_connection()
    try:
        complaints = execute_query(conn, """
            SELECT c.*, t.train_no, t.train_name, t.depot as train_depot
            FROM rail_sathi_railsathicomplain c
            LEFT JOIN trains_traindetails t ON c.train_id = t.id
            WHERE c.complain_date = %s AND c.mobile_number = %s
        """, (complain_date, mobile_number))
        for complaint in complaints:
            media_files = execute_query(conn, """
                SELECT id, media_type, media_url, created_at, updated_at, created_by, updated_by
                FROM rail_sathi_railsathicomplainmedia WHERE complain_id = %s
            """, (complaint['complain_id'],))
            complaint['rail_sathi_complain_media_files'] = media_files or []
        return complaints
    finally:
        conn.close()

def update_complaint(complain_id, data):
    conn = get_db_connection()
    try:
        data = validate_and_process_train_data(data)
        fields, values = [], []
        for key in ['pnr_number', 'is_pnr_validated', 'name', 'mobile_number', 'complain_type',
                    'complain_description', 'complain_date', 'complain_status', 'train_id',
                    'train_number', 'train_name', 'coach', 'berth_no', 'updated_by']:
            if key in data:
                fields.append(f"{key} = %s")
                values.append(data[key])
        fields.append("updated_at = %s")
        values.append(datetime.now())
        values.append(complain_id)
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE rail_sathi_railsathicomplain SET {', '.join(fields)} WHERE complain_id = %s
        """, tuple(values))
        conn.commit()
        return get_complaint_by_id(complain_id)
    finally:
        conn.close()

def delete_complaint(complain_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rail_sathi_railsathicomplainmedia WHERE complain_id = %s", (complain_id,))
        cursor.execute("DELETE FROM rail_sathi_railsathicomplain WHERE complain_id = %s", (complain_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()

def delete_complaint_media(complain_id: int, media_ids: List[int]):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM rail_sathi_railsathicomplainmedia
            WHERE complain_id = %s AND id = ANY(%s)
        """, (complain_id, media_ids))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()

def fetch_war_room_users_safe():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT u.*
                FROM information_schema.tables t
                JOIN user_onboarding_user u ON TRUE
                JOIN user_onboarding_roles ut ON u.user_type_id = ut.id
                WHERE t.table_name = 'user_onboarding_user' AND ut.name = 'war room user'
            """)
            return cursor.fetchall()
        except Exception as e:
            logger.warning(f"Skipping war room fetch due to error: {e}")
            return []
    finally:
        conn.close()
def validate_complaint_access(complain_id: int, name: str, mobile_number: str):
    """
    Dummy access check — you can customize it later.
    Allows delete if the complaint exists and name/mobile matches.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, mobile_number FROM rail_sathi_railsathicomplain
            WHERE complain_id = %s
        """, (complain_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return False, "Complaint not found"
        
        if result[0] == name and result[1] == mobile_number:
            return True, "Access granted"
        else:
            return False, "Name or mobile number does not match"

    except Exception as e:
        logger.error(f"Error validating access: {e}")
        return False, "Validation failed"
