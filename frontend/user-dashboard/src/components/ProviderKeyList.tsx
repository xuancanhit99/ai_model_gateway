import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next'; // Import useTranslation
import { supabase } from '../supabaseClient';
import toast from 'react-hot-toast'; // Import toast
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

// Interface cho log
interface ProviderKeyLog {
  id: string;
  user_id: string;
  action: 'ADD' | 'DELETE' | 'SELECT' | 'UNSELECT';
  provider_name: string;
  key_id: string | null;
  description: string;
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
  const [logs, setLogs] = useState<ProviderKeyLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(true);
  // const [successMessage, setSuccessMessage] = useState<string | null>(null); // Remove success message state
 
  const fetchProviderKeys = async () => {
    try {
      setLoading(true);
      setError(null); // Reset error before fetch
      
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

  // Hàm để lấy nhật ký thay đổi Provider Keys
  const fetchProviderKeyLogs = async () => {
    try {
      setLoadingLogs(true);
      
      if (!supabase) {
        throw new Error(t('authError', 'Supabase client not initialized'));
      }
      
      const { data, error } = await supabase
        .from('provider_key_logs')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(50);
      
      if (error) throw error;
      
      setLogs(data || []);
    } catch (error: any) {
      console.error('Error fetching provider key logs:', error);
      // Không hiển thị lỗi này trên UI để tránh làm rối giao diện
    } finally {
      setLoadingLogs(false);
    }
  };

  // Hàm ghi log khi có thay đổi
  const addProviderKeyLog = async (action: 'ADD' | 'DELETE' | 'SELECT' | 'UNSELECT', providerName: string, keyId: string | null = null, description: string = '') => {
    try {
      if (!supabase) {
        throw new Error('Supabase client not initialized');
      }
      
      const { error } = await supabase
        .from('provider_key_logs')
        .insert({
          action,
          provider_name: providerName,
          key_id: keyId,
          description: description || `${action} key for ${providerDisplayNames[providerName] || providerName}`
        });
        
      if (error) throw error;
      
      // Cập nhật logs
      fetchProviderKeyLogs();
    } catch (error: any) {
      console.error('Error adding log:', error);
    }
  };

  useEffect(() => {
    fetchProviderKeys();
    fetchProviderKeyLogs(); // Fetch logs when component mounts
  }, []);

  const handleSelectKey = async (keyId: string, providerName: string, currentIsSelected: boolean) => {
    try {
      // setError(null); // Errors handled by toast now
      
      if (!supabase) {
        // Use translation for error
        throw new Error(t('authError', 'Supabase client not initialized'));
      }

      let newIsSelectedValue = !currentIsSelected;
      let successMsg = '';
      let logAction: 'SELECT' | 'UNSELECT' = newIsSelectedValue ? 'SELECT' : 'UNSELECT';

      if (newIsSelectedValue) {
        // If selecting a new key, first unselect all keys for this provider
        await supabase
          .from('user_provider_keys')
          .update({ is_selected: false })
          .eq('provider_name', providerName);
        
        // Use translation for success message
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
      
      toast.success(successMsg); // Show success toast
      
      // Ghi nhật ký
      await addProviderKeyLog(
        logAction, 
        providerName, 
        keyId, 
        logAction === 'SELECT' ? 
          `Selected as default key for ${providerDisplayNames[providerName] || providerName}` : 
          `Unselected as default key for ${providerDisplayNames[providerName] || providerName}`
      );
      
      // Refresh the list
      fetchProviderKeys();
    } catch (error: any) {
      console.error('Error updating provider key selection:', error);
      // Use translation for error toast
      toast.error(`${t('providerList.updateSelectionError', 'Error updating selection:')} ${error.message}`);
    }
  };

  const handleDeleteKey = async (keyId: string, providerName: string) => {
    // Use translation for confirmation dialog
    const confirmMessage = t('providerList.deleteConfirm', { provider: providerDisplayNames[providerName] || providerName });
    if (!window.confirm(confirmMessage)) {
      return;
    }
    
    try {
      // setError(null); // Errors handled by toast now
      
      if (!supabase) {
        // Use translation for error
        throw new Error(t('authError', 'Supabase client not initialized'));
      }
      
      // Lấy thêm thông tin khóa trước khi xóa để ghi log
      const { data: keyData } = await supabase
        .from('user_provider_keys')
        .select('name, is_selected')
        .eq('id', keyId)
        .single();
        
      const { error } = await supabase
        .from('user_provider_keys')
        .delete()
        .eq('id', keyId);
      
      if (error) throw error;
      
      // Use translation for success toast
      toast.success(t('providerList.deleteSuccess', { provider: providerDisplayNames[providerName] || providerName }));
      
      // Ghi nhật ký
      await addProviderKeyLog(
        'DELETE',
        providerName,
        keyId,
        `Deleted ${keyData?.is_selected ? 'default ' : ''}key for ${providerDisplayNames[providerName] || providerName}${keyData?.name ? ` (${keyData.name})` : ''}`
      );
      
      // Refresh the list
      fetchProviderKeys();
    } catch (error: any) {
      console.error('Error deleting provider key:', error);
      // Use translation for error toast
      toast.error(`${t('providerList.deleteError', 'Error deleting key:')} ${error.message}`);
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
      
      {/* Display initial fetch error if it occurred before rendering the list */}
      {error && !loading && providerKeys.length === 0 && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {/* Success and other error messages are now handled by react-hot-toast */}
      
      {/* Layout hai cột: danh sách khóa bên trái và nhật ký bên phải */}
      <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', md: 'row' } }}>
        {/* Cột trái: Danh sách Provider Keys */}
        <Box sx={{ flex: '2', minWidth: 0 }}>
          {providerKeys.length === 0 && !loading && !error ? ( // Show 'no keys' only if not loading and no initial error
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

        {/* Cột phải: Nhật ký thay đổi */}
        <Box sx={{ flex: '1', minWidth: 250 }}>
          <Typography variant="h6" gutterBottom>
            {t('providerLogs.title', 'Activity Log')}
          </Typography>
          <ProviderKeyLogs logs={logs} loading={loadingLogs} />
        </Box>
      </Box>

      {/* Phần About Provider API Keys */}
      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t('providerView.aboutTitle')}
        </Typography>
        <Typography variant="body2" paragraph>
          {t('providerView.aboutIntro')}
        </Typography>
        <Typography variant="body2" paragraph>
          {t('providerView.aboutBenefitsTitle')}
        </Typography>
        <Box component="ul" sx={{ mt: 0, pl: 2 }}>
          <Typography component="li" variant="body2">
            {t('providerView.aboutBenefit1')}
          </Typography>
          <Typography component="li" variant="body2">
            {t('providerView.aboutBenefit2')}
          </Typography>
          <Typography component="li" variant="body2">
            {t('providerView.aboutBenefit3')}
          </Typography>
        </Box>
        <Typography variant="body2" paragraph sx={{ mt: 1 }}>
          {t('providerView.aboutSecurity')}
        </Typography>
      </Paper>
    </Box>
  );
};

// Component hiển thị nhật ký thay đổi Provider Keys
export const ProviderKeyLogs: React.FC<{ logs: ProviderKeyLog[], loading: boolean }> = ({ logs, loading }) => {
  const { t } = useTranslation();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" my={2}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  // Hiển thị danh sách trống
  if (logs.length === 0) {
    return (
      <Alert severity="info" sx={{ mt: 2 }}>
        {t('providerLogs.noLogs', 'No activity logs available.')}
      </Alert>
    );
  }

  return (
    <Box>
      <TableContainer component={Paper} sx={{ maxHeight: 400, overflow: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{t('providerLogs.action', 'Action')}</TableCell>
              <TableCell>{t('providerLogs.provider', 'Provider')}</TableCell>
              <TableCell>{t('providerLogs.time', 'Time')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {logs.map((log) => (
              <TableRow key={log.id}>
                <TableCell>
                  <Chip 
                    label={t(`providerLogs.actions.${log.action.toLowerCase()}`, log.action)}
                    color={
                      log.action === 'ADD' ? 'success' :
                      log.action === 'DELETE' ? 'error' :
                      log.action === 'SELECT' ? 'primary' : 
                      'default'
                    }
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  {providerDisplayNames[log.provider_name] || log.provider_name}
                </TableCell>
                <TableCell>
                  {new Date(log.created_at).toLocaleString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default ProviderKeyList;