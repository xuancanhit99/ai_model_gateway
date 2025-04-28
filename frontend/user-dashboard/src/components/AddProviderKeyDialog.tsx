import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { supabase } from '../supabaseClient';
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
  const addProviderKeyLog = async (responseData: any) => {
    try {
      if (!supabase || !responseData.id || !responseData.provider_name) {
        console.error('Cannot log provider key action: Missing data', responseData);
        return;
      }
      
      // Ghi nhật ký vào bảng provider_key_logs
      const { error } = await supabase
        .from('provider_key_logs')
        .insert({
          action: 'ADD',
          provider_name: responseData.provider_name,
          key_id: responseData.id,
          description: `Added new ${name ? `"${name}" ` : ''}key for ${providerDisplayName}`
        });
        
      if (error) {
        console.error('Error adding provider key log:', error);
      }
    } catch (error: any) {
      console.error('Error in addProviderKeyLog:', error);
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
      // Check if supabase is initialized
      if (!supabase) {
        throw new Error('Supabase client not initialized');
      }
      
      // Lấy token access của session hiện tại
      const sessionResult = await supabase.auth.getSession();
      const accessToken = sessionResult.data.session?.access_token;
      
      if (!accessToken) {
        throw new Error(t('providerCreateForm.notAuthenticated', 'Not authenticated. Please sign in again.'));
      }
      
      // Thử gửi yêu cầu qua XMLHttpRequest để xử lý sâu hơn các vấn đề mixed content
      await new Promise<{id?: string, provider_name?: string}>(async (resolve, reject) => {
        const xhr = new XMLHttpRequest();
        
        // Đảm bảo URL là HTTPS bằng cách sử dụng origin hiện tại và thêm dấu / ở cuối
        const apiUrl = `${window.location.origin}/api/v1/provider-keys/`;
        
        // Sử dụng withCredentials để đảm bảo cookies và auth headers được gửi
        xhr.open('POST', apiUrl, true);
        xhr.withCredentials = true; // Đảm bảo cookies được gửi trong CORS requests
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`);
        
        xhr.onload = function() {
          if (xhr.status >= 200 && xhr.status < 300) {
            console.log('XHR Success:', xhr.status, xhr.statusText);
            
            // Parse response to get key ID for logging
            let responseData = {};
            try {
              responseData = JSON.parse(xhr.responseText) || {};
            } catch (e) {
              console.error('Error parsing response:', e);
            }
            
            // Reset form và thông báo thành công
            setApiKey('');
            setName('');
            toast.success(t('providerCreateForm.keyAddedSuccess', 'API key added successfully')); 
            
            // Ghi nhật ký khi thêm key thành công
            addProviderKeyLog(responseData);
            
            // Call onSuccess if provided
            if (onSuccess) {
              onSuccess();
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
        
        xhr.onerror = function() {
          console.error('XHR Network Error');
          // Use translation for error toast
          const networkErrorMsg = t('providerCreateForm.networkError', 'Network error occurred. Please check your connection.');
          toast.error(networkErrorMsg);
          reject(new Error(networkErrorMsg));
        };
        
        xhr.onabort = function() {
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