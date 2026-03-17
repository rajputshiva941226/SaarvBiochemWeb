from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./saarv_biochem.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Enquiry(Base):
    __tablename__ = "enquiries"

    id = Column(Integer, primary_key=True, index=True)
    # Contact Info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False, index=True)
    phone = Column(String(30))
    company = Column(String(200))
    designation = Column(String(100))
    country = Column(String(100))
    # Enquiry Details
    enquiry_type = Column(String(50), nullable=False)  # service, api_catalog, custom
    service_interest = Column(String(200))
    subject = Column(String(300))
    message = Column(Text, nullable=False)
    # API-specific fields
    molecule_name = Column(String(200))
    cas_number = Column(String(50))
    required_quantity = Column(String(100))
    required_grade = Column(String(50))
    purity_requirement = Column(String(100))
    # Status & Meta
    status = Column(String(30), default="new")  # new, in_progress, quoted, closed
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    source_page = Column(String(100))
    ip_address = Column(String(50))
    consent_given = Column(Boolean, default=False)
    newsletter_opt_in = Column(Boolean, default=False)
    admin_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    name = Column(String(200))
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
