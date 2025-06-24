"""
Field Mapping Management API Endpoints
Provides CRUD operations for field mappings and image discovery
"""
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Any, Optional
import json

from app.config.database import get_db
from app.services.field_mapping_service import FieldMappingService, FieldMapping, FieldType
from app.models.plytix import PlytixProduct

router = APIRouter()

@router.get("/current")
async def get_current_mappings():
    """Get current field mappings configuration"""
    field_service = FieldMappingService()
    
    return {
        "mappings": {
            field: {
                "plytix_field": mapping.plytix_field,
                "webflow_field": mapping.webflow_field,
                "field_type": mapping.field_type.value,
                "required": mapping.required,
                "default_value": mapping.default_value
            }
            for field, mapping in field_service.field_mappings.items()
        },
        "matching_strategy": field_service.matching_strategy,
        "summary": field_service.get_mapping_summary()
    }

@router.post("/update")
async def update_field_mappings(mappings_update: Dict[str, Any]):
    """Update field mappings configuration"""
    try:
        field_service = FieldMappingService()
        
        # Update mappings in memory
        if "field_mappings" in mappings_update:
            for plytix_field, webflow_field in mappings_update["field_mappings"].items():
                field_type = field_service._detect_field_type(plytix_field)
                field_service.field_mappings[plytix_field] = FieldMapping(
                    plytix_field=plytix_field,
                    webflow_field=webflow_field,
                    field_type=field_type,
                    required=plytix_field in ['sku', 'name', 'price']
                )
        
        if "matching_strategy" in mappings_update:
            field_service.matching_strategy = mappings_update["matching_strategy"]
        
        # Save to file
        field_service.save_discovered_mappings()
        
        # Validate updated mappings
        validation_issues = field_service.validate_mappings()
        
        return {
            "success": True,
            "updated_mappings": len(field_service.field_mappings),
            "validation_issues": validation_issues,
            "summary": field_service.get_mapping_summary()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update mappings: {str(e)}")

@router.post("/discover-images")
async def discover_image_fields(sample_product: Dict[str, Any]):
    """Automatically discover image fields from sample product data"""
    try:
        field_service = FieldMappingService()
        discovered_images = field_service.discover_image_fields(sample_product)
        
        return {
            "discovered_images": discovered_images,
            "total_discovered": len(discovered_images),
            "sample_fields": list(sample_product.keys()),
            "recommendations": [
                f"Map '{plytix_field}' to '{webflow_field}'" 
                for plytix_field, webflow_field in discovered_images.items()
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image discovery failed: {str(e)}")

@router.post("/validate")
async def validate_mappings():
    """Validate current field mappings"""
    field_service = FieldMappingService()
    validation_issues = field_service.validate_mappings()
    
    return {
        "valid": len(validation_issues) == 0,
        "issues": validation_issues,
        "total_mappings": len(field_service.field_mappings),
        "required_fields_mapped": len([
            m for m in field_service.field_mappings.values() if m.required
        ])
    }

@router.get("/field-types")
async def get_available_field_types():
    """Get available field types for mapping"""
    return {
        "field_types": [
            {
                "value": field_type.value,
                "description": field_type.name.replace('_', ' ').title()
            }
            for field_type in FieldType
        ]
    }

@router.post("/test-transform")
async def test_field_transformation(test_data: Dict[str, Any]):
    """Test field transformation with sample data"""
    try:
        field_service = FieldMappingService()
        
        # Create a mock PlytixProduct for testing
        from types import SimpleNamespace
        mock_product = SimpleNamespace(**test_data)
        
        # Transform the data
        transformed_data = field_service.transform_product_data(mock_product)
        
        return {
            "original_data": test_data,
            "transformed_data": transformed_data,
            "mappings_applied": len([
                field for field in test_data.keys() 
                if field in field_service.field_mappings
            ]),
            "discovered_images": field_service.discover_image_fields(test_data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transformation test failed: {str(e)}")

@router.post("/import-config")
async def import_field_mappings(file: UploadFile = File(...)):
    """Import field mappings from uploaded JSON file"""
    try:
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="File must be a JSON file")
        
        content = await file.read()
        config_data = json.loads(content.decode('utf-8'))
        
        # Validate the configuration format
        required_keys = ['field_mappings']
        if not all(key in config_data for key in required_keys):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid config format. Required keys: {required_keys}"
            )
        
        # Create new field service with imported config
        field_service = FieldMappingService()
        field_service._process_field_mappings(config_data['field_mappings'])
        
        if 'image_mapping' in config_data:
            field_service._process_image_mappings(config_data['image_mapping'])
        
        field_service.matching_strategy = config_data.get('matching_strategy', 'sku')
        
        # Save imported configuration
        field_service.save_discovered_mappings()
        
        validation_issues = field_service.validate_mappings()
        
        return {
            "success": True,
            "imported_mappings": len(field_service.field_mappings),
            "validation_issues": validation_issues,
            "matching_strategy": field_service.matching_strategy
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@router.get("/export-config")
async def export_field_mappings():
    """Export current field mappings configuration"""
    field_service = FieldMappingService()
    
    config = {
        "field_mappings": {
            mapping.plytix_field: mapping.webflow_field
            for mapping in field_service.field_mappings.values()
        },
        "matching_strategy": field_service.matching_strategy,
        "image_mapping": {
            "discover_automatically": getattr(field_service, 'auto_discover_images', True),
            "primary_image_field": getattr(field_service, 'primary_image_field', 'main_image'),
            "gallery_images_field": getattr(field_service, 'gallery_images_field', 'gallery'),
            "webflow_image_field": getattr(field_service, 'webflow_image_field', 'main-image'),
            "discovered_fields": field_service.discovered_images
        },
        "pdf_file_fields": [
            mapping.plytix_field for mapping in field_service.field_mappings.values()
            if mapping.field_type == FieldType.PDF
        ],
        "description_fields": [
            mapping.plytix_field for mapping in field_service.field_mappings.values()
            if mapping.field_type == FieldType.RICH_TEXT
        ]
    }
    
    return config

@router.get("/sample-mapping")
async def get_sample_mapping():
    """Get a sample field mapping configuration for reference"""
    return {
        "field_mappings": {
            "sku": "sku",
            "name": "name", 
            "description": "description",
            "safety_data_sheet": "safety-data-sheet",
            "specification_sheet": "specification-sheet",
            "web_extended_description": "web-extended-description",
            "price": "price",
            "main_image": "main-image",
            "gallery_images": "gallery-images"
        },
        "matching_strategy": "sku",
        "image_mapping": {
            "discover_automatically": True,
            "primary_image_field": "main_image",
            "gallery_images_field": "gallery",
            "webflow_image_field": "main-image"
        },
        "pdf_file_fields": [
            "safety_data_sheet",
            "specification_sheet"
        ],
        "description_fields": [
            "web_extended_description",
            "description",
            "short_description"
        ]
    }

@router.post("/auto-map")
async def auto_generate_mappings(plytix_fields: List[str], webflow_fields: List[str]):
    """Automatically generate field mappings based on field name similarity"""
    try:
        field_service = FieldMappingService()
        
        # Simple name-based matching algorithm
        auto_mappings = {}
        used_webflow_fields = set()
        
        for plytix_field in plytix_fields:
            plytix_lower = plytix_field.lower().replace('_', '').replace('-', '')
            best_match = None
            best_score = 0
            
            for webflow_field in webflow_fields:
                if webflow_field in used_webflow_fields:
                    continue
                    
                webflow_lower = webflow_field.lower().replace('_', '').replace('-', '')
                
                # Calculate similarity score
                if plytix_lower == webflow_lower:
                    score = 100
                elif plytix_lower in webflow_lower or webflow_lower in plytix_lower:
                    score = 80
                elif any(word in webflow_lower for word in plytix_lower.split()):
                    score = 60
                else:
                    score = 0
                
                if score > best_score:
                    best_match = webflow_field
                    best_score = score
            
            if best_match and best_score >= 60:  # Threshold for auto-mapping
                auto_mappings[plytix_field] = best_match
                used_webflow_fields.add(best_match)
        
        return {
            "auto_mappings": auto_mappings,
            "confidence_threshold": 60,
            "unmapped_plytix_fields": [
                field for field in plytix_fields if field not in auto_mappings
            ],
            "unused_webflow_fields": [
                field for field in webflow_fields if field not in used_webflow_fields
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-mapping failed: {str(e)}")