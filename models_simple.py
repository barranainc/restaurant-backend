from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base
import datetime as dt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from sqlalchemy import func
from fastapi.responses import StreamingResponse
import csv
from io import StringIO
import smtplib
from email.message import EmailMessage
from sqlalchemy import extract
from datetime import date, datetime, timedelta
from datetime import time

# Role-based access control helpers
import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def has_permission(user_role: str, required_permission: str) -> bool:
    """Check if user role has required permission"""
    permissions = {
        "admin": ["dashboard", "reservations", "tables", "customers", "reports", "settings", "user_management"],
        "sub_admin": ["dashboard", "reservations", "tables", "customers"],
        "staff": ["reservations", "tables", "customers"]
    }
    return required_permission in permissions.get(user_role, [])

ADMIN_API_KEY = "supersecretadminkey"

def verify_admin_api_key(x_api_key: str = Header(...)):
    """Updated to be compatible with role-based auth"""
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# Create FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = "sqlite:///./restaurant.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

Base = declarative_base()

# Database Models
class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.now)
    reservations = relationship("Reservation", back_populates="customer")

class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True, index=True)
    table_number = Column(String, nullable=False, unique=True)
    location = Column(String, nullable=False)  # 'Indoor' or 'Outdoor'
    size = Column(Integer, nullable=False)     # Number of seats
    is_occupied = Column(Boolean, default=False)
    reservations = relationship("Reservation", back_populates="table")

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
    adults = Column(Integer, nullable=False)
    children = Column(Integer, default=0)
    child_seat_required = Column(Boolean, default=False)
    status = Column(String, default="queued")  # queued, seated, completed, cancelled, no-show
    queue_number = Column(Integer, nullable=False, unique=True)
    created_at = Column(DateTime, default=dt.datetime.now)
    notes = Column(Text, nullable=True)
    reservation_type = Column(String, default="phone")  # walk-in, phone, online

    customer = relationship("Customer", back_populates="reservations")
    table = relationship("Table", back_populates="reservations")

# Create database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
Base.metadata.create_all(bind=engine)

# Authentication Models (defined early to avoid import order issues)
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    api_key: Optional[str] = None
    user_role: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None

# Basic Login Endpoint (simplified)
@app.post("/admin/login", response_model=LoginResponse)
async def admin_login(login_data: LoginRequest):
    if login_data.username == "admin" and login_data.password == "password":
        return LoginResponse(
            success=True,
            message="Login successful",
            api_key=ADMIN_API_KEY,
            user_role="admin",
            user_id=0,
            username="admin"
        )
    
    raise HTTPException(status_code=401, detail="Invalid username or password")

# Test endpoint
@app.get("/")
async def root():
    return {"message": "Restaurant API is running"}

# Test admin endpoint
@app.get("/admin/test")
async def test_admin(x_api_key: str = Depends(verify_admin_api_key)):
    return {"message": "Admin access working"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 