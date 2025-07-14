# 🚆 Rail Sathi Complaint API

This is a backend API developed using **FastAPI** and **PostgreSQL** for registering and managing railway passenger complaints.  
Users can also upload complaint-related media files (like images/videos), which are saved **locally**.

![MIT License](https://img.shields.io/badge/license-MIT-green)

---

## 📦 Features

- Add new complaint with details
- Upload media (images/videos stored locally)
- Get complaint by ID
- Get complaints by date and mobile number
- Update complaint details
- Delete complaint (with name and mobile match)
- View train details
- Test all APIs using Swagger UI

---

## 🧰 Tech Stack

- **Backend**: Python (FastAPI)
- **Database**: PostgreSQL
- **Testing**: Swagger UI
- **Media Upload**: Local File System (`uploads/images`, `uploads/videos`)

---

## 🚀 How to Run

1. Open terminal and go to the project folder:

   ```bash
   cd RailSathiBE
   python -m uvicorn main:app --reload --port 5002

2. Open Swagger UI in browser:
   http://localhost:5002/rs_microservice/docs


## 🧪 API Endpoints

| Method   | Endpoint                                                       | Description                     |
| -------- | -------------------------------------------------------------- | ------------------------------- |
| `POST`   | `/rs_microservice/complaint/add`                               | Add new complaint               |
| `POST`   | `/rs_microservice/complaint/media/upload`                      | Upload media                    |
| `GET`    | `/rs_microservice/complaint/get/{complain_id}`                 | Get complaint by ID             |
| `GET`    | `/rs_microservice/complaint/get/date/{date}?mobile_number=...` | Get complaints by date & mobile |
| `PATCH`  | `/rs_microservice/complaint/update/{complain_id}`              | Update complaint                |
| `DELETE` | `/rs_microservice/complaint/delete/{complain_id}`              | Delete complaint                |
| `GET`    | `/health`                                                      | API health check                |

## 🧾 Sample Test Data

| Field                 | Value         |
| --------------------- | ------------- |
| Name                  | harika        |
| Mobile Number         | 9898989898    |
| PNR Number            | 1234567890    |
| Complaint Type        | food          |
| Complaint Description | food was cold |
| Complaint Date        | 2025-07-13    |
| Train Number          | 12345         |
| Train Name            | Express       |
| Coach                 | S1            |
| Berth                 | 13            |

## 📸 Screenshots
✅ Complaint Created Successfully
✅ Media Uploaded Successfully
✅ Get Complaints by Date
✅ Complaint Deleted Successfully

📁 (All screenshots are included in the ZIP folder under Screenshots/)

## 🙋 About Me
I am Harika Daka, a recent graduate passionate about backend development and API design.
This project was completed as part of a technical assignment to demonstrate my skills in Python (FastAPI), PostgreSQL, and API development.

## 💡 What I Learned
- Handling multipart/form-data in FastAPI

- Uploading and saving media files locally

- Writing and executing PostgreSQL queries

- Testing endpoints via Swagger UI

