from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum

class WebflowPriceUnit(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

class WebflowPrice(BaseModel):
    value: int  # Price in cents
    unit: WebflowPriceUnit = WebflowPriceUnit.USD

class WebflowInventory(BaseModel):
    type: str = "finite"  # or "infinite"
    quantity: int = 0

class WebflowSKUProperty(BaseModel):
    name: str
    enum: List[str]

class WebflowSKU(BaseModel):
    sku: str
    price: WebflowPrice
    inventory: WebflowInventory
    sku_values: Dict[str, str] = Field(default_factory=dict)

class WebflowProduct(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    product_type: str = "Advanced"  # Required for variants
    sku_properties: List[WebflowSKUProperty] = Field(default_factory=list)
    skus: List[WebflowSKU] = Field(default_factory=list)
    main_image: Optional[str] = None

class WebflowProductResponse(BaseModel):
    id: str
    name: str
    slug: str
    created_on: str
    updated_on: str