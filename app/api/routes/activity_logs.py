from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any # Thêm List, Dict, Any
from app.core.db import PostgresCompatClient as Client

from app.core.db import get_db_client # PostgreSQL DB dependency
from app.core.auth import get_current_user

router = APIRouter()

class ActivityLogCreate(BaseModel):
    action: Literal['ADD', 'DELETE', 'SELECT', 'UNSELECT', 'IMPORT'] # Thêm IMPORT nếu cần
    provider_name: str
    key_id: Optional[str] = None
    description: str

# Bỏ hàm helper _insert_log_sync vì không cần nữa

@router.post("/", status_code=status.HTTP_201_CREATED)
# Chuyển thành hàm đồng bộ (def)
def create_activity_log(
    log_data: ActivityLogCreate,
    supabase: Client = Depends(get_db_client),
    user_id: str = Depends(get_current_user) # Nhận trực tiếp user_id (string) từ dependency
):
    """
    Creates a new activity log entry associated with the current user.
    (FastAPI runs this 'def' handler in a threadpool automatically)
    """
    try:
        # user_id đã được inject trực tiếp và xác thực bởi get_current_user
        # Không cần kiểm tra lại ở đây nếu get_current_user xử lý lỗi đúng cách

        insert_data = {
            "user_id": user_id, # Sử dụng user_id trực tiếp
            "action": log_data.action,
            "provider_name": log_data.provider_name,
            "key_id": log_data.key_id,
            "description": log_data.description,
        }

        # Gọi trực tiếp lệnh Supabase đồng bộ
        # FastAPI sẽ tự động chạy hàm 'def' này trong threadpool
        response = supabase.table("provider_key_logs").insert(insert_data).execute()

        if response.data:
            return response.data[0] # Trả về log đã tạo
        else:
            # Xử lý trường hợp không có data trả về hoặc có lỗi ngầm
            print(f"Supabase insert response error or no data: {response}") # Log lỗi chi tiết ở backend
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create activity log in database")

    except HTTPException as http_exc:
        # Re-raise HTTPException để FastAPI xử lý
        raise http_exc
    except Exception as e:
        print(f"Error creating activity log: {e}") # Log lỗi chi tiết ở backend
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")

# Endpoint để lấy activity logs
@router.get("/", response_model=List[Dict[str, Any]]) # Sử dụng List[Dict] vì model log chưa được định nghĩa ở đây
def get_activity_logs(
    limit: int = 50, # Thêm limit làm query parameter
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_db_client)
):
    """
    Retrieves the most recent activity logs for the authenticated user.
    """
    try:
        response = supabase.table("provider_key_logs").select(
            "*"
        ).eq(
            "user_id", user_id
        ).order(
            "created_at", desc=True # Sắp xếp mới nhất trước
        ).limit(limit).execute()

        if response.data:
            return response.data
        else:
            # Có thể trả về [] nếu không có lỗi nhưng không có data
            print(f"Supabase select response error or no data for logs: {response}")
            # Kiểm tra xem có lỗi cụ thể không
            # if hasattr(response, 'error') and response.error:
            #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch logs: {response.error.message}")
            return [] # Trả về danh sách rỗng nếu không có log

    except Exception as e:
        print(f"Error fetching activity logs: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch activity logs")