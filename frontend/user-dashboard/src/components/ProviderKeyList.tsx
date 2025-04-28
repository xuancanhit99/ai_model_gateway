import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next'; // Import useTranslation
import { supabase } from '../supabaseClient';
import {
  Box,
  IconButton, 
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Alert,
  CircularProgress,
  Chip
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckIcon from '@mui/icons-material/Check';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';

interface ProviderKey {
  id: string;
  provider_name: string;
  name: string | null;
  is_selected: boolean;
  created_at: string;
}

const providerDisplayNames: Record<string, string> = {
  'google': 'Google AI (Gemini)',
  'xai': 'X.AI (Grok)',
  'gigachat': 'GigaChat',
  'perplexity': 'Perplexity (Sonar)'
};

const ProviderKeyList: React.FC = () => {
  const { t } = useTranslation(); // Use the hook
  const [providerKeys, setProviderKeys] = useState<ProviderKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchProviderKeys = async () => {
    try {
      setLoading(true);
      setError(null);
      
      if (!supabase) {
        // Use translation for error
        throw new Error(t('authError', 'Supabase client not initialized'));
      }
      
      const { data, error } = await supabase
        .from('user_provider_keys')
        .select('*')
        .order('provider_name', { ascending: true })
        .order('created_at', { ascending: false });
      
      if (error) throw error;
      
      setProviderKeys(data || []);
    } catch (error: any) {
      console.error('Error fetching provider keys:', error);
      // Use translation for error
      setError(`${t('providerList.fetchError', 'Error fetching provider keys:')} ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProviderKeys();
  }, []);

  const handleSelectKey = async (keyId: string, providerName: string, currentIsSelected: boolean) => {
    try {
      setError(null);
      
      if (!supabase) {
        // Use translation for error
        throw new Error(t('authError', 'Supabase client not initialized'));
      }

      let newIsSelectedValue = !currentIsSelected;
      let successMsg = '';

      if (newIsSelectedValue) {
        // If selecting a new key, first unselect all keys for this provider
        await supabase
          .from('user_provider_keys')
          .update({ is_selected: false })
          .eq('provider_name', providerName);
        
        // Use translation for success message (consider adding specific keys later if needed)
        successMsg = t('providerList.selectSuccess', { provider: providerDisplayNames[providerName] || providerName });
      } else {
        // If unselecting the current key
        // Use translation for success message
        successMsg = t('providerList.unselectSuccess', { provider: providerDisplayNames[providerName] || providerName });
      }
      
      // Then update the clicked key
      const { error } = await supabase
        .from('user_provider_keys')
        .update({ is_selected: newIsSelectedValue })
        .eq('id', keyId);
      
      if (error) throw error;
      
      setSuccessMessage(successMsg);
      setTimeout(() => setSuccessMessage(null), 3000);
      
      // Refresh the list
      fetchProviderKeys();
    } catch (error: any) {
      console.error('Error updating provider key selection:', error);
      // Use translation for error
      setError(`${t('providerList.updateSelectionError', 'Error updating selection:')} ${error.message}`);
    }
  };

  const handleDeleteKey = async (keyId: string, providerName: string) => {
    // Use translation for confirmation dialog
    const confirmMessage = t('providerList.deleteConfirm', { provider: providerDisplayNames[providerName] || providerName });
    if (!window.confirm(confirmMessage)) {
      return;
    }
    
    try {
      setError(null);
      
      if (!supabase) {
        // Use translation for error
        throw new Error(t('authError', 'Supabase client not initialized'));
      }
      
      const { error } = await supabase
        .from('user_provider_keys')
        .delete()
        .eq('id', keyId);
      
      if (error) throw error;
      
      // Use translation for success message
      setSuccessMessage(t('providerList.deleteSuccess', { provider: providerDisplayNames[providerName] || providerName }));
      setTimeout(() => setSuccessMessage(null), 3000);
      
      // Refresh the list
      fetchProviderKeys();
    } catch (error: any) {
      console.error('Error deleting provider key:', error);
      // Use translation for error
      setError(`${t('providerList.deleteError', 'Error deleting key:')} ${error.message}`);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" my={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Use translation for title */}
      <Typography variant="h6" gutterBottom>
        {t('providerList.title')}
      </Typography>
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {successMessage && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {successMessage}
        </Alert>
      )}
      
      {providerKeys.length === 0 ? (
        <Alert severity="info">
          {t('providerView.noKeys')} {/* Use translation */}
        </Alert>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                {/* Use translation for table headers */}
                <TableCell>{t('providerList.headerProvider', 'Provider')}</TableCell>
                <TableCell>{t('providerList.headerDescription', 'Description')}</TableCell>
                <TableCell>{t('providerList.headerCreated', 'Created')}</TableCell>
                <TableCell align="center">{t('providerList.headerDefault', 'Default')}</TableCell>
                <TableCell align="right">{t('providerList.headerActions', 'Actions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {providerKeys.map((key) => (
                <TableRow key={key.id}>
                  <TableCell>
                    <Chip 
                      label={providerDisplayNames[key.provider_name] || key.provider_name} 
                      color={
                        key.provider_name === 'google' ? 'primary' :
                        key.provider_name === 'xai' ? 'secondary' :
                        key.provider_name === 'gigachat' ? 'success' :
                        key.provider_name === 'perplexity' ? 'warning' : 'default'
                      }
                      size="small"
                    />
                  </TableCell>
                  {/* Use translation for fallback description */}
                  <TableCell>{key.name || t('providerList.noDescription', 'No description')}</TableCell>
                  <TableCell>{new Date(key.created_at).toLocaleString()}</TableCell>
                  <TableCell align="center">
                    <IconButton 
                      size="small" 
                      onClick={() => handleSelectKey(key.id, key.provider_name, key.is_selected)}
                      color={key.is_selected ? "primary" : "default"}
                    >
                      {key.is_selected ? <CheckIcon /> : <RadioButtonUncheckedIcon />}
                    </IconButton>
                  </TableCell>
                  <TableCell align="right">
                    <IconButton 
                      size="small"
                      color="error"
                      onClick={() => handleDeleteKey(key.id, key.provider_name)}
                      aria-label={t('providerList.deleteButton')} // Add aria-label for accessibility
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
};

export default ProviderKeyList;