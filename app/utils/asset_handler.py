"""
Asset Handler for Plytix to Webflow Integration
Handles images and files (PDFs) with options for direct linking or Webflow assets upload
"""
import httpx
import hashlib
import structlog
import mimetypes
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

logger = structlog.get_logger()

class AssetHandler:
    """Handles asset processing for Plytix to Webflow integration"""
    
    def __init__(self, webflow_client=None):
        self.webflow_client = webflow_client
        self._http_client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close HTTP client"""
        await self._http_client.aclose()
    
    async def process_plytix_image(self, plytix_image_data: Any, upload_to_webflow: bool = False) -> Optional[Dict[str, Any]]:
        """
        Process Plytix image data for Webflow
        
        Args:
            plytix_image_data: Image data from Plytix (URL, dict, or list)
            upload_to_webflow: Whether to upload to Webflow assets or use direct URL
            
        Returns:
            Webflow-formatted image object or None
        """
        # Extract URL from various Plytix formats
        image_url = self._extract_image_url(plytix_image_data)
        if not image_url:
            return None
        
        # Skip Plytix placeholders/defaults
        if self._is_placeholder_image(image_url):
            logger.debug("Skipping Plytix placeholder image", url=image_url)
            return None
        
        if upload_to_webflow and self.webflow_client:
            # Option 2: Upload to Webflow assets
            return await self._upload_image_to_webflow(image_url)
        else:
            # Option 1: Use direct Plytix URL
            return self._format_direct_image_link(image_url)
    
    async def process_plytix_file(self, plytix_file_data: Any, upload_to_webflow: bool = False) -> Optional[Dict[str, Any]]:
        """
        Process Plytix file data (PDFs) for Webflow
        
        Args:
            plytix_file_data: File data from Plytix
            upload_to_webflow: Whether to upload to Webflow assets or use direct URL
            
        Returns:
            Webflow-formatted file object or None
        """
        # Extract file info from various Plytix formats
        file_info = self._extract_file_info(plytix_file_data)
        if not file_info:
            return None
        
        if upload_to_webflow and self.webflow_client:
            # Option 2: Upload to Webflow assets
            return await self._upload_file_to_webflow(file_info['url'], file_info['filename'])
        else:
            # Option 1: Use direct Plytix URL
            return self._format_direct_file_link(file_info)
    
    def _extract_image_url(self, image_data: Any) -> Optional[str]:
        """Extract image URL from various Plytix formats"""
        if isinstance(image_data, str) and image_data.strip():
            return image_data.strip()
        elif isinstance(image_data, list) and image_data:
            # Get first valid URL from list
            for item in image_data:
                if isinstance(item, str) and item.strip():
                    return item.strip()
        elif isinstance(image_data, dict):
            # Handle complex image objects
            return (image_data.get('url') or 
                   image_data.get('file_url') or 
                   image_data.get('download_url'))
        return None
    
    def _extract_file_info(self, file_data: Any) -> Optional[Dict[str, str]]:
        """Extract file info from various Plytix formats"""
        if isinstance(file_data, dict):
            url = (file_data.get('url') or 
                  file_data.get('file_url') or 
                  file_data.get('download_url'))
            if url:
                return {
                    'url': url,
                    'filename': file_data.get('name', file_data.get('filename', 'document.pdf')),
                    'fileId': file_data.get('fileId', file_data.get('id', ''))
                }
        elif isinstance(file_data, str) and file_data.strip():
            # Handle string representation of dict
            if file_data.startswith("{'") or file_data.startswith('{"'):
                try:
                    import ast
                    parsed_dict = ast.literal_eval(file_data)
                    if isinstance(parsed_dict, dict):
                        return self._extract_file_info(parsed_dict)
                except:
                    pass
            # Handle direct URL
            elif file_data.startswith(('http://', 'https://')):
                return {
                    'url': file_data,
                    'filename': file_data.split('/')[-1] if '/' in file_data else 'document.pdf',
                    'fileId': ''
                }
        return None
    
    def _is_placeholder_image(self, url: str) -> bool:
        """Check if image URL is a Plytix placeholder"""
        placeholder_indicators = [
            'static.plytix.com/template',
            'default',
            'placeholder',
            'no-image'
        ]
        return any(indicator in url.lower() for indicator in placeholder_indicators)
    
    def _format_direct_image_link(self, image_url: str) -> Dict[str, Any]:
        """Format image for direct Plytix URL usage - matching working script"""
        # Remove /thumb/ from URL to get original image (like in working script)
        clean_url = image_url.replace('/thumb/', '/file/')
        
        return {
            "url": clean_url,
            "alt": self._generate_alt_text(clean_url)
        }
    
    def _format_direct_file_link(self, file_info: Dict[str, str]) -> Dict[str, Any]:
        """Format file for direct Plytix URL usage - matching working script"""
        # Clean URL to remove /thumb/ if present
        clean_url = file_info['url'].replace('/thumb/', '/file/')
        
        return {
            "fileId": file_info.get('fileId', ''),
            "url": clean_url,
            "alt": file_info.get('filename', 'Document')
        }
    
    def _generate_alt_text(self, url: str) -> str:
        """Generate alt text from URL"""
        filename = url.split('/')[-1] if '/' in url else 'Product image'
        return filename
    
    async def process_safety_data_sheet(self, plytix_product_data: dict, upload_to_webflow: bool = True) -> Optional[Dict[str, Any]]:
        """Process safety data sheet from Plytix product attributes"""
        try:
            attributes = plytix_product_data.get('attributes', {})
            safety_sheet_data = attributes.get('safety_data_sheet') or attributes.get('sds') or attributes.get('safety_sheet')
            
            if not safety_sheet_data:
                return None
            
            if upload_to_webflow and self.webflow_client:
                # Extract file info and upload to Webflow
                file_info = self._extract_file_info(safety_sheet_data)
                if file_info:
                    return await self._upload_file_to_webflow(file_info['url'], file_info['filename'])
            else:
                # Use direct URL
                return self.process_asset_from_attribute(safety_sheet_data, "file")
                
        except Exception as e:
            logger.error("Error processing safety data sheet", error=str(e))
            return None
    
    async def process_specification_sheet(self, plytix_product_data: dict, upload_to_webflow: bool = True) -> Optional[Dict[str, Any]]:
        """Process specification sheet from Plytix product attributes"""
        try:
            attributes = plytix_product_data.get('attributes', {})
            spec_sheet_data = (attributes.get('specification_sheet') or 
                             attributes.get('spec_sheet') or 
                             attributes.get('product_specification') or
                             attributes.get('datasheet'))
            
            if not spec_sheet_data:
                return None
            
            if upload_to_webflow and self.webflow_client:
                # Extract file info and upload to Webflow
                file_info = self._extract_file_info(spec_sheet_data)
                if file_info:
                    return await self._upload_file_to_webflow(file_info['url'], file_info['filename'])
            else:
                # Use direct URL
                return self.process_asset_from_attribute(spec_sheet_data, "file")
                
        except Exception as e:
            logger.error("Error processing specification sheet", error=str(e))
            return None
    
    async def _upload_image_to_webflow(self, image_url: str) -> Optional[Dict[str, Any]]:
        """Upload image to Webflow assets using the Assets API"""
        try:
            logger.info("Uploading image to Webflow assets", url=image_url[:50])
            
            # Download image from Plytix
            response = await self._http_client.get(image_url)
            response.raise_for_status()
            image_data = response.content
            
            # Generate filename and content type
            filename = self._generate_filename_from_url(image_url, 'image')
            content_type = mimetypes.guess_type(filename)[0] or 'image/jpeg'
            
            # Step 1: Create asset in Webflow to get upload URL
            asset_response = await self.webflow_client._make_request(
                f"/sites/{self.webflow_client.site_id}/assets",
                method="POST",
                json_data={
                    "fileName": filename,
                    "fileHash": hashlib.md5(image_data).hexdigest()
                }
            )
            
            # Step 2: Upload to the provided upload URL
            upload_url = asset_response.get("uploadUrl")
            upload_details = asset_response.get("uploadDetails", {})
            
            if upload_url and upload_details:
                # Prepare form data for upload
                form_data = {}
                for key, value in upload_details.items():
                    form_data[key] = value
                
                # Add the file data
                files = {
                    "file": (filename, image_data, content_type)
                }
                
                # Upload to Webflow's provided URL
                upload_response = await self._http_client.post(
                    upload_url,
                    data=form_data,
                    files=files
                )
                upload_response.raise_for_status()
                
                logger.info("Successfully uploaded image to Webflow", 
                          filename=filename, 
                          asset_id=asset_response.get("id"))
                
                return {
                    "fileId": asset_response.get("id", ""),
                    "url": asset_response.get("hostedUrl", image_url),
                    "alt": self._generate_alt_text(image_url)
                }
            else:
                logger.warning("No upload URL provided in asset response")
                return self._format_direct_image_link(image_url)
            
        except Exception as e:
            logger.warning("Failed to upload image to Webflow, using direct URL", 
                         error=str(e), url=image_url[:50])
            return self._format_direct_image_link(image_url)
    
    async def _upload_file_to_webflow(self, file_url: str, filename: str) -> Optional[Dict[str, Any]]:
        """Upload file (PDF/document) to Webflow assets using the Assets API"""
        try:
            logger.info("Uploading file to Webflow assets", url=file_url[:50], filename=filename)
            
            # Download file from Plytix
            response = await self._http_client.get(file_url)
            response.raise_for_status()
            file_data = response.content
            
            # Generate content type
            content_type = mimetypes.guess_type(filename)[0] or 'application/pdf'
            
            # Step 1: Create asset in Webflow to get upload URL
            asset_response = await self.webflow_client._make_request(
                f"/sites/{self.webflow_client.site_id}/assets",
                method="POST",
                json_data={
                    "fileName": filename,
                    "fileHash": hashlib.md5(file_data).hexdigest()
                }
            )
            
            # Step 2: Upload to the provided upload URL
            upload_url = asset_response.get("uploadUrl")
            upload_details = asset_response.get("uploadDetails", {})
            
            if upload_url and upload_details:
                # Prepare form data for upload
                form_data = {}
                for key, value in upload_details.items():
                    form_data[key] = value
                
                # Add the file data
                files = {
                    "file": (filename, file_data, content_type)
                }
                
                # Upload to Webflow's provided URL
                upload_response = await self._http_client.post(
                    upload_url,
                    data=form_data,
                    files=files
                )
                upload_response.raise_for_status()
                
                logger.info("Successfully uploaded file to Webflow", 
                          filename=filename, 
                          asset_id=asset_response.get("id"))
                
                return {
                    "fileId": asset_response.get("id", ""),
                    "url": asset_response.get("hostedUrl", file_url),
                    "alt": filename
                }
            else:
                logger.warning("No upload URL provided in asset response")
                return self._format_direct_file_link({
                    'url': file_url,
                    'filename': filename,
                    'fileId': ''
                })
            
        except Exception as e:
            logger.warning("Failed to upload file to Webflow, using direct URL", 
                         error=str(e), url=file_url[:50], filename=filename)
            return self._format_direct_file_link({
                'url': file_url,
                'filename': filename,
                'fileId': ''
            })
    
    def _generate_filename_from_url(self, url: str, asset_type: str) -> str:
        """Generate a clean filename from URL"""
        # Extract filename from URL
        if '/' in url:
            filename = url.split('/')[-1]
        else:
            filename = f"{asset_type}_asset"
        
        # Clean filename
        import re
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Ensure it has an extension
        if '.' not in filename:
            ext = '.jpg' if asset_type == 'image' else '.pdf'
            filename += ext
        
        # Limit length
        if len(filename) > 100:
            name, ext = filename.rsplit('.', 1)
            filename = name[:90] + '.' + ext
        
        return filename