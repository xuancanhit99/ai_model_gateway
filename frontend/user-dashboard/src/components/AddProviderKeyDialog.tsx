import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getAccessToken } from '../authHelper';
import toast from 'react-hot-toast';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  CircularProgress
} from '@mui/material';

// Định nghĩa kiểu dữ liệu cho response từ API tạo key
interface ProviderKeyApiResponse {
  id?: string;
  provider_name?: string;
  // Thêm các trường khác nếu API trả về
}

interface AddProviderKeyDialogProps {
  open: boolean;
  providerName: string;
  providerDisplayName: string;
  onClose: () => void;
  onSuccess: () => void;
}

const AddProviderKeyDialog: React.FC<AddProviderKeyDialogProps> = ({
  open,
  providerName,
  providerDisplayName,
  onClose,
  onSuccess
}) => {
  const { t } = useTranslation();
  const [apiKey, setApiKey] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);

  const handleClose = () => {
    if (!loading) {
      setApiKey('');
      setName('');
      onClose();
    }
  };

  // Hàm ghi nhật ký khi thêm mới Provider Key
  const addProviderKeyLog = async (action: 'ADD', providerNameLog: string, keyIdLog: string | null, descriptionLog: string) => {
    try {
      const token = await getAccessToken();

      const logPayload = {
        action,
        provider_name: providerNameLog,
        key_id: keyIdLog,
        description: descriptionLog
      };

      // Gọi API backend để ghi log
      const logResponse = await fetch('/api/v1/activity-logs/', { // Sử dụng đường dẫn tương đối
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(logPayload)
      });

      if (!logResponse.ok) {
        // Log lỗi nhưng không làm gián đoạn luồng chính
        const errorData = await logResponse.json().catch(() => ({ detail: 'Unknown logging error' }));
        console.error(`Failed to log activity via API (${logResponse.status}): ${errorData.detail}`);
      } else {
        console.log("Activity logged successfully via API.");
        // Không cần fetchProviderKeyLogs() ở đây vì dialog này không hiển thị log trực tiếp
      }

    } catch (err: any) {
      console.error('Error adding activity log via API:', err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!apiKey) {
      toast.error(t('providerCreateForm.apiKeyRequired', 'API Key is required'));
      return;
    }

    setLoading(true);

    try {
      const accessToken = await getAccessToken();
      // Thử gửi yêu cầu qua XMLHttpRequest để xử lý sâu hơn các vấn đề mixed content
      // Sử dụng kiểu ProviderKeyApiResponse cho Promise
      await new Promise<ProviderKeyApiResponse>(async (resolve, reject) => {
        const xhr = new XMLHttpRequest();


        // Đảm bảo URL là HTTPS bằng cách sử dụng origin hiện tại và thêm dấu / ở cuối
        const apiUrl = `${window.location.origin}/api/v1/provider-keys/`;

        // Sử dụng withCredentials để đảm bảo cookies và auth headers được gửi
        xhr.open('POST', apiUrl, true);
        xhr.withCredentials = true; // Đảm bảo cookies được gửi trong CORS requests
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`);

        // Chuyển thành async function để có thể await
        xhr.onload = async function () {
          if (xhr.status >= 200 && xhr.status < 300) {
            console.log('XHR Success:', xhr.status, xhr.statusText);
            // Parse response và ép kiểu an toàn
            let responseData: ProviderKeyApiResponse = {}; // Khởi tạo với kiểu rõ ràng
            try {
              const parsed = JSON.parse(xhr.responseText);
              // Kiểm tra xem parsed có phải object không trước khi gán
              if (typeof parsed === 'object' && parsed !== null) {
                responseData = parsed as ProviderKeyApiResponse;
              } else {
                console.error('Parsed response is not an object:', parsed);
              }
            } catch (e) {
              console.error('Error parsing response:', e);
              // responseData vẫn là {} nếu parse lỗi
            }


            // Reset form và thông báo thành công
            setApiKey('');
            setName('');
            toast.success(t('providerCreateForm.keyAddedSuccess', 'API key added successfully'));
            // Ghi nhật ký khi thêm key thành công qua API và chờ hoàn tất
            const keyIdForLog = responseData?.id || null;
            const providerNameForLog = responseData?.provider_name || providerName; // Fallback nếu response không có
            const descriptionForLog = `Added new ${name ? `"${name}" ` : ''}key for ${providerDisplayName}`;
            try {
              // Await lời gọi ghi log
              await addProviderKeyLog('ADD', providerNameForLog, keyIdForLog, descriptionForLog);
            } catch (logError) {
              console.error("Logging failed, but proceeding:", logError);
              // Có thể bỏ qua lỗi log hoặc hiển thị thông báo phụ
            }

            // Call onSuccess CHỈ SAU KHI ghi log đã được thử (await)
            if (onSuccess) {
              onSuccess(); // Sẽ trigger fetchProviderKeys và fetchProviderKeyLogs trong parent
            }


            // Đóng dialog
            handleClose();

            resolve(responseData);
          } else {
            console.error('XHR Error:', xhr.status, xhr.statusText, xhr.responseText);
            let errorMessage = `Failed with status: ${xhr.status}`;

            try {
              const errorData = JSON.parse(xhr.responseText);
              errorMessage = errorData.detail || errorData.message || errorMessage;
            } catch (e) {
              // Ignore parse error
            }
            // Use toast.error instead of rejecting with Error for UI feedback
            toast.error(t('providerCreateForm.httpError', 'Error: {{message}}', { message: errorMessage }));
            // Still reject the promise for internal handling if needed, but UI error is shown via toast
            reject(new Error(errorMessage));
          }
        };

        xhr.onerror = function () {
          console.error('XHR Network Error');
          // Use translation for error toast
          const networkErrorMsg = t('providerCreateForm.networkError', 'Network error occurred. Please check your connection.');
          toast.error(networkErrorMsg);
          reject(new Error(networkErrorMsg));
        };

        xhr.onabort = function () {
          console.error('XHR Aborted');
          // Use translation for error toast
          const abortErrorMsg = t('providerCreateForm.requestAborted', 'Request was aborted.');
          toast.error(abortErrorMsg);
          reject(new Error(abortErrorMsg));
        };

        const data = JSON.stringify({
          provider_name: providerName,
          api_key: apiKey,
          name: name || null
        });

        xhr.send(data);
      });

    } catch (error: any) {
      console.error('Error creating provider key:', error);
      // Use translation for error toast, include original error if possible
      const defaultError = t('providerCreateForm.createFailed', 'Failed to create provider key');
      toast.error(`${t('providerCreateForm.keyAddedError', 'Error adding key:')} ${error.message || defaultError}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle>
        {t('providerCreateForm.addKeyForProvider', 'Add API Key for {{provider}}', {
          provider: providerDisplayName
        })}
      </DialogTitle>
      <Box component="form" onSubmit={handleSubmit}>
        <DialogContent>
          <TextField
            fullWidth
            label={t('providerCreateForm.apiKeyLabel', 'API Key')}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            margin="normal"
            required
            type="password"
            autoFocus
            helperText={t('providerCreateForm.apiKeyHelper', 'Your API key will be encrypted before storage')}
          />

          <TextField
            fullWidth
            label={t('providerCreateForm.descriptionLabel', 'Description (Optional)')}
            value={name}
            onChange={(e) => setName(e.target.value)}
            margin="normal"
            helperText={t('providerCreateForm.descriptionHelper', 'Add a friendly name to help identify this key')}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={loading}>
            {t('action.cancel', 'Cancel')}
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={loading}
          >
            {loading ? (
              <>
                <CircularProgress size={24} sx={{ mr: 1 }} />
                {t('providerCreateForm.addingButton', 'Adding...')}
              </>
            ) : (
              t('providerCreateForm.submitButton', 'Add Key')
            )}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
};

export default AddProviderKeyDialog;