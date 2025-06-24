from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class PlytixVariantAttribute(BaseModel):
    name: str
    value: str

class PlytixVariant(BaseModel):
    id: str
    sku: str
    attributes: Dict[str, str] = Field(default_factory=dict)
    price: Optional[float] = None
    inventory: Optional[int] = 0
    images: List[str] = Field(default_factory=list)
    active: bool = True

class PlytixProduct(BaseModel):
    id: str
    sku: str
    thumbnail: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    num_variations: int = 0
    product_family_id: Optional[str] = None
    product_family_model_id: Optional[str] = None
    modified_user_audit: Optional[Dict[str, Any]] = None
    created_user_audit: Optional[Dict[str, Any]] = None
    overwritten_attributes: List[Any] = Field(default_factory=list)
    categories: List[Any] = Field(default_factory=list)
    
    # Derived/computed fields that we'll populate from attributes or details
    name: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    variants: List[PlytixVariant] = Field(default_factory=list)
    modified_at: Optional[datetime] = None
    active: bool = True
    
    # Store detailed product data if fetched
    detailed_attributes: Optional[Dict[str, Any]] = None

class PlytixProductsResponse(BaseModel):
    data: List[PlytixProduct]  # Changed from 'results' to 'data'
    pagination: Dict[str, Any] = Field(default_factory=dict)
    
    # Legacy support
    @property
    def results(self) -> List[PlytixProduct]:
        return self.data
    
    @property
    def count(self) -> int:
        return self.pagination.get('total_count', len(self.data))