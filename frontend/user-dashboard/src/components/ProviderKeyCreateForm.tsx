import React, { useState } from 'react';
import { useTranslation } from 'react-i18next'; // Import useTranslation
import { supabase } from '../supabaseClient';
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
  Alert,
  Paper,
  SelectChangeEvent
} from '@mui/material';

interface ProviderKeyCreateFormProps {
  onSuccess?: () => void;
}

const ProviderKeyCreateForm: React.FC<ProviderKeyCreateFormProps> = ({ onSuccess }) => {
  const { t } = useTranslation(); // Use the hook
  const [provider, setProvider] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleProviderChange = (event: SelectChangeEvent<string>) => {
    setProvider(event.target.value);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!provider || !apiKey) {
      // Use translation for error message
      setError(t('providerCreateForm.providerAndApiKeyRequired', 'Provider and API Key are required'));
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccess(false);
    
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
      return new Promise<void>((resolve, reject) => {
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
            
            // Reset form và thông báo thành công
            setProvider('');
            setApiKey('');
            setName('');
            setSuccess(true);
            
            // Call onSuccess if provided
            if (onSuccess) {
              onSuccess();
            }
            
            // Clear success message after a delay
            setTimeout(() => setSuccess(false), 5000);
            
            resolve();
          } else {
            console.error('XHR Error:', xhr.status, xhr.statusText, xhr.responseText);
            let errorMessage = `Failed with status: ${xhr.status}`;
            
            try {
              const errorData = JSON.parse(xhr.responseText);
              errorMessage = errorData.detail || errorData.message || errorMessage;
            } catch (e) {
              // Ignore parse error
            }
            
            reject(new Error(errorMessage));
          }
        };
        
        xhr.onerror = function() {
          console.error('XHR Network Error');
          // Use translation for error message
          reject(new Error(t('providerCreateForm.networkError', 'Network error occurred. Please check your connection.')));
        };
        
        xhr.onabort = function() {
          console.error('XHR Aborted');
          // Use translation for error message
          reject(new Error(t('providerCreateForm.requestAborted', 'Request was aborted.')));
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
      // Use translation for error message, include original error if possible
      const defaultError = t('providerCreateForm.createFailed', 'Failed to create provider key');
      setError(`${t('providerCreateForm.keyAddedError')} ${error.message || defaultError}`);
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
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {t('providerCreateForm.keyAddedSuccess')} {/* Use translation */}
        </Alert>
      )}
      
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