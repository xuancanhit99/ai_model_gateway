# app/api/routes/manage_keys.py
from fastapi import APIRouter, Depends, HTTPException, status, Path, Body # Import Body
from typing import List, Dict, Any, Optional # Import Optional
from datetime import datetime, timezone
import logging

from app.core.auth import get_current_user, generate_api_key, hash_api_key
from app.core.supabase_client import get_supabase_client
from app.models.schemas import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyInfo,
    ApiKeyListResponse,
    StatusResponse,
    ErrorResponse,
    
)
from supabase import Client
from postgrest import APIResponse # Import for type hinting
from pydantic import BaseModel # Import BaseModel for simple request body

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/keys", # Prefix for all routes in this router
    tags=["API Key Management"], # Tag for OpenAPI documentation
)

# Optional: Define a simple request body model for PATCH
class ApiKeyActivatePayload(BaseModel):
    is_active: bool

@router.post(
    "", # Route path relative to prefix, so it becomes /api/v1/keys
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API Key for the authenticated user",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Invalid or expired JWT"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
async def create_new_api_key(
    request_body: ApiKeyCreateRequest,
    current_user_id: str = Depends(get_current_user), # Get user ID from JWT
    supabase: Client = Depends(get_supabase_client)
):
    """
    Generates a new API key (hp_...), hashes it, stores metadata in Supabase,
    and returns the full key **ONCE**. The user must save this key securely.
    """
    try:
        # 1. Generate the new key components
        full_api_key, key_prefix_lookup, secret_part = generate_api_key()
        # Note: We hash the *full* key, not just the secret part
        hashed_key = hash_api_key(full_api_key)

        # 2. Prepare data for Supabase insertion
        key_data_to_insert = {
            "user_id": current_user_id,
            "key_prefix": key_prefix_lookup, # Store the lookup prefix
            "key_hash": hashed_key,
            "name": request_body.name,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            # last_used_at will be null initially
        }

        # 3. Insert into Supabase
        logger.info(f"Attempting to insert API key for user {current_user_id} with prefix {key_prefix_lookup}")
        # Remove await and type hint as .execute() seems synchronous here too
        insert_response = supabase.table("api_keys") \
                                             .insert(key_data_to_insert) \
                                             .execute()

        # Check for insertion errors (Postgrest typically raises exceptions on failure,
        # but double-checking the response might be useful depending on configuration)
        if not insert_response.data:
             # Log the actual response if possible
            logger.error(f"Failed to insert API key into Supabase for user {current_user_id}. Response: {insert_response}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Không thể tạo API key trong cơ sở dữ liệu."
            )

        logger.info(f"Successfully created API key with prefix {key_prefix_lookup} for user {current_user_id}")

        # 4. Return the response including the full key
        return ApiKeyCreateResponse(
            name=request_body.name,
            key_prefix=key_prefix_lookup,
            full_api_key=full_api_key, # Return the full key this one time
            created_at=key_data_to_insert["created_at"], # Use the generated timestamp
            user_id=current_user_id
        )

    except HTTPException as e:
        # Re-raise HTTPExceptions (like 401 from get_current_user)
        raise e
    except Exception as e:
        logger.exception(f"Lỗi không mong đợi khi tạo API key cho user {current_user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đã xảy ra lỗi không mong đợi khi tạo API key."
        )

@router.get(
    "", # Route path relative to prefix, so it becomes /api/v1/keys
    response_model=ApiKeyListResponse,
    summary="List API Keys for the authenticated user",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Invalid or expired JWT"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
async def list_user_api_keys(
    current_user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Retrieves metadata for all API keys associated with the authenticated user.
    Does not return the key hash or the full key.
    """
    try:
        logger.info(f"Fetching API keys for user {current_user_id}")
        # Remove await as .execute() might be synchronous in this context
        response = supabase.table("api_keys") \
                                      .select("key_prefix, name, created_at, last_used_at, is_active, user_id") \
                                      .eq("user_id", current_user_id) \
                                      .order("created_at", desc=True) \
                                      .execute()

        # Postgrest returns data even if empty, so check the list
        keys_data = response.data if response.data else []
        logger.debug(f"Found {len(keys_data)} keys for user {current_user_id}")

        # Convert raw data to ApiKeyInfo models
        api_keys_info = [ApiKeyInfo(**key) for key in keys_data]

        return ApiKeyListResponse(keys=api_keys_info)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"Lỗi khi lấy danh sách API key cho user {current_user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đã xảy ra lỗi khi truy vấn danh sách API key."
        )

@router.patch(
    "/{key_prefix_to_activate}", # Use path parameter for the prefix
    response_model=StatusResponse,
    summary="Activate an API Key for the authenticated user",
    responses={
        status.HTTP_200_OK: {"model": StatusResponse, "description": "API Key activated successfully"},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Invalid or expired JWT"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "User does not own this key or key not found"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "API Key with the specified prefix not found for this user"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse, "description": "Invalid request body or key prefix"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
async def activate_api_key(
    key_prefix_to_activate: str = Path(..., description="The prefix (first 6 chars after 'hp_') of the API key to activate."),
    payload: ApiKeyActivatePayload = Body(..., description="Payload indicating the desired state (must be is_active: true)"),
    current_user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Activates (sets is_active=true) an API key identified by its prefix,
    ensuring the key belongs to the authenticated user and is currently inactive.
    """
    # Input validation for prefix length
    if len(key_prefix_to_activate) != 6: # Assuming API_KEY_PREFIX_LOOKUP_LENGTH is 6
         raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Định dạng key prefix không hợp lệ."
        )

    # Validate payload - ensure we are actually activating
    if not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chỉ có thể kích hoạt key (is_active phải là true)."
        )

    try:
        logger.info(f"Attempting to activate API key with prefix {key_prefix_to_activate} for user {current_user_id}")

        # Update the key, but only if it belongs to the current user
        # We could add .eq("is_active", False) here too, but updating an already active key is idempotent
        update_response = supabase.table("api_keys") \
                                             .update({"is_active": True}) \
                                             .eq("key_prefix", key_prefix_to_activate) \
                                             .eq("user_id", current_user_id) \
                                             .execute()

        # Check if any row was actually updated
        if not update_response.data:
            # Check if the key prefix exists at all for this user to give a better error
            # Use synchronous execute based on previous observations
            check_exists_response = supabase.table("api_keys") \
                                                      .select("key_prefix, is_active") \
                                                      .eq("key_prefix", key_prefix_to_activate) \
                                                      .eq("user_id", current_user_id) \
                                                      .limit(1) \
                                                      .execute()
            if not check_exists_response.data:
                 logger.warning(f"API key with prefix {key_prefix_to_activate} not found for user {current_user_id} during activation attempt.")
                 raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Không tìm thấy API key với prefix '{key_prefix_to_activate}'."
                )
            # Optional: Check if it was already active
            elif check_exists_response.data[0].get("is_active"):
                 logger.info(f"API key {key_prefix_to_activate} for user {current_user_id} was already active.")
                 # Return success as it's already in the desired state
                 return StatusResponse(status="success", message="API key đã được kích hoạt (hoặc đã kích hoạt trước đó).")
            else:
                 # This case means the key exists, belongs to user, is inactive, but update failed.
                 logger.error(f"Update failed unexpectedly during activation for key {key_prefix_to_activate}, user {current_user_id}. Response: {update_response}")
                 raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Không thể kích hoạt API key do lỗi máy chủ."
                )

        logger.info(f"Successfully activated API key with prefix {key_prefix_to_activate} for user {current_user_id}")
        return StatusResponse(status="success", message="API key đã được kích hoạt thành công.")

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"Lỗi khi kích hoạt API key {key_prefix_to_activate} cho user {current_user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đã xảy ra lỗi không mong đợi khi kích hoạt API key."
        )


@router.delete(
    "/{key_prefix_to_delete}", # Path for DEACTIVATION
    response_model=StatusResponse,
    summary="Deactivate an API Key for the authenticated user",
    description="This endpoint sets the 'is_active' flag to false, but does not permanently delete the key.",
    responses={
        status.HTTP_200_OK: {"model": StatusResponse, "description": "API Key deactivated successfully"}, # Added 200 OK
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Invalid or expired JWT"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "User does not own this key or key not found"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "API Key with the specified prefix not found for this user"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse, "description": "Invalid key prefix format"}, # Added 422
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
async def deactivate_api_key(
    key_prefix_to_delete: str = Path(..., description="The prefix (first 6 chars after 'hp_') of the API key to deactivate."),
    current_user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Deactivates (sets is_active=false) an API key identified by its prefix,
    ensuring the key belongs to the authenticated user.
    """
    # Input validation for prefix length
    if len(key_prefix_to_delete) != 6: # Assuming API_KEY_PREFIX_LOOKUP_LENGTH is 6
         raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Định dạng key prefix không hợp lệ."
        )

    try:
        logger.info(f"Attempting to deactivate API key with prefix {key_prefix_to_delete} for user {current_user_id}")

        # Update the key, but only if it belongs to the current user
        # Remove await and type hint as .execute() seems synchronous here too
        update_response = supabase.table("api_keys") \
                                             .update({"is_active": False}) \
                                             .eq("key_prefix", key_prefix_to_delete) \
                                             .eq("user_id", current_user_id) \
                                             .execute()

        # Check if any row was actually updated
        # Note: PostgREST update returns the updated data. If no rows matched the filter, data will be empty.
        if not update_response.data:
            # Check if the key prefix exists at all for this user to give a better error
            # Use synchronous execute
            check_exists_response = supabase.table("api_keys") \
                                                      .select("key_prefix") \
                                                      .eq("key_prefix", key_prefix_to_delete) \
                                                      .eq("user_id", current_user_id) \
                                                      .limit(1) \
                                                      .execute()
            if not check_exists_response.data:
                 logger.warning(f"API key with prefix {key_prefix_to_delete} not found for user {current_user_id} during deactivation.")
                 raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Không tìm thấy API key với prefix '{key_prefix_to_delete}'."
                )
            else:
                 # Key exists but wasn't updated (maybe already inactive?)
                 # Consider returning success if already inactive, or a specific message
                 logger.info(f"API key {key_prefix_to_delete} for user {current_user_id} might already be inactive or update failed.")
                 # Let's return success for idempotency
                 return StatusResponse(status="success", message="API key đã được vô hiệu hóa (hoặc đã vô hiệu hóa trước đó).")


        logger.info(f"Successfully deactivated API key with prefix {key_prefix_to_delete} for user {current_user_id}")
        return StatusResponse(status="success", message="API key đã được vô hiệu hóa.")

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"Lỗi khi vô hiệu hóa API key {key_prefix_to_delete} cho user {current_user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đã xảy ra lỗi khi vô hiệu hóa API key."
        )

@router.delete(
    "/{key_prefix_to_delete}/permanent", # Distinct path for PERMANENT deletion
    response_model=StatusResponse,
    summary="Permanently delete an API Key for the authenticated user",
    description="DANGER ZONE: This endpoint permanently removes the API key record from the database. This action cannot be undone.",
    responses={
        status.HTTP_200_OK: {"model": StatusResponse, "description": "API Key permanently deleted successfully"},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Invalid or expired JWT"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "User does not own this key or key not found"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "API Key with the specified prefix not found for this user"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse, "description": "Invalid key prefix format"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
async def delete_api_key_permanently(
    key_prefix_to_delete: str = Path(..., description="The prefix (first 6 chars after 'hp_') of the API key to permanently delete."),
    current_user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Permanently deletes an API key record identified by its prefix from the database,
    ensuring the key belongs to the authenticated user.
    """
    # Input validation for prefix length
    if len(key_prefix_to_delete) != 6:
         raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Định dạng key prefix không hợp lệ."
        )

    try:
        logger.warning(f"Attempting to PERMANENTLY DELETE API key with prefix {key_prefix_to_delete} for user {current_user_id}")

        # Perform the delete operation, ensuring the key belongs to the user
        delete_response = supabase.table("api_keys") \
                                             .delete() \
                                             .eq("key_prefix", key_prefix_to_delete) \
                                             .eq("user_id", current_user_id) \
                                             .execute()

        # Check if any row was actually deleted
        # PostgREST delete returns the deleted data. If no rows matched, data will be empty.
        if not delete_response.data:
            # Check if the key ever existed for this user to give a 404 vs 403/other
            check_exists_response = supabase.table("api_keys") \
                                                      .select("key_prefix") \
                                                      .eq("key_prefix", key_prefix_to_delete) \
                                                      .eq("user_id", current_user_id) \
                                                      .limit(1) \
                                                      .execute()
            if not check_exists_response.data:
                 logger.warning(f"API key with prefix {key_prefix_to_delete} not found for user {current_user_id} during permanent delete attempt.")
                 raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Không tìm thấy API key với prefix '{key_prefix_to_delete}' để xóa."
                )
            else:
                 # Key exists but wasn't deleted - this indicates an unexpected server error
                 logger.error(f"Permanent delete failed unexpectedly for key {key_prefix_to_delete}, user {current_user_id}. Response: {delete_response}")
                 raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Không thể xóa vĩnh viễn API key do lỗi máy chủ."
                )

        logger.info(f"Successfully PERMANENTLY DELETED API key with prefix {key_prefix_to_delete} for user {current_user_id}")
        return StatusResponse(status="success", message="API key đã được xóa vĩnh viễn.")

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"Lỗi khi xóa vĩnh viễn API key {key_prefix_to_delete} cho user {current_user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Đã xảy ra lỗi không mong đợi khi xóa vĩnh viễn API key."
        )