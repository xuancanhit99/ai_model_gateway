import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { supabase } from '../supabaseClient';
import toast from 'react-hot-toast';
import {
  Box,
  Button,
  FormControl,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
  // Alert, // Remove Alert import if no longer needed
  Paper,
  SelectChangeEvent
} from '@mui/material';

interface ProviderKeyCreateFormProps {
  onSuccess: () => void;
}

// Tên hiển thị cho các nhà cung cấp
const providerDisplayNames: Record<string, string> = {
  'google': 'Google AI (Gemini)',
  'xai': 'X.AI (Grok)',
  'gigachat': 'GigaChat',
  'perplexity': 'Perplexity (Sonar)'
};

const ProviderKeyCreateForm: React.FC<ProviderKeyCreateFormProps> = ({ onSuccess }) => {
  const { t } = useTranslation(); // Use the hook
  const [provider, setProvider] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  
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
          description: `Added new ${name ? `"${name}" ` : ''}key for ${providerDisplayNames[responseData.provider_name] || responseData.provider_name}`
        });
        
      if (error) {
        console.error('Error adding provider key log:', error);
      }
    } catch (error: any) {
      console.error('Error in addProviderKeyLog:', error);
    }
  };
  
  const handleProviderChange = (event: SelectChangeEvent<string>) => {
    setProvider(event.target.value);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!provider || !apiKey) {
      // Use translation for error toast
      toast.error(t('providerCreateForm.providerAndApiKeyRequired', 'Provider and API Key are required'));
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
        // Use translation for error message
        throw new Error(t('providerCreateForm.notAuthenticated', 'Not authenticated. Please sign in again.'));
      }
      
      // Thử gửi yêu cầu qua XMLHttpRequest để xử lý sâu hơn các vấn đề mixed content
      await new Promise<{id?: string, provider_name?: string}>(async (resolve, reject) => {
        const xhr = new XMLHttpRequest();
        
        // Đảm bảo URL là HTTPS bằng cách sử dụng origin hiện tại và thêm dấu / ở cuối
        const apiUrl = `${window.location.origin}/api/v1/provider-keys/`; // Thêm dấu / ở cuối
        console.log('Submitting to URL via XHR:', apiUrl);
        
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
            setProvider('');
            setApiKey('');
            setName('');
            toast.success(t('providerCreateForm.keyAddedSuccess')); // Show success toast
            
            // Ghi nhật ký khi thêm key thành công
            addProviderKeyLog(responseData);
            
            // Call onSuccess if provided
            if (onSuccess) {
              onSuccess();
            }
            
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
            toast.error(errorMessage);
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
          provider_name: provider,
          api_key: apiKey,
          name: name || null
        });
        
        xhr.send(data);
      });
      
    } catch (error: any) {
      console.error('Error creating provider key:', error);
      // Use translation for error toast, include original error if possible
      const defaultError = t('providerCreateForm.createFailed', 'Failed to create provider key');
      toast.error(`${t('providerCreateForm.keyAddedError')} ${error.message || defaultError}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      {/* Use translation for form title */}
      <Typography variant="h6" gutterBottom>
        {t('providerCreateForm.title')}
      </Typography>
      
      {/* Error and Success messages are now handled by react-hot-toast */}
      {/* {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )} */}
      {/* {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {t('providerCreateForm.keyAddedSuccess')}
        </Alert>
      )} */}
      
      <Box component="form" onSubmit={handleSubmit}>
        <FormControl fullWidth sx={{ mb: 2 }}>
          {/* Use translation for label */}
          <InputLabel id="provider-select-label">{t('providerCreateForm.providerLabel')}</InputLabel>
          <Select
            labelId="provider-select-label"
            value={provider}
            label={t('providerCreateForm.providerLabel')} // Use translation for label prop as well
            onChange={handleProviderChange}
            required
          >
            <MenuItem value="google">Google AI (Gemini)</MenuItem>
            <MenuItem value="xai">X.AI (Grok)</MenuItem>
            <MenuItem value="gigachat">GigaChat</MenuItem>
            <MenuItem value="perplexity">Perplexity (Sonar)</MenuItem>
          </Select>
          {/* Use translation for helper text */}
          <FormHelperText>{t('providerCreateForm.selectProviderHelper', 'Select the AI provider for this API key')}</FormHelperText>
        </FormControl>
        
        <TextField
          fullWidth
          label={t('providerCreateForm.apiKeyLabel')} // Use translation
          value={apiKey}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setApiKey(e.target.value)}
          margin="normal"
          required
          type="password"
          // Use translation for helper text
          helperText={t('providerCreateForm.apiKeyHelper', 'Your API key will be encrypted before storage')}
        />
        
        <TextField
          fullWidth
          label={t('providerCreateForm.descriptionLabel', 'Description (Optional)')} // Use translation
          value={name}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
          margin="normal"
          // Use translation for helper text
          helperText={t('providerCreateForm.descriptionHelper', 'Add a friendly name to help identify this key')}
        />
        
        <Button
          type="submit"
          variant="contained"
          color="primary"
          disabled={loading}
          sx={{ mt: 2 }}
        >
          {/* Use translation for button text */}
          {loading ? t('providerCreateForm.addingButton', 'Adding...') : t('providerCreateForm.submitButton')}
        </Button>
      </Box>
    </Paper>
  );
};

export default ProviderKeyCreateForm;