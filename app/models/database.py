from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.config.database import Base

class SyncState(Base):
    __tablename__ = "sync_states"
    
    id = Column(Integer, primary_key=True, index=True)
    last_sync_time = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), nullable=False)
    products_processed = Column(Integer, default=0)
    variants_processed = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    sync_duration_seconds = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    errors = relationship("SyncError", back_populates="sync_state")

class ProductMapping(Base):
    __tablename__ = "product_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    plytix_product_id = Column(String(255), nullable=False, index=True)
    webflow_product_id = Column(String(255), nullable=True, index=True)
    webflow_collection_id = Column(String(255), nullable=True, index=True)  # Track collection
    plytix_sku = Column(String(255), nullable=False)
    webflow_sku = Column(String(255), nullable=True)
    product_name = Column(String(500))
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    variants = relationship("VariantMapping", back_populates="product")

class VariantMapping(Base):
    __tablename__ = "variant_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    product_mapping_id = Column(Integer, ForeignKey("product_mappings.id"), nullable=False)
    plytix_variant_id = Column(String(255), nullable=False, index=True)
    webflow_sku_id = Column(String(255), nullable=True, index=True)
    variant_sku = Column(String(255), nullable=False)
    variant_attributes = Column(JSON)  # Store variant attributes as JSON
    price_cents = Column(Integer)  # Store price in cents
    inventory_quantity = Column(Integer)
    last_synced = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    product = relationship("ProductMapping", back_populates="variants")

class SyncError(Base):
    __tablename__ = "sync_errors"
    
    id = Column(Integer, primary_key=True, index=True)
    sync_state_id = Column(Integer, ForeignKey("sync_states.id"), nullable=False)
    plytix_product_id = Column(String(255), index=True)
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text)
    error_data = Column(JSON)  # Store additional error context
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    sync_state = relationship("SyncState", back_populates="errors")