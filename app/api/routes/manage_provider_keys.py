# app/api/routes/manage_provider_keys.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.supabase_client import get_supabase_client
from supabase import Client
import logging
from cryptography.fernet import Fernet
import base64  # Thêm import base64 để sử dụng trong mã hóa/giải mã

# Initialize logger
logger = logging.getLogger(__name__)

# Create router (loại bỏ dấu / ở cuối để tránh redirect)
router = APIRouter(prefix="/api/v1/provider-keys")

# Initialize settings
settings = get_settings()

# --- Pydantic Models ---
class ProviderKeyBase(BaseModel):
    provider_name: str = Field(..., description="Provider name (google, xai, gigachat, perplexity)")
    name: Optional[str] = Field(None, description="Optional descriptive name for the key")

class ProviderKeyCreate(ProviderKeyBase):
    api_key: str = Field(..., description="Provider API key to store (will be encrypted)")

class ProviderKeyInfo(ProviderKeyBase):
    id: str = Field(..., description="Unique ID for the provider key")
    is_selected: bool = Field(..., description="Whether this key is selected as default for this provider")
    created_at: str = Field(..., description="Creation timestamp")

class ProviderKeyUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Optional descriptive name for the key")
    is_selected: Optional[bool] = Field(None, description="Whether this key should be selected as default")

# --- Helper Functions ---
def get_encryption_key() -> bytes:
    """Get encryption key from settings or generate one"""
    # In production, you should store this key securely and persistently
    # For now, we'll use a derived key from SUPABASE_SERVICE_ROLE_KEY for simplicity
    
    # WARNING: In a real production environment, you would want a dedicated 
    # encryption key that is properly managed and stored securely
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server encryption configuration missing"
        )
    
    # Derive a 32-byte key (suitable for Fernet)
    # In production, use a proper key management solution
    import hashlib
    derived_key = hashlib.sha256(settings.SUPABASE_SERVICE_ROLE_KEY.encode()).digest()
    return derived_key

def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key before storing it"""
    try:
        key = get_encryption_key()
        f = Fernet(Fernet.generate_key() if not key else base64.urlsafe_b64encode(key))
        return f.encrypt(api_key.encode()).decode()
    except Exception as e:
        logger.error(f"Error encrypting API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not securely store API key"
        )

def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key from storage"""
    try:
        key = get_encryption_key()
        f = Fernet(base64.urlsafe_b64encode(key))
        return f.decrypt(encrypted_key.encode()).decode()
    except Exception as e:
        logger.error(f"Error decrypting API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve stored API key"
        )

# --- CRUD Endpoints ---
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ProviderKeyInfo)
# Chuyển thành hàm đồng bộ (def)
def create_provider_key(
    key_data: ProviderKeyCreate,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Create a new provider API key for the authenticated user"""
    
    # Validate provider name
    valid_providers = ['google', 'xai', 'gigachat', 'perplexity']
    if key_data.provider_name not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider name. Must be one of: {', '.join(valid_providers)}"
        )
    
    try:
        # Encrypt the API key
        encrypted_key = encrypt_api_key(key_data.api_key)
        
        # Insert into database
        response = supabase.table("user_provider_keys").insert({
            "user_id": user_id,
            "provider_name": key_data.provider_name,
            "api_key_encrypted": encrypted_key,
            "name": key_data.name,
            "is_selected": False,  # New keys are not selected by default
        }).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create provider key"
            )
        
        return response.data[0]
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating provider key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating provider key: {str(e)}"
        )

@router.get("/", response_model=List[ProviderKeyInfo])
async def get_provider_keys(
    provider: Optional[str] = None,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Get all provider keys for the authenticated user"""
    try:
        query = supabase.table("user_provider_keys").select("*").eq("user_id", user_id)
        
        # Filter by provider if specified
        if provider:
            query = query.eq("provider_name", provider)
            
        response = query.execute()
        return response.data
        
    except Exception as e:
        logger.error(f"Error retrieving provider keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider keys"
        )

@router.get("/{key_id}", response_model=ProviderKeyInfo)
async def get_provider_key(
    key_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Get a specific provider key by ID"""
    try:
        response = supabase.table("user_provider_keys").select("*").eq("id", key_id).eq("user_id", user_id).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider key not found"
            )
            
        return response.data[0]
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving provider key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider key"
        )

@router.patch("/{key_id}", response_model=ProviderKeyInfo)
async def update_provider_key(
    key_id: str,
    key_update: ProviderKeyUpdate,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Update a provider key (name or selection status)"""
    try:
        # First, verify the key exists and belongs to this user
        check_response = supabase.table("user_provider_keys").select("provider_name").eq("id", key_id).eq("user_id", user_id).execute()
        
        if not check_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider key not found or not owned by you"
            )
            
        provider_name = check_response.data[0]['provider_name']
        
        # Prepare update data
        update_data = {}
        if key_update.name is not None:
            update_data["name"] = key_update.name
            
        if key_update.is_selected is not None:
            update_data["is_selected"] = key_update.is_selected
            
            # If setting to selected, unselect other keys for this provider
            if key_update.is_selected:
                # Transaction would be better here but we'll use sequential operations
                # First, unselect all other keys for this provider
                supabase.table("user_provider_keys").update(
                    {"is_selected": False}
                ).eq("user_id", user_id).eq("provider_name", provider_name).execute()
        
        # Update the specified key
        if update_data:
            response = supabase.table("user_provider_keys").update(
                update_data
            ).eq("id", key_id).eq("user_id", user_id).execute()
            
            if not response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update provider key"
                )
                
            return response.data[0]
        else:
            # If nothing to update, just return the current data
            response = supabase.table("user_provider_keys").select("*").eq("id", key_id).eq("user_id", user_id).execute()
            return response.data[0]
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating provider key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update provider key: {str(e)}"
        )

@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_key(
    key_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Delete a provider key"""
    try:
        # Verify the key exists and belongs to this user
        check_response = supabase.table("user_provider_keys").select("id").eq("id", key_id).eq("user_id", user_id).execute()
        
        if not check_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider key not found or not owned by you"
            )
            
        # Delete the key
        supabase.table("user_provider_keys").delete().eq("id", key_id).eq("user_id", user_id).execute()
        
        return None
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting provider key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete provider key"
        )

@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_provider_keys_for_provider(
    provider_name: str, # Lấy từ query parameter
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """Delete all provider keys for a specific provider for the authenticated user"""
    try:
        # Validate provider name (optional but good practice)
        valid_providers = ['google', 'xai', 'gigachat', 'perplexity']
        if provider_name not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider name specified for deletion."
            )

        # Delete all keys for the specified provider and user
        # Không cần check trước vì delete sẽ không làm gì nếu không có bản ghi khớp
        supabase.table("user_provider_keys").delete().eq(
            "user_id", user_id
        ).eq(
            "provider_name", provider_name
        ).execute()

        # Log action (optional, can be done via the activity log endpoint from frontend)
        logger.info(f"Deleted all keys for provider '{provider_name}' for user {user_id}")

        return None # Return None for 204 No Content

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting all keys for provider {provider_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete keys for provider {provider_name}"
        )