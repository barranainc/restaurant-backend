from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request, File, UploadFile
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
from fastapi.responses import StreamingResponse, FileResponse
import csv
from io import StringIO
import smtplib
from email.message import EmailMessage
from sqlalchemy import extract
from datetime import date, datetime, timedelta
from datetime import time
import os
import shutil
from pathlib import Path

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

# API Keys
ADMIN_API_KEY = "admin-secret-key-2024"
PUBLIC_BOOKING_KEY = "public-booking-key"

def verify_admin_api_key(x_api_key: str = Header(...)):
    """Updated to be compatible with role-based auth and public bookings"""
    if x_api_key not in [ADMIN_API_KEY, PUBLIC_BOOKING_KEY]:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

def verify_admin_only_api_key(x_api_key: str = Header(...)):
    """Verify admin-only API key (excludes public booking key)"""
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False, unique=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.now)
    notes = Column(Text, nullable=True)
    reservations = relationship("Reservation", back_populates="customer")

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
    adults = Column(Integer, nullable=False)
    children = Column(Integer, nullable=False)
    child_seat_required = Column(Boolean, default=False)
    status = Column(String, default="Queued")  # Queued, Seated, Completed, Cancelled, No-show
    queue_number = Column(Integer)
    created_at = Column(DateTime, default=dt.datetime.now)
    seated_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    reservation_type = Column(String, default="phone")  # walk-in, phone, online
    # New fields for scheduled reservations
    reservation_date = Column(Date, nullable=True)  # Date of reservation
    reservation_time = Column(String, nullable=True)  # Time of reservation (HH:MM format)
    is_scheduled = Column(Boolean, default=False)  # True for future reservations, False for walk-ins
    customer = relationship("Customer", back_populates="reservations")
    table = relationship("Table", back_populates="reservations")

class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True, index=True)
    table_number = Column(String, nullable=False, unique=True)
    location = Column(String, nullable=False)  # 'Indoor' or 'Outdoor'
    size = Column(Integer, nullable=False)     # Number of seats
    is_occupied = Column(Boolean, default=False)
    reservations = relationship("Reservation", back_populates="table")

class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="staff")  # admin, sub_admin, staff
    email = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=dt.datetime.now)
    created_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)

class OperatingHours(Base):
    __tablename__ = "operating_hours"
    id = Column(Integer, primary_key=True, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    open_time = Column(String, nullable=False)  # HH:MM format
    close_time = Column(String, nullable=False)  # HH:MM format
    is_open = Column(Boolean, default=True)
    created_at = Column(DateTime, default=dt.datetime.now)

class Holiday(Base):
    __tablename__ = "holidays"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    is_closed = Column(Boolean, default=True)
    special_hours = Column(String, nullable=True)  # JSON string for special hours
    created_at = Column(DateTime, default=dt.datetime.now)

class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    adults = Column(Integer, nullable=False)
    children = Column(Integer, nullable=False)
    child_seat_required = Column(Boolean, default=False)
    location = Column(String, nullable=False)  # 'Indoor' or 'Outdoor'
    notes = Column(Text, nullable=True)
    status = Column(String, default="Waiting")  # Waiting, Called, Seated, Cancelled
    created_at = Column(DateTime, default=dt.datetime.now)
    called_at = Column(DateTime, nullable=True)
    seated_at = Column(DateTime, nullable=True)
    estimated_wait_time = Column(Integer, nullable=True)  # Estimated wait time in minutes
    customer = relationship("Customer")

class Note(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.now)

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    type = Column(String, nullable=False)  # Daily, Monthly
    data = Column(Text, nullable=False)    # JSON or CSV as text
    generated_at = Column(DateTime, default=dt.datetime.now)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection setup
DATABASE_URL = "sqlite:///./restaurant.db"  # Change to your production DB URL as needed
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=20,  # Increased pool size
    max_overflow=40
)
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

class CapacityUpdate(BaseModel):
    new_capacity: int

class OperatingHoursCreate(BaseModel):
    day_of_week: int  # 0=Monday, 6=Sunday
    open_time: str  # HH:MM format
    close_time: str  # HH:MM format
    is_open: bool = True

class OperatingHoursUpdate(BaseModel):
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    is_open: Optional[bool] = None

class OperatingHoursOut(BaseModel):
    id: int
    day_of_week: int
    open_time: str
    close_time: str
    is_open: bool
    day_name: str

    class Config:
        from_attributes = True

class HolidayCreate(BaseModel):
    name: str
    date: date
    is_closed: bool = True
    special_hours: Optional[str] = None

class HolidayUpdate(BaseModel):
    name: Optional[str] = None
    is_closed: Optional[bool] = None
    special_hours: Optional[str] = None

class HolidayOut(BaseModel):
    id: int
    name: str
    date: date
    is_closed: bool
    special_hours: Optional[str] = None
    created_at: dt.datetime

    class Config:
        from_attributes = True

class WaitlistCreate(BaseModel):
    name: str
    phone_number: str
    email: str = None
    adults: int
    children: int
    child_seat_required: bool = False
    location: str  # 'Indoor' or 'Outdoor'
    notes: str = None
    estimated_wait_time: Optional[int] = None

class WaitlistOut(BaseModel):
    id: int
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    adults: int
    children: int
    child_seat_required: bool
    location: str
    status: str
    created_at: dt.datetime
    called_at: Optional[dt.datetime] = None
    seated_at: Optional[dt.datetime] = None
    estimated_wait_time: Optional[int] = None
    notes: Optional[str] = None
    wait_time_minutes: Optional[int] = None  # Calculated wait time

    class Config:
        from_attributes = True

class WaitlistStatusUpdate(BaseModel):
    status: str  # Waiting, Called, Seated, Cancelled
    estimated_wait_time: Optional[int] = None
    notes: Optional[str] = None

class ReservationCreate(BaseModel):
    name: str
    phone_number: str
    email: str = None
    adults: int
    children: int
    child_seat_required: bool = False
    location: str  # 'Indoor' or 'Outdoor'
    notes: str = None
    reservation_type: str = "phone"  # walk-in, phone, online
    # New fields for scheduled reservations
    reservation_date: Optional[date] = None
    reservation_time: Optional[str] = None  # HH:MM format
    is_scheduled: bool = False

class ReservationOut(BaseModel):
    id: int
    customer_name: Optional[str] = None
    phone_number: Optional[str] = None
    adults: int
    children: int
    child_seat_required: bool
    status: str
    queue_number: int
    created_at: dt.datetime
    notes: Optional[str] = None
    table_id: Optional[int] = None
    reservation_type: Optional[str] = None
    # New fields for scheduled reservations
    reservation_date: Optional[date] = None
    reservation_time: Optional[str] = None
    is_scheduled: bool = False

    class Config:
        from_attributes = True

# Twilio placeholders (fill in when ready)
TWILIO_ACCOUNT_SID = "your_twilio_account_sid"
TWILIO_AUTH_TOKEN = "your_twilio_auth_token"
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"  # Twilio Sandbox number

# To use Twilio Sandbox for WhatsApp:
# 1. Sign up at https://www.twilio.com/console/sms/whatsapp/sandbox
# 2. Join the sandbox with your phone (send the code to the number above)
# 3. Set your credentials and use your WhatsApp number as the recipient (e.g., 'whatsapp:+12345556789')
USE_TWILIO_WHATSAPP = False  # Set to True to use Twilio, False to mock

def send_whatsapp_notification(phone_number: str, queue_number: int):
    if not USE_TWILIO_WHATSAPP:
        print(f"[MOCK] WhatsApp notification to {phone_number}: Your queue number is {queue_number}")
        return
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"Your reservation is confirmed! Your queue number is {queue_number}.",
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{phone_number}"
        )
        print(f"[TWILIO] WhatsApp message sent: SID={message.sid}")
    except Exception as e:
        print(f"[TWILIO ERROR] Failed to send WhatsApp message: {e}")

# Email notification functions
def send_email_notification(to_email: str, subject: str, body: str):
    """Send email notification (simulated for now)"""
    try:
        # In a real implementation, you would use a service like SendGrid, Mailgun, or SMTP
        print(f"EMAIL SENT TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print(f"BODY: {body}")
        print("-" * 50)
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def send_reservation_confirmation_email(customer_name: str, customer_email: str, reservation_data: dict):
    """Send reservation confirmation email"""
    if not customer_email:
        return False
    
    subject = f"Reservation Confirmed - {reservation_data.get('restaurant_name', 'Barrana Restaurant')}"
    
    body = f"""
Dear {customer_name},

Your reservation has been confirmed!

Reservation Details:
- Date: {reservation_data.get('reservation_date', 'Today')}
- Time: {reservation_data.get('reservation_time', 'Walk-in')}
- Party Size: {reservation_data.get('adults', 0)} adults, {reservation_data.get('children', 0)} children
- Location: {reservation_data.get('location', 'Indoor')}
- Queue Number: {reservation_data.get('queue_number', 'N/A')}

Special Notes: {reservation_data.get('notes', 'None')}

We look forward to serving you!

Best regards,
{reservation_data.get('restaurant_name', 'Barrana Restaurant')}
    """
    
    return send_email_notification(customer_email, subject, body)

def send_waitlist_notification_email(customer_name: str, customer_email: str, waitlist_data: dict):
    """Send waitlist notification email"""
    if not customer_email:
        return False
    
    subject = f"Added to Waitlist - {waitlist_data.get('restaurant_name', 'Barrana Restaurant')}"
    
    body = f"""
Dear {customer_name},

You have been added to our waitlist.

Waitlist Details:
- Party Size: {waitlist_data.get('adults', 0)} adults, {waitlist_data.get('children', 0)} children
- Location: {waitlist_data.get('location', 'Indoor')}
- Estimated Wait Time: {waitlist_data.get('estimated_wait_time', 'Unknown')} minutes

We will notify you when a table becomes available.

Thank you for your patience!

Best regards,
{waitlist_data.get('restaurant_name', 'Barrana Restaurant')}
    """
    
    return send_email_notification(customer_email, subject, body)

def send_table_ready_notification_email(customer_name: str, customer_email: str, table_data: dict):
    """Send table ready notification email"""
    if not customer_email:
        return False
    
    subject = f"Table Ready - {table_data.get('restaurant_name', 'Barrana Restaurant')}"
    
    body = f"""
Dear {customer_name},

Great news! Your table is ready.

Table Details:
- Table Number: {table_data.get('table_number', 'N/A')}
- Location: {table_data.get('location', 'Indoor')}
- Please proceed to the host station.

We look forward to serving you!

Best regards,
{table_data.get('restaurant_name', 'Barrana Restaurant')}
    """
    
    return send_email_notification(customer_email, subject, body)

# SMS notification functions (simulated)
def send_sms_notification(phone_number: str, message: str):
    """Send SMS notification (simulated for now)"""
    try:
        # In a real implementation, you would use a service like Twilio, AWS SNS, etc.
        print(f"SMS SENT TO: {phone_number}")
        print(f"MESSAGE: {message}")
        print("-" * 50)
        return True
    except Exception as e:
        print(f"Failed to send SMS: {e}")
        return False

def send_reservation_confirmation_sms(phone_number: str, reservation_data: dict):
    """Send reservation confirmation SMS"""
    message = f"""
Barrana Restaurant - Reservation Confirmed
Date: {reservation_data.get('reservation_date', 'Today')}
Time: {reservation_data.get('reservation_time', 'Walk-in')}
Queue: #{reservation_data.get('queue_number', 'N/A')}
Party: {reservation_data.get('adults', 0)}A {reservation_data.get('children', 0)}C
Location: {reservation_data.get('location', 'Indoor')}
    """
    
    return send_sms_notification(phone_number, message.strip())

@app.put("/tables/{table_id}/capacity")
def update_table_capacity(table_id: int, update: CapacityUpdate):
    db: Session = SessionLocal()
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        db.close()
        raise HTTPException(status_code=404, detail="Table not found")
    table.size = update.new_capacity
    db.commit()
    db.refresh(table)
    db.close()
    return {"message": f"Table {table.table_number} capacity updated to {update.new_capacity}"}

@app.get("/tables")
def list_tables():
    db: Session = SessionLocal()
    tables = db.query(Table).all()
    db.close()
    return tables

@app.post("/reservations")
def create_reservation(reservation: ReservationCreate):
    db = SessionLocal()
    # Check if customer exists
    customer = db.query(Customer).filter(Customer.phone_number == reservation.phone_number).first()
    if not customer:
        customer = Customer(
            name=reservation.name,
            phone_number=reservation.phone_number,
            email=reservation.email,
            notes=reservation.notes
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
    # Assign queue number (max + 1 for today)
    today = dt.datetime.now().date()
    last_queue = db.query(Reservation).filter(
        Reservation.created_at >= dt.datetime.combine(today, dt.time.min),
        Reservation.created_at <= dt.datetime.combine(today, dt.time.max)
    ).order_by(Reservation.queue_number.desc()).first()
    queue_number = 1 if not last_queue else last_queue.queue_number + 1
    # Find available table (stub: just None for now)
    table = db.query(Table).filter(
        Table.location == reservation.location,
        Table.is_occupied == False,
        Table.size >= (reservation.adults + reservation.children)
    ).first()
    table_id = table.id if table else None
    # Create reservation
    new_reservation = Reservation(
        customer_id=customer.id,
        table_id=table_id,  # Assign if available
        adults=reservation.adults,
        children=reservation.children,
        child_seat_required=reservation.child_seat_required,
        status="Queued",
        queue_number=queue_number,
        notes=reservation.notes,
        created_at=dt.datetime.now(),
        reservation_type=reservation.reservation_type
    )
    db.add(new_reservation)
    db.commit()
    db.refresh(new_reservation)
    # WhatsApp notification stub
    send_whatsapp_notification(customer.phone_number, queue_number)
    db.close()
    return {"message": "Reservation created", "queue_number": queue_number, "table_id": table_id}

# Waitlist Management Endpoints
@app.post("/admin/waitlist", response_model=WaitlistOut)
def admin_add_to_waitlist(waitlist_entry: WaitlistCreate, dep=Depends(verify_admin_api_key)):
    """Add a customer to the waitlist"""
    db = SessionLocal()
    try:
        # Check if customer exists, create if not
        customer = db.query(Customer).filter(Customer.phone_number == waitlist_entry.phone_number).first()
        if not customer:
            customer = Customer(
                name=waitlist_entry.name,
                phone_number=waitlist_entry.phone_number,
                email=waitlist_entry.email
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)
        
        # Create waitlist entry
        waitlist = WaitlistEntry(
            customer_id=customer.id,
            adults=waitlist_entry.adults,
            children=waitlist_entry.children,
            child_seat_required=waitlist_entry.child_seat_required,
            location=waitlist_entry.location,
            notes=waitlist_entry.notes,
            estimated_wait_time=waitlist_entry.estimated_wait_time
        )
        db.add(waitlist)
        db.commit()
        db.refresh(waitlist)
        
        # Return with customer info
        result = WaitlistOut(
            id=waitlist.id,
            customer_name=customer.name,
            phone_number=customer.phone_number,
            adults=waitlist.adults,
            children=waitlist.children,
            child_seat_required=waitlist.child_seat_required,
            location=waitlist.location,
            status=waitlist.status,
            created_at=waitlist.created_at,
            called_at=waitlist.called_at,
            seated_at=waitlist.seated_at,
            estimated_wait_time=waitlist.estimated_wait_time,
            notes=waitlist.notes
        )
        return result
    finally:
        db.close()

@app.get("/admin/waitlist", response_model=List[WaitlistOut])
def admin_list_waitlist(dep=Depends(verify_admin_api_key)):
    """List all waitlist entries"""
    db = SessionLocal()
    try:
        waitlist_entries = db.query(WaitlistEntry).filter(
            WaitlistEntry.status.in_(["Waiting", "Called"])
        ).order_by(WaitlistEntry.created_at.asc()).all()
        
        result = []
        for entry in waitlist_entries:
            customer = db.query(Customer).filter(Customer.id == entry.customer_id).first()
            wait_time = None
            if entry.created_at:
                wait_time = int((dt.datetime.now() - entry.created_at).total_seconds() / 60)
            
            result.append(WaitlistOut(
                id=entry.id,
                customer_name=customer.name if customer else None,
                phone_number=customer.phone_number if customer else None,
                adults=entry.adults,
                children=entry.children,
                child_seat_required=entry.child_seat_required,
                location=entry.location,
                status=entry.status,
                created_at=entry.created_at,
                called_at=entry.called_at,
                seated_at=entry.seated_at,
                estimated_wait_time=entry.estimated_wait_time,
                notes=entry.notes,
                wait_time_minutes=wait_time
            ))
        return result
    finally:
        db.close()

@app.put("/admin/waitlist/{waitlist_id}")
def admin_update_waitlist_status(waitlist_id: int, update: WaitlistStatusUpdate, dep=Depends(verify_admin_api_key)):
    """Update waitlist entry status"""
    db = SessionLocal()
    try:
        waitlist = db.query(WaitlistEntry).filter(WaitlistEntry.id == waitlist_id).first()
        if not waitlist:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        
        waitlist.status = update.status
        if update.estimated_wait_time is not None:
            waitlist.estimated_wait_time = update.estimated_wait_time
        if update.notes is not None:
            waitlist.notes = update.notes
        
        # Update timestamps based on status
        if update.status == "Called":
            waitlist.called_at = dt.datetime.now()
        elif update.status == "Seated":
            waitlist.seated_at = dt.datetime.now()
        
        db.commit()
        return {"message": "Waitlist status updated successfully"}
    finally:
        db.close()

@app.delete("/admin/waitlist/{waitlist_id}")
def admin_remove_from_waitlist(waitlist_id: int, dep=Depends(verify_admin_api_key)):
    """Remove customer from waitlist"""
    db = SessionLocal()
    try:
        waitlist = db.query(WaitlistEntry).filter(WaitlistEntry.id == waitlist_id).first()
        if not waitlist:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        
        db.delete(waitlist)
        db.commit()
        return {"message": "Customer removed from waitlist"}
    finally:
        db.close()

# Enhanced reservation creation with conflict detection
@app.post("/admin/reservations", response_model=ReservationOut)
def admin_create_reservation(reservation: ReservationCreate, dep=Depends(verify_admin_api_key)):
    """Create a new reservation with enhanced features"""
    db = SessionLocal()
    try:
        # Check if customer exists, create if not
        customer = db.query(Customer).filter(Customer.phone_number == reservation.phone_number).first()
        if not customer:
            customer = Customer(
                name=reservation.name,
                phone_number=reservation.phone_number,
                email=reservation.email
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)
        
        # For scheduled reservations, check for conflicts
        if reservation.is_scheduled and reservation.reservation_date and reservation.reservation_time:
            # Check for table conflicts at the same time
            conflicting_reservations = db.query(Reservation).filter(
                Reservation.reservation_date == reservation.reservation_date,
                Reservation.reservation_time == reservation.reservation_time,
                Reservation.status.in_(["Queued", "Seated"]),
                Reservation.table_id.isnot(None)
            ).all()
            
            if conflicting_reservations:
                # Check if we have available tables
                available_tables = db.query(Table).filter(
                    Table.location == reservation.location,
                    Table.size >= (reservation.adults + reservation.children),
                    Table.is_occupied == False
                ).all()
                
                if len(available_tables) <= len(conflicting_reservations):
                    # No tables available, suggest waitlist
                    raise HTTPException(
                        status_code=409, 
                        detail=f"No tables available for {reservation.reservation_time} on {reservation.reservation_date}. Consider adding to waitlist."
                    )
        
        # Find available table
        table = db.query(Table).filter(
            Table.location == reservation.location,
            Table.size >= (reservation.adults + reservation.children),
            Table.is_occupied == False
        ).first()
        
        # If no table available and it's a walk-in, add to waitlist
        if not table and not reservation.is_scheduled:
            # Create waitlist entry instead
            waitlist_entry = WaitlistEntry(
                customer_id=customer.id,
                adults=reservation.adults,
                children=reservation.children,
                child_seat_required=reservation.child_seat_required,
                location=reservation.location,
                notes=reservation.notes
            )
            db.add(waitlist_entry)
            db.commit()
            db.refresh(waitlist_entry)
            
            # Return waitlist info
            return {
                "id": waitlist_entry.id,
                "customer_name": customer.name,
                "phone_number": customer.phone_number,
                "adults": waitlist_entry.adults,
                "children": waitlist_entry.children,
                "child_seat_required": waitlist_entry.child_seat_required,
                "status": "Waitlist",
                "queue_number": None,
                "created_at": waitlist_entry.created_at,
                "notes": waitlist_entry.notes,
                "table_id": None,
                "reservation_type": reservation.reservation_type,
                "reservation_date": reservation.reservation_date,
                "reservation_time": reservation.reservation_time,
                "is_scheduled": reservation.is_scheduled
            }
        
        # Get next queue number
        max_queue = db.query(func.max(Reservation.queue_number)).scalar() or 0
        queue_number = max_queue + 1
        
        # Create reservation
        new_reservation = Reservation(
            customer_id=customer.id,
            table_id=table.id if table else None,
            adults=reservation.adults,
            children=reservation.children,
            child_seat_required=reservation.child_seat_required,
            status="Queued" if not table else "Seated",
            queue_number=queue_number,
            notes=reservation.notes,
            reservation_type=reservation.reservation_type,
            reservation_date=reservation.reservation_date,
            reservation_time=reservation.reservation_time,
            is_scheduled=reservation.is_scheduled
        )
        
        db.add(new_reservation)
        
        # Mark table as occupied if assigned
        if table:
            table.is_occupied = True
        
        db.commit()
        db.refresh(new_reservation)
        
        # Return reservation with customer info
        result = ReservationOut(
            id=new_reservation.id,
            customer_name=customer.name,
            phone_number=customer.phone_number,
            adults=new_reservation.adults,
            children=new_reservation.children,
            child_seat_required=new_reservation.child_seat_required,
            status=new_reservation.status,
            queue_number=new_reservation.queue_number,
            created_at=new_reservation.created_at,
            notes=new_reservation.notes,
            table_id=new_reservation.table_id,
            reservation_type=new_reservation.reservation_type,
            reservation_date=new_reservation.reservation_date,
            reservation_time=new_reservation.reservation_time,
            is_scheduled=new_reservation.is_scheduled
        )
        
        # Send notifications
        reservation_data = {
            "restaurant_name": "Barrana Restaurant",
            "reservation_date": reservation.reservation_date,
            "reservation_time": reservation.reservation_time,
            "adults": reservation.adults,
            "children": reservation.children,
            "location": reservation.location,
            "queue_number": queue_number,
            "notes": reservation.notes
        }
        
        # Send email notification
        if customer.email:
            send_reservation_confirmation_email(customer.name, customer.email, reservation_data)
        
        # Send SMS notification
        send_reservation_confirmation_sms(customer.phone_number, reservation_data)
        
        return result
    finally:
        db.close()

@app.post("/admin/login", response_model=LoginResponse)
async def admin_login(login_data: LoginRequest):
    db = SessionLocal()
    try:
        # Check database users first
        user = db.query(AdminUser).filter(
            AdminUser.username == login_data.username,
            AdminUser.is_active == True
        ).first()
        
        if user and verify_password(login_data.password, user.password_hash):
            return LoginResponse(
                success=True,
                message="Login successful",
                api_key=ADMIN_API_KEY,
                user_role=user.role,
                user_id=user.id,
                username=user.username
            )
        
        # Fallback to hardcoded admin for backward compatibility
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
    finally:
        db.close()

@app.get("/admin/reservations", response_model=List[ReservationOut])
def admin_list_reservations(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_queue_minutes: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    table_size: Optional[int] = Query(None),
    location: Optional[str] = Query(None),
    customer_type: Optional[str] = Query(None),
    show_no_shows: Optional[bool] = Query(False),
    dep=Depends(verify_admin_api_key)
):
    db = SessionLocal()
    query = db.query(Reservation).join(Customer).outerjoin(Table)

    if search:
        query = query.filter(
            (Customer.name.ilike(f"%{search}%")) |
            (Customer.phone_number.ilike(f"%{search}%"))
        )
    if status:
        query = query.filter(Reservation.status == status)
    if min_queue_minutes and status == "queued":
        queue_time_threshold = dt.datetime.now() - timedelta(minutes=min_queue_minutes)
        query = query.filter(Reservation.created_at <= queue_time_threshold)
    if start_date:
        start_datetime = dt.datetime.combine(start_date, dt.time.min)
        query = query.filter(Reservation.created_at >= start_datetime)
    if end_date:
        end_datetime = dt.datetime.combine(end_date, dt.time.max)
        query = query.filter(Reservation.created_at <= end_datetime)
    if table_size:
        query = query.filter(Table.size == table_size)
    if location:
        query = query.filter(Table.location == location)
    if customer_type:
        # This requires a subquery or a more complex join to count reservations per customer
        # For now, we'll skip this server-side and it can be handled client-side if needed
        pass
    if show_no_shows:
        query = query.filter(Reservation.status.in_(['cancelled', 'no-show']))

    reservations = query.order_by(Reservation.created_at.desc()).all()

    result = []
    for r in reservations:
        customer_name = r.customer.name if r.customer else None
        phone_number = r.customer.phone_number if r.customer else None
        result.append(ReservationOut(
            id=r.id,
            customer_name=customer_name,
            phone_number=phone_number,
            adults=r.adults,
            children=r.children,
            child_seat_required=r.child_seat_required,
            status=r.status,
            queue_number=r.queue_number,
            created_at=r.created_at,
            notes=r.notes,
            table_id=r.table_id,
            reservation_type=r.reservation_type
        ))
    db.close()
    return result

class ReservationStatusUpdate(BaseModel):
    status: str = None
    queue_number: int = None
    notes: str = None

@app.put("/admin/reservations/{reservation_id}")
def admin_update_reservation(reservation_id: int, update: ReservationStatusUpdate, dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        db.close()
        raise HTTPException(status_code=404, detail="Reservation not found")
    if update.status:
        reservation.status = update.status
    if update.queue_number is not None:
        reservation.queue_number = update.queue_number
    if update.notes is not None:
        reservation.notes = update.notes
    db.commit()
    db.refresh(reservation)
    db.close()
    return {"message": "Reservation updated"}

@app.get("/admin/queue", response_model=List[ReservationOut])
def admin_list_queue(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    queue = db.query(Reservation).filter(Reservation.status == "Queued").order_by(Reservation.queue_number).all()
    result = []
    for r in queue:
        customer_name = r.customer.name if r.customer else None
        phone_number = r.customer.phone_number if r.customer else None
        result.append(ReservationOut(
            id=r.id,
            customer_name=customer_name,
            phone_number=phone_number,
            adults=r.adults,
            children=r.children,
            child_seat_required=r.child_seat_required,
            status=r.status,
            queue_number=r.queue_number,
            created_at=r.created_at,
            notes=r.notes,
            table_id=r.table_id,
            reservation_type=r.reservation_type
        ))
    db.close()
    return result

class TableStatusUpdate(BaseModel):
    is_occupied: bool

@app.put("/admin/tables/{table_id}/status")
def admin_update_table_status(table_id: int, update: TableStatusUpdate, dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        db.close()
        raise HTTPException(status_code=404, detail="Table not found")
    table.is_occupied = update.is_occupied
    db.commit()
    db.refresh(table)
    db.close()
    return {"message": f"Table {table.table_number} status updated to {'Occupied' if update.is_occupied else 'Unoccupied'}"}

class TableCreate(BaseModel):
    table_number: str
    location: str  # 'Indoor' or 'Outdoor'
    size: int

class TableUpdate(BaseModel):
    table_number: str = None
    location: str = None
    size: int = None

@app.post("/admin/tables")
def admin_create_table(table: TableCreate, dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    new_table = Table(
        table_number=table.table_number,
        location=table.location,
        size=table.size,
        is_occupied=False
    )
    db.add(new_table)
    db.commit()
    db.refresh(new_table)
    db.close()
    return {"message": "Table created", "table_id": new_table.id}

@app.get("/admin/tables")
def admin_list_tables(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    tables = db.query(Table).all()
    result = []
    for t in tables:
        result.append({
            "id": t.id,
            "table_number": t.table_number,
            "location": t.location,
            "size": t.size,
            "is_occupied": t.is_occupied
        })
    db.close()
    return result

@app.put("/admin/tables/{table_id}")
def admin_update_table(table_id: int, update: TableUpdate, dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        db.close()
        raise HTTPException(status_code=404, detail="Table not found")
    if update.table_number is not None:
        table.table_number = update.table_number
    if update.location is not None:
        table.location = update.location
    if update.size is not None:
        table.size = update.size
    db.commit()
    db.refresh(table)
    db.close()
    return {"message": "Table updated"}

@app.delete("/admin/tables/{table_id}")
def admin_delete_table(table_id: int, dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        db.close()
        raise HTTPException(status_code=404, detail="Table not found")
    db.delete(table)
    db.commit()
    db.close()
    return {"message": "Table deleted"}

@app.get("/admin/reports/daily")
def admin_daily_report(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    results = db.query(
        func.date(Reservation.created_at).label("date"),
        func.count(Reservation.id).label("reservation_count")
    ).group_by(func.date(Reservation.created_at)).order_by(func.date(Reservation.created_at)).all()
    db.close()
    return [{"date": str(row.date), "reservation_count": row.reservation_count} for row in results]

@app.get("/admin/reports/monthly")
def admin_monthly_report(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    results = db.query(
        func.strftime('%Y-%m', Reservation.created_at).label("month"),
        func.count(Reservation.id).label("reservation_count")
    ).group_by(func.strftime('%Y-%m', Reservation.created_at)).order_by(func.strftime('%Y-%m', Reservation.created_at)).all()
    db.close()
    return [{"month": row.month, "reservation_count": row.reservation_count} for row in results]

@app.get("/admin/reports/daily/csv")
def admin_daily_report_csv(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    results = db.query(
        func.date(Reservation.created_at).label("date"),
        func.count(Reservation.id).label("reservation_count")
    ).group_by(func.date(Reservation.created_at)).order_by(func.date(Reservation.created_at)).all()
    db.close()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "reservation_count"])
    for row in results:
        writer.writerow([row.date, row.reservation_count])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=daily_report.csv"})

@app.get("/admin/reports/monthly/csv")
def admin_monthly_report_csv(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    results = db.query(
        func.strftime('%Y-%m', Reservation.created_at).label("month"),
        func.count(Reservation.id).label("reservation_count")
    ).group_by(func.strftime('%Y-%m', Reservation.created_at)).order_by(func.strftime('%Y-%m', Reservation.created_at)).all()
    db.close()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["month", "reservation_count"])
    for row in results:
        writer.writerow([row.month, row.reservation_count])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=monthly_report.csv"})

GMAIL_USER = "singhgarcia5@gmail.com"  # <-- Your Gmail address
GMAIL_APP_PASSWORD = "www.&.com"  # <-- Your Gmail app password
ADMIN_EMAIL = "ikram.rana1507@gmail.com"

def send_email_with_attachment(subject, body, to_email, attachment_content, attachment_filename):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg.set_content(body)
    msg.add_attachment(attachment_content, maintype="text", subtype="csv", filename=attachment_filename)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

@app.post("/admin/reports/send-email")
def send_daily_report_email(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    results = db.query(
        func.date(Reservation.created_at).label("date"),
        func.count(Reservation.id).label("reservation_count")
    ).group_by(func.date(Reservation.created_at)).order_by(func.date(Reservation.created_at)).all()
    db.close()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "reservation_count"])
    for row in results:
        writer.writerow([row.date, row.reservation_count])
    output.seek(0)
    csv_content = output.read().encode()
    send_email_with_attachment(
        subject="Daily Reservation Report",
        body="Please find attached the daily reservation report.",
        to_email=ADMIN_EMAIL,
        attachment_content=csv_content,
        attachment_filename="daily_report.csv"
    )
    return {"message": f"Daily report sent to {ADMIN_EMAIL}"}

class CustomerOut(BaseModel):
    id: int
    name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    created_at: dt.datetime
    notes: Optional[str] = None
    class Config:
        from_attributes = True

@app.get("/admin/customers", response_model=List[CustomerOut])
def admin_list_customers(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    customers = db.query(Customer).order_by(Customer.created_at.desc()).all()
    result = [CustomerOut.from_orm(c) for c in customers]
    db.close()
    return result

@app.get("/admin/customers/{customer_id}/reservations", response_model=List[ReservationOut])
def admin_customer_reservations(customer_id: int, dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    reservations = db.query(Reservation).filter(Reservation.customer_id == customer_id).order_by(Reservation.created_at.desc()).all()
    result = []
    for r in reservations:
        customer_name = r.customer.name if r.customer else None
        phone_number = r.customer.phone_number if r.customer else None
        result.append(ReservationOut(
            id=r.id,
            customer_name=customer_name,
            phone_number=phone_number,
            adults=r.adults,
            children=r.children,
            child_seat_required=r.child_seat_required,
            status=r.status,
            queue_number=r.queue_number,
            created_at=r.created_at,
            notes=r.notes,
            table_id=r.table_id,
            reservation_type=r.reservation_type
        ))
    db.close()
    return result

class CustomerFilter(BaseModel):
    min_reservations: int = 1
    last_visit_after: Optional[dt.date] = None

@app.post("/admin/customers/filter", response_model=List[CustomerOut])
def admin_filter_customers(filter: CustomerFilter, dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    query = db.query(Customer)
    if filter.last_visit_after:
        subq = db.query(Reservation.customer_id, func.max(Reservation.created_at).label("last_visit")).group_by(Reservation.customer_id).subquery()
        query = query.join(subq, Customer.id == subq.c.customer_id).filter(subq.c.last_visit >= filter.last_visit_after)
    customers = query.all()
    # Filter by min_reservations in Python for flexibility
    result = []
    for c in customers:
        res_count = db.query(Reservation).filter(Reservation.customer_id == c.id).count()
        if res_count >= filter.min_reservations:
            result.append(CustomerOut.from_orm(c))
    db.close()
    return result

class MarketingMessage(BaseModel):
    customer_ids: List[int]
    message: str

# User Management Models
class UserCreate(BaseModel):
    username: str
    password: str
    role: str  # admin, sub_admin, staff
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    created_by_admin_id: Optional[int] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None

class UserOut(BaseModel):
    id: int
    username: str
    role: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: bool
    created_at: dt.datetime
    created_by_admin_id: Optional[int] = None
    class Config:
        from_attributes = True

# Moved to earlier in file to fix import order

@app.post("/admin/marketing/send-whatsapp")
def admin_send_marketing_whatsapp(msg: MarketingMessage, dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    customers = db.query(Customer).filter(Customer.id.in_(msg.customer_ids)).all()
    for c in customers:
        # Mocked WhatsApp send
        print(f"[MOCK MARKETING] WhatsApp to {c.phone_number}: {msg.message}")
    db.close()
    return {"message": f"WhatsApp marketing message sent to {len(customers)} customers (mocked)"}

@app.get("/admin/analytics/peak-hours")
def analytics_peak_hours(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    results = db.query(Reservation).all()
    arrivals = [[0 for _ in range(24)] for _ in range(7)]  # [day][hour]
    waits = [[[] for _ in range(24)] for _ in range(7)]
    for r in results:
        if r.created_at:
            dt = r.created_at
            day = dt.weekday()  # 0=Mon
            hour = dt.hour
            arrivals[day][hour] += 1
            if r.seated_at:
                wait = (r.seated_at - r.created_at).total_seconds() / 60
                waits[day][hour].append(wait)
    avg_waits = [[(sum(waits[d][h])/len(waits[d][h]) if waits[d][h] else 0) for h in range(24)] for d in range(7)]
    db.close()
    return {"arrivals": arrivals, "avg_waits": avg_waits}

@app.get("/admin/analytics/table-utilization")
def analytics_table_utilization(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    tables = db.query(Table).all()
    utilization = []
    for t in tables:
        total = db.query(Reservation).filter(Reservation.table_id == t.id).count()
        occupied = db.query(Reservation).filter(Reservation.table_id == t.id, Reservation.status.in_(["seated", "completed"])).count()
        utilization.append({"table_number": t.table_number, "total": total, "occupied": occupied})
    db.close()
    return utilization

@app.get("/admin/analytics/no-show-rate")
def analytics_no_show_rate(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    total = db.query(Reservation).count()
    cancelled = db.query(Reservation).filter(Reservation.status == "cancelled").count()
    db.close()
    rate = (cancelled / total * 100) if total else 0
    return {"total": total, "cancelled": cancelled, "rate": rate}

@app.get("/admin/analytics/customer-frequency")
def analytics_customer_frequency(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    customers = db.query(Customer).all()
    new_count = 0
    repeat_count = 0
    for c in customers:
        res_count = db.query(Reservation).filter(Reservation.customer_id == c.id).count()
        if res_count > 1:
            repeat_count += 1
        elif res_count == 1:
            new_count += 1
    db.close()
    return {"new": new_count, "repeat": repeat_count}

@app.get("/admin/analytics/group-size-over-time")
def analytics_group_size_over_time(dep=Depends(verify_admin_api_key)):
    db = SessionLocal()
    from datetime import datetime, timedelta
    today = dt.datetime.now().date()
    data = []
    for i in range(30):
        day = today - timedelta(days=i)
        res = db.query(Reservation).filter(
            extract('year', Reservation.created_at) == day.year,
            extract('month', Reservation.created_at) == day.month,
            extract('day', Reservation.created_at) == day.day
        ).all()
        if res:
            avg_size = sum(r.adults + (r.children or 0) for r in res) / len(res)
        else:
            avg_size = 0
        data.append({"date": str(day), "avg_group_size": avg_size})
    db.close()
    return list(reversed(data))

@app.get("/admin/status")
def get_current_status(dep=Depends(verify_admin_api_key)):
    """Get current operational status for the status header"""
    db = SessionLocal()

    # Get occupied tables count
    occupied_count = db.query(Table).filter(Table.is_occupied == True).count()

    # Get waiting customers count (queued reservations)
    waiting_count = db.query(Reservation).filter(Reservation.status == "Queued").count()

    # Get total tables count
    total_tables = db.query(Table).count()

    db.close()

    return {
        "occupied": occupied_count,
        "waiting": waiting_count,
        "total_tables": total_tables,
        "timestamp": dt.datetime.now().isoformat()
    }

@app.get("/admin/dashboard/analytics")
def get_dashboard_analytics(dep=Depends(verify_admin_api_key)):
    """Get comprehensive dashboard analytics"""
    db = SessionLocal()

    # Calculate average wait time
    reservations_with_wait = db.query(Reservation).filter(
        Reservation.status.in_(["Seated", "Completed"]),
        Reservation.seated_at.isnot(None)
    ).all()

    total_wait_time = 0
    for res in reservations_with_wait:
        if res.seated_at and res.created_at:
            wait_time = (res.seated_at - res.created_at).total_seconds() / 60
            total_wait_time += wait_time

    avg_wait_time = round(total_wait_time / len(reservations_with_wait), 1) if reservations_with_wait else 0

    # Calculate next hour reservations
    now = dt.datetime.now()
    next_hour = now + timedelta(hours=1)
    next_hour_reservations = db.query(Reservation).filter(
        Reservation.created_at >= now,
        Reservation.created_at <= next_hour
    ).count()

    # Calculate turnover pace (simplified)
    completed_today = db.query(Reservation).filter(
        Reservation.status == "Completed",
        Reservation.created_at >= dt.datetime.combine(now.date(), dt.time.min)
    ).count()

    turnover_pace = round(completed_today / 10, 1) if completed_today > 0 else 0  # Assuming 10 hour day

    # Get abandonment rate
    total_reservations = db.query(Reservation).count()
    cancelled_reservations = db.query(Reservation).filter(Reservation.status == "Cancelled").count()
    abandonment_rate = round((cancelled_reservations / total_reservations * 100), 1) if total_reservations > 0 else 0

    # Get customer frequency
    total_customers = db.query(Customer).count()
    repeat_customers = db.query(Customer).join(Reservation).group_by(Customer.id).having(
        func.count(Reservation.id) > 1
    ).count()
    new_customers = total_customers - repeat_customers

    db.close()

    return {
        "kpis": {
            "avg_wait_time": avg_wait_time,
            "next_hour_reservations": next_hour_reservations,
            "turnover_pace": turnover_pace,
            "abandonment_rate": abandonment_rate
        },
        "customer_frequency": {
            "new": round((new_customers / total_customers * 100), 1) if total_customers > 0 else 0,
            "repeat": round((repeat_customers / total_customers * 100), 1) if total_customers > 0 else 0
        },
        "no_show_rate": {
            "completed": 100 - abandonment_rate,
            "cancelled": abandonment_rate
        }
    }

# User Management Endpoints
@app.post("/admin/users", response_model=UserOut)
async def create_user(user_data: UserCreate, x_api_key: str = Depends(verify_admin_api_key)):
    db = SessionLocal()
    try:
        # Check if username already exists
        existing_user = db.query(AdminUser).filter(AdminUser.username == user_data.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Create new user
        hashed_password = hash_password(user_data.password)
        db_user = AdminUser(
            username=user_data.username,
            password_hash=hashed_password,
            role=user_data.role,
            email=user_data.email,
            full_name=user_data.full_name,
            is_active=user_data.is_active,
            created_by_admin_id=user_data.created_by_admin_id
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return UserOut(
            id=db_user.id,
            username=db_user.username,
            role=db_user.role,
            email=db_user.email,
            full_name=db_user.full_name,
            is_active=db_user.is_active,
            created_at=db_user.created_at,
            created_by_admin_id=db_user.created_by_admin_id
        )
    finally:
        db.close()

@app.get("/admin/users", response_model=List[UserOut])
async def list_users(x_api_key: str = Depends(verify_admin_api_key)):
    db = SessionLocal()
    try:
        users = db.query(AdminUser).all()
        return [UserOut(
            id=user.id,
            username=user.username,
            role=user.role,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
            created_by_admin_id=user.created_by_admin_id
        ) for user in users]
    finally:
        db.close()

@app.put("/admin/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, user_data: UserUpdate, x_api_key: str = Depends(verify_admin_api_key)):
    db = SessionLocal()
    try:
        user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update fields if provided
        if user_data.username is not None:
            # Check if new username already exists (but not for the same user)
            existing = db.query(AdminUser).filter(
                AdminUser.username == user_data.username,
                AdminUser.id != user_id
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Username already exists")
            user.username = user_data.username
        
        if user_data.password is not None:
            user.password_hash = hash_password(user_data.password)
        if user_data.role is not None:
            user.role = user_data.role
        if user_data.email is not None:
            user.email = user_data.email
        if user_data.full_name is not None:
            user.full_name = user_data.full_name
        if user_data.is_active is not None:
            user.is_active = user_data.is_active
        
        db.commit()
        db.refresh(user)
        
        return UserOut(
            id=user.id,
            username=user.username,
            role=user.role,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
            created_by_admin_id=user.created_by_admin_id
        )
    finally:
        db.close()

@app.delete("/admin/users/{user_id}")
async def delete_user(user_id: int, x_api_key: str = Depends(verify_admin_api_key)):
    db = SessionLocal()
    try:
        user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        db.delete(user)
        db.commit()
        
        return {"message": "User deleted successfully"}
    finally:
        db.close()

# Restaurant Logo Management Endpoints
LOGO_UPLOAD_DIR = Path("uploads/logos")
LOGO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@app.post("/admin/upload-logo")
async def upload_restaurant_logo(
    logo: UploadFile = File(...),
    x_api_key: str = Depends(verify_admin_api_key)
):
    """Upload restaurant logo - Admin only"""
    try:
        # Validate file type
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif"]
        if logo.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail="Invalid file type. Only JPEG, PNG, and GIF images are allowed."
            )
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB in bytes
        logo.file.seek(0, 2)  # Seek to end
        file_size = logo.file.tell()
        logo.file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 5MB."
            )
        
        # Generate filename with timestamp
        file_extension = logo.filename.split('.')[-1].lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"restaurant_logo_{timestamp}.{file_extension}"
        file_path = LOGO_UPLOAD_DIR / filename
        
        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
        
        # Remove old logo files (keep only the latest)
        for old_file in LOGO_UPLOAD_DIR.glob("restaurant_logo_*"):
            if old_file.name != filename:
                try:
                    old_file.unlink()
                except:
                    pass  # Ignore errors when deleting old files
        
        return {
            "message": "Logo uploaded successfully",
            "filename": filename,
            "url": f"/admin/logo/{filename}"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading logo: {str(e)}")

@app.get("/admin/logo/{filename}")
async def get_restaurant_logo(filename: str):
    """Serve restaurant logo file"""
    file_path = LOGO_UPLOAD_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    
    return FileResponse(
        path=file_path,
        media_type="image/*",
        headers={"Cache-Control": "public, max-age=3600"}  # Cache for 1 hour
    )

@app.get("/admin/current-logo")
async def get_current_logo():
    """Get the current restaurant logo URL"""
    try:
        # Find the most recent logo file
        logo_files = list(LOGO_UPLOAD_DIR.glob("restaurant_logo_*"))
        if not logo_files:
            return {"logo_url": None, "has_logo": False}
        
        # Get the most recent file
        latest_logo = max(logo_files, key=lambda x: x.stat().st_mtime)
        
        return {
            "logo_url": f"/admin/logo/{latest_logo.name}",
            "filename": latest_logo.name,
            "has_logo": True
        }
    except Exception as e:
        return {"logo_url": None, "has_logo": False, "error": str(e)}

# Operating Hours Management
@app.get("/admin/operating-hours", response_model=List[OperatingHoursOut])
def admin_get_operating_hours(dep=Depends(verify_admin_api_key)):
    """Get all operating hours"""
    db = SessionLocal()
    try:
        hours = db.query(OperatingHours).order_by(OperatingHours.day_of_week).all()
        result = []
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for hour in hours:
            result.append(OperatingHoursOut(
                id=hour.id,
                day_of_week=hour.day_of_week,
                open_time=hour.open_time,
                close_time=hour.close_time,
                is_open=hour.is_open,
                day_name=day_names[hour.day_of_week]
            ))
        return result
    finally:
        db.close()

@app.post("/admin/operating-hours", response_model=OperatingHoursOut)
def admin_create_operating_hours(hours: OperatingHoursCreate, dep=Depends(verify_admin_only_api_key)):
    """Create or update operating hours for a day"""
    db = SessionLocal()
    try:
        # Check if hours already exist for this day
        existing = db.query(OperatingHours).filter(OperatingHours.day_of_week == hours.day_of_week).first()
        
        if existing:
            # Update existing
            existing.open_time = hours.open_time
            existing.close_time = hours.close_time
            existing.is_open = hours.is_open
            db.commit()
            db.refresh(existing)
            hour = existing
        else:
            # Create new
            hour = OperatingHours(
                day_of_week=hours.day_of_week,
                open_time=hours.open_time,
                close_time=hours.close_time,
                is_open=hours.is_open
            )
            db.add(hour)
            db.commit()
            db.refresh(hour)
        
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return OperatingHoursOut(
            id=hour.id,
            day_of_week=hour.day_of_week,
            open_time=hour.open_time,
            close_time=hour.close_time,
            is_open=hour.is_open,
            day_name=day_names[hour.day_of_week]
        )
    finally:
        db.close()

@app.put("/admin/operating-hours/{day_of_week}")
def admin_update_operating_hours(day_of_week: int, update: OperatingHoursUpdate, dep=Depends(verify_admin_only_api_key)):
    """Update operating hours for a specific day"""
    db = SessionLocal()
    try:
        hours = db.query(OperatingHours).filter(OperatingHours.day_of_week == day_of_week).first()
        if not hours:
            raise HTTPException(status_code=404, detail="Operating hours not found for this day")
        
        if update.open_time is not None:
            hours.open_time = update.open_time
        if update.close_time is not None:
            hours.close_time = update.close_time
        if update.is_open is not None:
            hours.is_open = update.is_open
        
        db.commit()
        return {"message": "Operating hours updated successfully"}
    finally:
        db.close()

# Holiday Management
@app.get("/admin/holidays", response_model=List[HolidayOut])
def admin_get_holidays(dep=Depends(verify_admin_api_key)):
    """Get all holidays"""
    db = SessionLocal()
    try:
        holidays = db.query(Holiday).order_by(Holiday.date).all()
        return [HolidayOut.from_orm(holiday) for holiday in holidays]
    finally:
        db.close()

@app.post("/admin/holidays", response_model=HolidayOut)
def admin_create_holiday(holiday: HolidayCreate, dep=Depends(verify_admin_only_api_key)):
    """Create a new holiday"""
    db = SessionLocal()
    try:
        new_holiday = Holiday(
            name=holiday.name,
            date=holiday.date,
            is_closed=holiday.is_closed,
            special_hours=holiday.special_hours
        )
        db.add(new_holiday)
        db.commit()
        db.refresh(new_holiday)
        return HolidayOut.from_orm(new_holiday)
    finally:
        db.close()

@app.put("/admin/holidays/{holiday_id}")
def admin_update_holiday(holiday_id: int, update: HolidayUpdate, dep=Depends(verify_admin_only_api_key)):
    """Update a holiday"""
    db = SessionLocal()
    try:
        holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
        if not holiday:
            raise HTTPException(status_code=404, detail="Holiday not found")
        
        if update.name is not None:
            holiday.name = update.name
        if update.is_closed is not None:
            holiday.is_closed = update.is_closed
        if update.special_hours is not None:
            holiday.special_hours = update.special_hours
        
        db.commit()
        return {"message": "Holiday updated successfully"}
    finally:
        db.close()

@app.delete("/admin/holidays/{holiday_id}")
def admin_delete_holiday(holiday_id: int, dep=Depends(verify_admin_only_api_key)):
    """Delete a holiday"""
    db = SessionLocal()
    try:
        holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
        if not holiday:
            raise HTTPException(status_code=404, detail="Holiday not found")
        
        db.delete(holiday)
        db.commit()
        return {"message": "Holiday deleted successfully"}
    finally:
        db.close()

# Check if restaurant is open
@app.get("/admin/is-open")
def admin_check_if_open(dep=Depends(verify_admin_api_key)):
    """Check if restaurant is currently open"""
    db = SessionLocal()
    try:
        now = dt.datetime.now()
        day_of_week = now.weekday()
        current_time = now.strftime("%H:%M")
        
        # Check if today is a holiday
        today = now.date()
        holiday = db.query(Holiday).filter(Holiday.date == today).first()
        
        if holiday:
            if holiday.is_closed:
                return {
                    "is_open": False,
                    "reason": f"Closed for {holiday.name}",
                    "next_open": "Check operating hours"
                }
            elif holiday.special_hours:
                # Parse special hours (simplified)
                return {
                    "is_open": True,
                    "reason": f"Special hours for {holiday.name}",
                    "hours": holiday.special_hours
                }
        
        # Check regular operating hours
        hours = db.query(OperatingHours).filter(OperatingHours.day_of_week == day_of_week).first()
        
        if not hours or not hours.is_open:
            return {
                "is_open": False,
                "reason": "Closed today",
                "next_open": "Check operating hours"
            }
        
        # Check if current time is within operating hours
        is_open = hours.open_time <= current_time <= hours.close_time
        
        return {
            "is_open": is_open,
            "reason": "Regular hours" if is_open else "Outside operating hours",
            "hours": f"{hours.open_time} - {hours.close_time}"
        }
    finally:
        db.close()

# Enhanced Analytics Endpoints for Intelligent Reports
@app.get("/admin/analytics/reservations")
def analytics_reservations(range: str = Query("7d"), dep=Depends(verify_admin_api_key)):
    """Get comprehensive reservation analytics"""
    db = SessionLocal()
    try:
        # Calculate date range
        end_date = dt.datetime.now()
        if range == "1d":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range == "7d":
            start_date = end_date - dt.timedelta(days=7)
        elif range == "30d":
            start_date = end_date - dt.timedelta(days=30)
        elif range == "90d":
            start_date = end_date - dt.timedelta(days=90)
        elif range == "1y":
            start_date = end_date - dt.timedelta(days=365)
        else:
            start_date = end_date - dt.timedelta(days=7)
        
        # Get reservations in date range
        reservations = db.query(Reservation).filter(
            Reservation.created_at >= start_date,
            Reservation.created_at <= end_date
        ).all()
        
        # Calculate metrics
        total_reservations = len(reservations)
        total_guests = sum(r.adults + r.children for r in reservations)
        no_shows = len([r for r in reservations if r.status == "No-show"])
        no_show_rate = no_shows / total_reservations if total_reservations > 0 else 0
        
        # Daily data
        daily_data = []
        current_date = start_date.date()
        while current_date <= end_date.date():
            day_reservations = [r for r in reservations if r.created_at.date() == current_date]
            daily_data.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "count": len(day_reservations)
            })
            current_date += dt.timedelta(days=1)
        
        return {
            "total_reservations": total_reservations,
            "total_guests": total_guests,
            "no_show_rate": no_show_rate,
            "daily_data": daily_data
        }
    finally:
        db.close()

@app.get("/admin/analytics/customer-frequency")
def analytics_customer_frequency(range: str = Query("7d"), dep=Depends(verify_admin_api_key)):
    """Get customer analytics"""
    db = SessionLocal()
    try:
        # Calculate date range
        end_date = dt.datetime.now()
        if range == "1d":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range == "7d":
            start_date = end_date - dt.timedelta(days=7)
        elif range == "30d":
            start_date = end_date - dt.timedelta(days=30)
        elif range == "90d":
            start_date = end_date - dt.timedelta(days=90)
        elif range == "1y":
            start_date = end_date - dt.timedelta(days=365)
        else:
            start_date = end_date - dt.timedelta(days=7)
        
        # Get all customers
        all_customers = db.query(Customer).all()
        total_customers = len(all_customers)
        
        # Count repeat customers (more than 1 reservation)
        repeat_customers = 0
        new_customers = 0
        
        for customer in all_customers:
            reservation_count = db.query(Reservation).filter(
                Reservation.customer_id == customer.id
            ).count()
            
            if reservation_count > 1:
                repeat_customers += 1
            elif reservation_count == 1:
                new_customers += 1
        
        # Customer types distribution
        customer_types = [
            {"type": "New Customers", "count": new_customers},
            {"type": "Repeat Customers", "count": repeat_customers},
            {"type": "VIP Customers", "count": repeat_customers // 3}  # Mock VIP calculation
        ]
        
        return {
            "total_customers": total_customers,
            "new_customers": new_customers,
            "repeat_customers": repeat_customers,
            "customer_types": customer_types
        }
    finally:
        db.close()

@app.get("/admin/analytics/table-utilization")
def analytics_table_utilization(range: str = Query("7d"), dep=Depends(verify_admin_api_key)):
    """Get table utilization analytics"""
    db = SessionLocal()
    try:
        # Calculate date range
        end_date = dt.datetime.now()
        if range == "1d":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range == "7d":
            start_date = end_date - dt.timedelta(days=7)
        elif range == "30d":
            start_date = end_date - dt.timedelta(days=30)
        elif range == "90d":
            start_date = end_date - dt.timedelta(days=90)
        elif range == "1y":
            start_date = end_date - dt.timedelta(days=365)
        else:
            start_date = end_date - dt.timedelta(days=7)
        
        # Get all tables
        tables = db.query(Table).all()
        total_tables = len(tables)
        
        table_data = []
        total_utilization = 0
        
        for table in tables:
            # Count total reservations for this table
            total_reservations = db.query(Reservation).filter(
                Reservation.table_id == table.id,
                Reservation.created_at >= start_date,
                Reservation.created_at <= end_date
            ).count()
            
            # Count occupied time (seated or completed reservations)
            occupied_reservations = db.query(Reservation).filter(
                Reservation.table_id == table.id,
                Reservation.status.in_(["Seated", "Completed"]),
                Reservation.created_at >= start_date,
                Reservation.created_at <= end_date
            ).count()
            
            # Calculate utilization rate
            utilization = occupied_reservations / max(total_reservations, 1)
            total_utilization += utilization
            
            table_data.append({
                "table_number": table.table_number,
                "utilization": utilization,
                "total_reservations": total_reservations,
                "occupied_reservations": occupied_reservations
            })
        
        average_utilization = total_utilization / total_tables if total_tables > 0 else 0
        peak_utilization = max([t["utilization"] for t in table_data]) if table_data else 0
        lowest_utilization = min([t["utilization"] for t in table_data]) if table_data else 0
        
        return {
            "total_tables": total_tables,
            "average_utilization": average_utilization,
            "peak_utilization": peak_utilization,
            "lowest_utilization": lowest_utilization,
            "table_data": table_data
        }
    finally:
        db.close()

@app.get("/admin/analytics/revenue")
def analytics_revenue(range: str = Query("7d"), dep=Depends(verify_admin_api_key)):
    """Get revenue analytics (simulated)"""
    db = SessionLocal()
    try:
        # Calculate date range
        end_date = dt.datetime.now()
        if range == "1d":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range == "7d":
            start_date = end_date - dt.timedelta(days=7)
        elif range == "30d":
            start_date = end_date - dt.timedelta(days=30)
        elif range == "90d":
            start_date = end_date - dt.timedelta(days=90)
        elif range == "1y":
            start_date = end_date - dt.timedelta(days=365)
        else:
            start_date = end_date - dt.timedelta(days=7)
        
        # Get reservations in date range
        reservations = db.query(Reservation).filter(
            Reservation.created_at >= start_date,
            Reservation.created_at <= end_date,
            Reservation.status.in_(["Completed", "Seated"])
        ).all()
        
        # Simulate revenue based on party size and average check
        daily_revenue = []
        total_revenue = 0
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            day_reservations = [r for r in reservations if r.created_at.date() == current_date]
            day_revenue = sum((r.adults + r.children) * 25 for r in day_reservations)  # $25 per person average
            total_revenue += day_revenue
            
            daily_revenue.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "amount": day_revenue
            })
            current_date += dt.timedelta(days=1)
        
        average_check = total_revenue / len(reservations) if reservations else 0
        revenue_growth = 0.15  # Mock 15% growth
        
        # Find best day
        best_day_data = max(daily_revenue, key=lambda x: x["amount"]) if daily_revenue else {"date": "N/A"}
        best_day = best_day_data["date"]
        
        return {
            "total_revenue": total_revenue,
            "average_check": average_check,
            "revenue_growth": revenue_growth,
            "best_day": best_day,
            "daily_revenue": daily_revenue
        }
    finally:
        db.close()

@app.get("/admin/analytics/peak-hours")
def analytics_peak_hours(range: str = Query("7d"), dep=Depends(verify_admin_api_key)):
    """Get peak hours analytics"""
    db = SessionLocal()
    try:
        # Calculate date range
        end_date = dt.datetime.now()
        if range == "1d":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range == "7d":
            start_date = end_date - dt.timedelta(days=7)
        elif range == "30d":
            start_date = end_date - dt.timedelta(days=30)
        elif range == "90d":
            start_date = end_date - dt.timedelta(days=90)
        elif range == "1y":
            start_date = end_date - dt.timedelta(days=365)
        else:
            start_date = end_date - dt.timedelta(days=7)
        
        # Get reservations in date range
        reservations = db.query(Reservation).filter(
            Reservation.created_at >= start_date,
            Reservation.created_at <= end_date
        ).all()
        
        # Count reservations by hour
        hour_counts = [0] * 24
        for reservation in reservations:
            if reservation.created_at:
                hour = reservation.created_at.hour
                hour_counts[hour] += 1
        
        # Create peak hours data
        peak_hours = []
        for hour in range(24):
            if hour_counts[hour] > 0:
                peak_hours.append({
                    "hour": f"{hour:02d}",
                    "count": hour_counts[hour]
                })
        
        # Sort by count descending
        peak_hours.sort(key=lambda x: x["count"], reverse=True)
        
        # Calculate average wait time (simulated)
        average_wait_time = 15  # Mock 15 minutes
        
        # Find peak hour and day
        peak_hour = peak_hours[0]["hour"] if peak_hours else "N/A"
        peak_day = "Friday"  # Mock data
        
        return {
            "peak_hours": peak_hours,
            "average_wait_time": average_wait_time,
            "peak_hour": peak_hour,
            "peak_day": peak_day,
            "busiest_period": "6:00 PM - 8:00 PM"  # Mock data
        }
    finally:
        db.close()

@app.get("/admin/analytics/waitlist")
def analytics_waitlist(range: str = Query("7d"), dep=Depends(verify_admin_api_key)):
    """Get waitlist analytics"""
    db = SessionLocal()
    try:
        # Calculate date range
        end_date = dt.datetime.now()
        if range == "1d":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range == "7d":
            start_date = end_date - dt.timedelta(days=7)
        elif range == "30d":
            start_date = end_date - dt.timedelta(days=30)
        elif range == "90d":
            start_date = end_date - dt.timedelta(days=90)
        elif range == "1y":
            start_date = end_date - dt.timedelta(days=365)
        else:
            start_date = end_date - dt.timedelta(days=7)
        
        # Get waitlist entries in date range
        waitlist_entries = db.query(WaitlistEntry).filter(
            WaitlistEntry.created_at >= start_date,
            WaitlistEntry.created_at <= end_date
        ).all()
        
        total_entries = len(waitlist_entries)
        
        # Calculate conversion rate (seated entries)
        seated_entries = len([w for w in waitlist_entries if w.status == "Seated"])
        conversion_rate = seated_entries / total_entries if total_entries > 0 else 0
        
        # Calculate average wait time
        total_wait_time = 0
        wait_time_count = 0
        for entry in waitlist_entries:
            if entry.seated_at and entry.created_at:
                wait_time = (entry.seated_at - entry.created_at).total_seconds() / 60
                total_wait_time += wait_time
                wait_time_count += 1
        
        average_wait_time = total_wait_time / wait_time_count if wait_time_count > 0 else 0
        peak_wait_time = 45  # Mock data
        
        # Daily waitlist trend
        waitlist_trend = []
        current_date = start_date.date()
        while current_date <= end_date.date():
            day_entries = [w for w in waitlist_entries if w.created_at.date() == current_date]
            waitlist_trend.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "count": len(day_entries)
            })
            current_date += dt.timedelta(days=1)
        
        return {
            "total_entries": total_entries,
            "conversion_rate": conversion_rate,
            "average_wait_time": average_wait_time,
            "peak_wait_time": peak_wait_time,
            "waitlist_trend": waitlist_trend
        }
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    