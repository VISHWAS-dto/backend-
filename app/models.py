from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    businesses = relationship("Business", back_populates="user")


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    logo_url = Column(String, nullable=True)
    brand_colors = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="businesses")
    products = relationship("Product", back_populates="business")
    catalogues = relationship("Catalogue", back_populates="business")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String, nullable=False)
    sku = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    business = relationship("Business", back_populates="products")
    images = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    ai_jobs = relationship("AiJob", back_populates="product")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    image_url = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Result of the deterministic pre-AI quality checks in app.validation.
    # validation_status is "READY_FOR_AI_GENERATION" or "NEEDS_ATTENTION";
    # validation_reasons is a newline-separated list of failure reasons ("" when
    # the image passed).
    validation_status = Column(String, nullable=True)
    validation_reasons = Column(Text, nullable=True)

    product = relationship("Product", back_populates="images")


class AiJob(Base):
    __tablename__ = "ai_jobs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    status = Column(String, default="PENDING", nullable=False)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    product = relationship("Product", back_populates="ai_jobs")
    catalogues = relationship("Catalogue", back_populates="ai_job")


class Catalogue(Base):
    __tablename__ = "catalogues"

    id = Column(Integer, primary_key=True, index=True)
    ai_job_id = Column(Integer, ForeignKey("ai_jobs.id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    template_name = Column(String, nullable=True)
    content_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    ai_job = relationship("AiJob", back_populates="catalogues")
    business = relationship("Business", back_populates="catalogues")
