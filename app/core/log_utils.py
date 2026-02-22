# app/core/log_utils.py
import logging
from typing import Optional
from app.core.db import PostgresCompatClient as Client # Import Supabase Client
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Sử dụng AsyncClient để thực hiện request bất đồng bộ
# Khởi tạo client một lần để tái sử dụng kết nối (tốt hơn cho hiệu năng)
# Tuy nhiên, trong môi trường serverless hoặc nhiều worker, quản lý client phức tạp hơn.
# Cách đơn giản là tạo client mỗi lần gọi, nhưng kém hiệu quả hơn.
# Ở đây, chúng ta sẽ tạo client mỗi lần gọi cho đơn giản.

# Sửa lại hàm để ghi trực tiếp vào DB
async def log_activity_db( # Đổi tên hàm để rõ ràng hơn
    user_id: str,
    provider_name: str,
    action: str,
    supabase: Client, # Nhận Supabase client làm tham số (Đưa lên trước)
    # Sử dụng lại tên description
    description: Optional[str] = None, # Đổi lại thành description
    key_id: Optional[str] = None,
):
    """
    Ghi trực tiếp một bản ghi activity log vào database Supabase.

    Args:
        user_id: ID của người dùng.
        provider_name: Tên nhà cung cấp liên quan.
        action: Loại hành động (ADD, DELETE, SELECT, UNSELECT, FAILOVER_EXHAUSTED, RETRY_FAILED, ERROR).
        description: Mô tả chi tiết về hành động hoặc thông báo lỗi.
        supabase: Supabase client instance (sử dụng service_role key).
        key_id: ID của provider key liên quan (tùy chọn).
    """
    insert_data = {
        "user_id": user_id,
        "provider_name": provider_name,
        "action": action,
        "description": description, # Sử dụng lại description
        "key_id": str(key_id) if key_id else None, # Đảm bảo key_id là string nếu có
    }

    try:
        # Sử dụng client Supabase được truyền vào để ghi log
        # Xóa await vì insert là đồng bộ trong thư viện hiện tại
        response = supabase.table("provider_key_logs").insert(insert_data).execute()

        # Kiểm tra kết quả insert kỹ hơn
        # Giả định: Nếu có lỗi từ PostgREST, nó có thể nằm trong response.error hoặc response không có data
        log_successful = False
        error_details = None
        if hasattr(response, 'error') and response.error:
            error_details = response.error
            logger.error(f"Error returned from Supabase during activity logging: {error_details}")
        elif hasattr(response, 'data') and response.data:
             # Giả sử insert thành công nếu có data trả về (thường là list các record đã insert)
             log_successful = True
             logger.info(f"Activity logged successfully to DB for user {user_id}, action {action}")
        else:
            # Trường hợp không có lỗi rõ ràng nhưng cũng không có data (có thể là lỗi ngầm hoặc cấu hình)
             error_details = "No data returned and no explicit error from Supabase."
             logger.warning(f"Potential issue logging activity: {error_details} Response: {response}")
 
        if not log_successful:
             # Log chi tiết hơn khi thất bại
             logger.error(
                 f"Failed to log activity to DB. User: {user_id}, Action: {action}. "
                 f"Attempted data: {insert_data}. Error: {error_details}. Response: {response}"
             )

    except Exception as e:
        # Log chi tiết hơn khi có exception
        logger.exception(
            f"Unexpected error during direct DB activity logging for user {user_id}. "
            f"Attempted data: {insert_data}. Error: {e}"
        )
        # Không ném lỗi ra ngoài để tránh làm gián đoạn luồng chính.