# ✅ Full corrected main.py code with ALL endpoints (create, update, delete, media, train details, etc.)
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, date
import asyncio
import threading
import logging

from services import (
    create_complaint, get_complaint_by_id, get_complaints_by_date,
    update_complaint, delete_complaint, delete_complaint_media,
    upload_file_thread, upload_file_async,validate_complaint_access
)
from database import get_db_connection, execute_query_one
from psycopg2.extras import RealDictCursor

app = FastAPI(
    title="Rail Sathi Complaint API",
    description="API for handling rail complaints",
    version="1.0.0",
    openapi_url="/rs_microservice/openapi.json",
    docs_url="/rs_microservice/docs",
    redoc_url="/rs_microservice/redoc"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/rs_microservice")
async def root():
    return {"message": "Rail Sathi Microservice is running"}

class RailSathiComplainMediaResponse(BaseModel):
    id: int
    media_type: Optional[str]
    media_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]

class RailSathiComplainData(BaseModel):
    complain_id: int
    pnr_number: Optional[str]
    is_pnr_validated: Optional[str]
    name: Optional[str]
    mobile_number: Optional[str]
    complain_type: Optional[str]
    complain_description: Optional[str]
    complain_date: Optional[date]
    complain_status: str
    train_id: Optional[int]
    train_number: Optional[str]
    train_name: Optional[str]
    coach: Optional[str]
    berth_no: Optional[int]
    created_at: datetime
    created_by: Optional[str]
    updated_at: datetime
    updated_by: Optional[str]
    train_no: Optional[int]
    train_depot: Optional[str]
    rail_sathi_complain_media_files: List[RailSathiComplainMediaResponse]

class RailSathiComplainResponse(BaseModel):
    message: str
    data: RailSathiComplainData

@app.get("/rs_microservice/complaint/get/{complain_id}", response_model=RailSathiComplainResponse)
async def get_complaint(complain_id: int):
    complaint = get_complaint_by_id(complain_id)
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {"message": "Complaint retrieved successfully", "data": complaint}

@app.get("/rs_microservice/complaint/get/date/{date_str}", response_model=List[RailSathiComplainResponse])
async def get_complaints_by_date_endpoint(date_str: str, mobile_number: Optional[str] = None):
    try:
        complaint_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    if not mobile_number:
        raise HTTPException(status_code=400, detail="mobile_number parameter is required")
    complaints = get_complaints_by_date(complaint_date, mobile_number)
    return [{"message": "Complaint retrieved successfully", "data": c} for c in complaints]

@app.post("/rs_microservice/complaint/media/upload")
async def upload_complaint_media(
    complain_id: int = Form(...),
    created_by: str = Form(...),
    files: List[UploadFile] = File(...)
):
    uploaded_urls = []
    for file in files:
        result = await upload_file_async(file, complain_id, created_by)
        if result:
            uploaded_urls.append(file.filename)
        else:
            return {"message": f"Failed to upload: {file.filename}"}
    return {"message": "Media uploaded successfully", "files": uploaded_urls}

@app.post("/rs_microservice/complaint/add", response_model=RailSathiComplainResponse)
async def create_complaint_endpoint_threaded(
    pnr_number: Optional[str] = Form(None),
    is_pnr_validated: Optional[str] = Form("not-attempted"),
    name: Optional[str] = Form(None),
    mobile_number: Optional[str] = Form(None),
    complain_type: Optional[str] = Form(None),
    date_of_journey: Optional[str] = Form(None),
    complain_description: Optional[str] = Form(None),
    complain_date: Optional[str] = Form(None),
    complain_status: str = Form("pending"),
    train_id: Optional[int] = Form(None),
    train_number: Optional[str] = Form(None),
    train_name: Optional[str] = Form(None),
    coach: Optional[str] = Form(None),
    berth_no: Optional[int] = Form(None),
    rail_sathi_complain_media_files: List[UploadFile] = File(default=[])
):
    complaint_data = {
        "pnr_number": pnr_number,
        "is_pnr_validated": is_pnr_validated,
        "name": name,
        "mobile_number": mobile_number,
        "complain_type": complain_type,
        "complain_description": complain_description,
        "complain_date": complain_date,
        "date_of_journey": date_of_journey,
        "complain_status": complain_status,
        "train_id": train_id,
        "train_number": train_number,
        "train_name": train_name,
        "coach": coach,
        "berth_no": berth_no,
        "created_by": name
    }
    complaint = create_complaint(complaint_data)
    complain_id = complaint["complain_id"]
    threads = []
    for file_obj in rail_sathi_complain_media_files:
        if file_obj.filename:
            file_content = await file_obj.read()
            class MockFile:
                def __init__(self, content, filename, content_type):
                    self.content = content
                    self.filename = filename
                    self.content_type = content_type
                def read(self): return self.content
            mock_file = MockFile(file_content, file_obj.filename, file_obj.content_type)
            t = threading.Thread(target=upload_file_thread, args=(mock_file, complain_id, name or ''))
            t.start()
            threads.append(t)
    for t in threads: t.join()
    await asyncio.sleep(1)
    updated_complaint = get_complaint_by_id(complain_id)
    return {"message": "Complaint created successfully", "data": updated_complaint}

@app.patch("/rs_microservice/complaint/update/{complain_id}", response_model=RailSathiComplainResponse)
async def update_complaint_endpoint(
    complain_id: int,
    pnr_number: Optional[str] = Form(None),
    is_pnr_validated: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    mobile_number: Optional[str] = Form(None),
    complain_type: Optional[str] = Form(None),
    complain_description: Optional[str] = Form(None),
    complain_date: Optional[str] = Form(None),
    complain_status: Optional[str] = Form(None),
    train_id: Optional[int] = Form(None),
    train_number: Optional[str] = Form(None),
    train_name: Optional[str] = Form(None),
    coach: Optional[str] = Form(None),
    berth_no: Optional[int] = Form(None)
):
    update_data = {
        "pnr_number": pnr_number,
        "is_pnr_validated": is_pnr_validated,
        "name": name,
        "mobile_number": mobile_number,
        "complain_type": complain_type,
        "complain_description": complain_description,
        "complain_date": complain_date,
        "complain_status": complain_status,
        "train_id": train_id,
        "train_number": train_number,
        "train_name": train_name,
        "coach": coach,
        "berth_no": berth_no,
        "updated_by": name
    }
    updated = update_complaint(complain_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {"message": "Complaint updated successfully", "data": updated}

@app.delete("/rs_microservice/complaint/delete/{complain_id}")
async def delete_complaint_endpoint(
    complain_id: int,
    name: str = Form(...),
    mobile_number: str = Form(...)
):
    can_delete, reason = validate_complaint_access(complain_id, name, mobile_number)
    if not can_delete:
        raise HTTPException(status_code=403, detail=reason)
    count = delete_complaint(complain_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {"message": f"Complaint {complain_id} deleted successfully"}

@app.delete("/rs_microservice/media/delete/{complain_id}")
async def delete_complaint_media_endpoint(
    complain_id: int,
    media_ids: List[int] = Form(...)
):
    deleted = delete_complaint_media(complain_id, media_ids)
    return {"message": f"{deleted} media file(s) deleted successfully"}

@app.get("/rs_microservice/train_details/{train_no}")
async def get_train_details(train_no: str):
    conn = get_db_connection()
    try:
        query = "SELECT * FROM trains_traindetails WHERE train_no = %s"
        result = execute_query_one(conn, query, (train_no,))
        if not result:
            raise HTTPException(status_code=404, detail="Train not found")
        return result
    finally:
        conn.close()

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)
