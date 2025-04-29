# app/core/failover_utils.py
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from supabase import Client
from cryptography.fernet import Fernet # Cần để giải mã key mới
import base64

# Giả sử hàm get_encryption_key được chuyển hoặc import từ auth
# Tốt hơn là chuyển nó vào một module utils chung nếu chưa có
from app.core.auth import get_encryption_key
from app.core.log_utils import log_activity_db # Đã đúng

logger = logging.getLogger(__name__)

# Hằng số thời gian vô hiệu hóa (5 phút)
DISABLE_DURATION_MINUTES = 5

async def attempt_automatic_failover(
    user_id: str,
    provider_name: str,
    failed_key_id: str,
    error_code: int,
    error_message: str,
    supabase: Client,
    # Đảm bảo đã bỏ auth_token khỏi signature
) -> Optional[Dict[str, Any]]: # Trả về dict chứa id và api_key mới, hoặc None
    """
    Thực hiện logic tự động chuyển đổi API key khi key hiện tại lỗi.

    Args:
        user_id: ID người dùng.
        provider_name: Tên nhà cung cấp (google, xai, etc.).
        failed_key_id: ID của key vừa gây lỗi.
        error_code: Mã lỗi HTTP (ví dụ: 401, 429).
        error_message: Thông báo lỗi từ nhà cung cấp.
        supabase: Supabase client instance.
        # Bỏ dòng mô tả auth_token

    Returns:
        Một dictionary chứa 'id' và 'api_key' của key mới được chọn,
        hoặc None nếu không tìm thấy key thay thế hợp lệ.
    """
    logger.warning(
        f"Failover triggered: user={user_id}, provider={provider_name}, "
        f"failed_key_id={failed_key_id}, error={error_code} - {error_message}"
    )

    # Lấy tên của key bị lỗi để ghi log chi tiết hơn
    failed_key_name = str(failed_key_id) # Giá trị mặc định nếu không tìm thấy tên
    try:
        # Xóa await ở đây
        failed_key_res = supabase.table("user_provider_keys").select("name").eq("id", failed_key_id).maybe_single().execute()
        # Dòng log gỡ lỗi 1 đã bị xóa
        if hasattr(failed_key_res, 'data') and failed_key_res.data and failed_key_res.data.get("name"):
            failed_key_name = failed_key_res.data["name"] or failed_key_name # Sử dụng tên nếu có, nếu không giữ lại ID
    except Exception as e:
        logger.warning(f"Could not fetch name for failed key {failed_key_id}: {e}")

    # 1. Xử lý lỗi 429: Vô hiệu hóa key tạm thời
    if error_code == 429:
        try:
            disable_time = datetime.now(timezone.utc) + timedelta(minutes=DISABLE_DURATION_MINUTES)
            # Sử dụng await cho các hoạt động I/O với Supabase
            update_res = await supabase.table("user_provider_keys").update(
                {"disabled_until": disable_time.isoformat()}
            ).eq("id", failed_key_id).execute()
            # Kiểm tra kết quả trả về từ Supabase (có thể khác nhau tùy phiên bản client)
            # Giả sử .data chứa danh sách các bản ghi được cập nhật
            if not hasattr(update_res, 'data') or not update_res.data:
                 logger.error(f"Failed to update disabled_until for key {failed_key_id}. Response: {update_res}")
            else:
                 logger.info(f"Key {failed_key_id} temporarily disabled until {disable_time}")
        except Exception as e:
            logger.exception(f"Error updating disabled_until for key {failed_key_id}: {e}")
            # Tiếp tục thử tìm key khác dù không cập nhật được disabled_until

    # 2. Tìm key thay thế hợp lệ
    next_key_info: Optional[Dict[str, Any]] = None
    try:
        # Lấy TẤT CẢ các key của provider này để xác định thứ tự quay vòng
        # Xóa await ở đây
        all_keys_res = supabase.table("user_provider_keys").select("id, created_at") \
            .eq("user_id", user_id) \
            .eq("provider_name", provider_name) \
            .order("created_at", desc=False) \
            .execute()

        if not hasattr(all_keys_res, 'data') or not all_keys_res.data:
            logger.error(f"No keys found for provider {provider_name} for user {user_id} during failover.")
            return None

        all_key_ids = [str(k['id']) for k in all_keys_res.data] # Đảm bảo ID là string
        try:
            # Đảm bảo failed_key_id cũng là string để so sánh
            failed_key_index = all_key_ids.index(str(failed_key_id))
        except ValueError:
            logger.error(f"Failed key {failed_key_id} not found in user's keys for provider {provider_name}.")
            return None

        # Lấy các key KHẢ DỤNG (không bị khóa)
        # Sử dụng RPC hoặc lọc phía client nếu lọc IS NULL OR <= NOW() phức tạp
        # Cách đơn giản: Lọc IS NULL
        # Xóa await ở đây
        available_keys_res = supabase.table("user_provider_keys") \
            .select("id, api_key_encrypted, created_at") \
            .eq("user_id", user_id) \
            .eq("provider_name", provider_name) \
            .is_("disabled_until", "null") \
            .order("created_at", desc=False) \
            .execute()

        available_keys = available_keys_res.data if hasattr(available_keys_res, 'data') else []

        # Lọc thêm các key có disabled_until <= NOW() trong Python nếu cần
        now_utc = datetime.now(timezone.utc)
        truly_available_keys = [
            k for k in available_keys
            # Bỏ qua kiểm tra disabled_until nếu đã lọc bằng .is_("disabled_until", "null")
            # Nếu muốn lọc cả <= NOW(), cần lấy tất cả key và lọc ở đây:
            # if k.get('disabled_until') is None or datetime.fromisoformat(k['disabled_until'].replace('Z', '+00:00')) <= now_utc
        ]


        if not truly_available_keys or (len(truly_available_keys) == 1 and str(truly_available_keys[0]['id']) == str(failed_key_id)):
             logger.warning(f"No available keys found for failover: user={user_id}, provider={provider_name}")
             # Gọi log_activity_db và truyền supabase
             # Đã đúng: gọi log_activity_db và truyền supabase
             await log_activity_db(
                 user_id=user_id, provider_name=provider_name, key_id=failed_key_id, action="FAILOVER_EXHAUSTED",
                 supabase=supabase, description=f"No available keys to switch to after error {error_code} on key {failed_key_id}"
             )
             return None

        # Sắp xếp key khả dụng theo created_at để nhất quán với all_key_ids
        truly_available_keys.sort(key=lambda k: k['created_at'])
        available_key_ids_map = {str(k['id']): k for k in truly_available_keys} # Map để truy cập nhanh

        # Tìm key tiếp theo trong danh sách TẤT CẢ key, bắt đầu từ sau key lỗi (quay vòng)
        num_keys = len(all_key_ids)
        found_next_key_data = None
        for i in range(1, num_keys + 1):
            next_index = (failed_key_index + i) % num_keys
            candidate_key_id = all_key_ids[next_index]

            # Kiểm tra xem candidate có trong danh sách khả dụng không
            if candidate_key_id in available_key_ids_map:
                 found_next_key_data = available_key_ids_map[candidate_key_id]
                 break # Đã tìm thấy key thay thế hợp lệ

        if not found_next_key_data:
            logger.warning(f"Could not find a valid next key after checking all possibilities: user={user_id}, provider={provider_name}")
            # Gọi log_activity_db và truyền supabase
            # Đã đúng: gọi log_activity_db và truyền supabase
            await log_activity_db(
                user_id=user_id, provider_name=provider_name, key_id=failed_key_id, action="FAILOVER_EXHAUSTED",
                supabase=supabase, description=f"No valid alternative key found after error {error_code} on key {failed_key_id}"
            )
            return None
        
        next_key_info = found_next_key_data

    except Exception as e:
        logger.exception(f"Error finding replacement key for user {user_id}, provider {provider_name}: {e}")
        return None

    # 3. Giải mã key mới
    next_key_id = str(next_key_info['id']) # Đảm bảo là string
    encrypted_key = next_key_info['api_key_encrypted']
    try:
        encryption_fernet_key = base64.urlsafe_b64encode(get_encryption_key())
        f = Fernet(encryption_fernet_key)
        decrypted_next_key = f.decrypt(encrypted_key.encode()).decode()
    except Exception as e:
        logger.exception(f"Error decrypting replacement key {next_key_id}: {e}")
        # Sửa lại: Gọi log_activity_db và truyền supabase
        await log_activity_db(
            user_id=user_id, provider_name=provider_name, key_id=next_key_id, action="ERROR",
            supabase=supabase, description=f"Failed to decrypt key during failover. Manual intervention needed."
        )
        return None

    # 4. Cập nhật is_selected trong DB
    try:
        # Bỏ chọn key cũ
        # Gỡ bỏ await vì update().execute() là đồng bộ
        supabase.table("user_provider_keys").update({"is_selected": False}).eq("id", failed_key_id).execute()
        # Chọn key mới
        # Gỡ bỏ await vì update().execute() là đồng bộ
        supabase.table("user_provider_keys").update({"is_selected": True}).eq("id", next_key_id).execute()
        logger.info(f"Successfully switched selected key from {failed_key_id} to {next_key_id}")
    except Exception as e:
        logger.exception(f"Error updating is_selected flags during failover from {failed_key_id} to {next_key_id}: {e}")
        # Gọi log_activity_db và truyền supabase
        # Đã đúng: gọi log_activity_db và truyền supabase
        await log_activity_db(
            user_id=user_id, provider_name=provider_name, key_id=next_key_id, action="ERROR",
            supabase=supabase, description=f"DB update failed during failover to this key. State might be inconsistent."
        )
        # Vẫn trả về key mới để thử, hy vọng lần sau sẽ cập nhật được
        return {"id": next_key_id, "api_key": decrypted_next_key}

    # Lấy tên của key mới được chọn
    next_key_name = str(next_key_id) # Giá trị mặc định
    try:
        # Xóa await ở đây
        next_key_res = supabase.table("user_provider_keys").select("name").eq("id", next_key_id).maybe_single().execute()
        # Dòng log gỡ lỗi 2 đã bị xóa
        if hasattr(next_key_res, 'data') and next_key_res.data and next_key_res.data.get("name"):
            next_key_name = next_key_res.data["name"] or next_key_name # Sử dụng tên nếu có, nếu không giữ lại ID
    except Exception as e:
        logger.warning(f"Could not fetch name for next key {next_key_id}: {e}")

    # 5. Ghi Activity Log cho việc chuyển đổi (await là đúng vì log_activity_db là async)
    # Nối toàn bộ error_message vào description
    error_detail = f": {error_message}" if error_message else ""

    # Gọi log_activity_db và truyền supabase
    await log_activity_db(
        user_id=user_id, provider_name=provider_name, key_id=failed_key_id, action="UNSELECT",
        supabase=supabase, description=f"Key '{failed_key_name}' unselected due to error {error_code}{error_detail}" # Thêm toàn bộ error_message
    )
    await log_activity_db(
        user_id=user_id, provider_name=provider_name, key_id=next_key_id, action="SELECT",
        supabase=supabase, description=f"Selected key '{next_key_name}' by automatic failover from key '{failed_key_name}'"
    )

    # 6. Trả về thông tin key mới
    return {"id": next_key_id, "api_key": decrypted_next_key}