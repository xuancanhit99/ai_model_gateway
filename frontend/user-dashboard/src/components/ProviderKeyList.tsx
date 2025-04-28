import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { supabase } from '../supabaseClient';
import toast from 'react-hot-toast';
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
  Chip,
  TextField,
  InputAdornment,
  Button,
  Card,
  CardContent,
  Collapse,
  Divider,
  Badge,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle
} from '@mui/material';
import CancelIcon from '@mui/icons-material/Cancel';
import FolderDeleteIcon from '@mui/icons-material/FolderDelete';
import CheckIcon from '@mui/icons-material/Check';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import InfoIcon from '@mui/icons-material/Info';
import SearchIcon from '@mui/icons-material/Search';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';

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
  const [expandedProviders, setExpandedProviders] = useState<Record<string, boolean>>({});
  const [searchTerms, setSearchTerms] = useState<Record<string, string>>({});
  // Dialog states for confirmation
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);
  const [keyToDelete, setKeyToDelete] = useState<{id: string, providerName: string} | null>(null);
  const [providerToDeleteAll, setProviderToDeleteAll] = useState<string | null>(null);
  // const [successMessage, setSuccessMessage] = useState<string | null>(null); // Remove success message state
  // Refs cho các file inputs của từng provider
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  
  // State cho tracking import progress
  const [importing, setImporting] = useState<Record<string, boolean>>({});
  const [importStats, setImportStats] = useState<Record<string, { total: number, success: number, failed: number } | null>>({});
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [currentImportProvider, setCurrentImportProvider] = useState<string | null>(null);
  
  // Hàm xử lý khi click vào nút Import CSV
  const handleImportClick = (providerName: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Ngăn không cho event click lan đến parent
    
    // Kích hoạt click cho file input tương ứng
    if (fileInputRefs.current[providerName]) {
      fileInputRefs.current[providerName]?.click();
    }
  };
  
  // Hàm xử lý file CSV được chọn
  const handleCsvFileChange = async (providerName: string, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    try {
      // Đánh dấu đang import
      setImporting(prev => ({ ...prev, [providerName]: true }));
      setCurrentImportProvider(providerName);
      setImportDialogOpen(true);
      
      // Đọc file CSV
      const keys = await readCsvFile(file);
      if (keys.length === 0) {
        throw new Error(t('providerList.importError.noKeys', 'No keys found in CSV file'));
      }
      
      // Import các keys
      const stats = await importKeysToProvider(keys, providerName);
      
      // Cập nhật statistics
      setImportStats(prev => ({ ...prev, [providerName]: stats }));
      
      // Thông báo thành công
      toast.success(
        t('providerList.importSuccess', { 
          count: stats.success,
          provider: providerDisplayNames[providerName] || providerName 
        })
      );
      
      // Refresh danh sách keys
      fetchProviderKeys();
      
      // Ghi log
      await addProviderKeyLog(
        'ADD',
        providerName,
        null,
        `Imported ${stats.success} keys from CSV for ${providerDisplayNames[providerName] || providerName}`
      );
      
    } catch (error: any) {
      console.error('Error importing CSV:', error);
      toast.error(`${t('providerList.importError.general', 'Error importing CSV:')} ${error.message}`);
    } finally {
      // Reset file input
      if (e.target) {
        e.target.value = '';
      }
      
      // Đánh dấu kết thúc import
      setImporting(prev => ({ ...prev, [providerName]: false }));
    }
  };
  
  // Hàm đọc file CSV
  const readCsvFile = (file: File): Promise<{ description: string, key: string }[]> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (event) => {
        try {
          const content = event.target?.result as string;
          if (!content) {
            reject(new Error(t('providerList.importError.readError', 'Could not read file content')));
            return;
          }
          
          // Parse nội dung CSV
          const lines = content.split(/\r\n|\n/).filter(line => line.trim());
          const keys = lines.map(line => {
            // Xử lý các trường hợp phân tách: dấu phẩy (,), dấu chấm phẩy (;), tab (\t)
            const separator = line.includes(',') ? ',' : line.includes(';') ? ';' : '\t';
            const parts = line.split(separator);
            
            // Kiểm tra nếu chỉ có 2 phần và không có phần thứ 3
            if (parts.length === 2) {
              return {
                description: (parts[0] || '').trim(),
                key: (parts[1] || '').trim()
              };
            }
            
            // Nếu có nhiều hơn 2 phần, có thể là file CSV phức tạp hơn
            // Sẽ dùng phần đầu tiên làm description và phần thứ hai làm key
            return {
              description: (parts[0] || '').trim(),
              key: (parts[1] || '').trim()
            };
          }).filter(item => item.key && item.key.length > 0); // Chỉ giữ lại những item có key
          
          resolve(keys);
        } catch (error) {
          reject(error);
        }
      };
      
      reader.onerror = () => {
        reject(new Error(t('providerList.importError.readError', 'Error reading file')));
      };
      
      reader.readAsText(file);
    });
  };
  
  // Hàm import các keys vào provider
  const importKeysToProvider = async (
    keys: { description: string, key: string }[], 
    providerName: string
  ): Promise<{ total: number, success: number, failed: number }> => {
    if (!supabase) {
      throw new Error(t('authError', 'Supabase client not initialized'));
    }
    
    const stats = { total: keys.length, success: 0, failed: 0 };
    
    // Sử dụng backend API endpoint thay vì trực tiếp thao tác với Supabase
    for (const item of keys) {
      try {
        // Kiểm tra xem key có trống không
        if (!item.key || item.key.trim() === '') {
          stats.failed++;
          continue;
        }
        
        // Lấy token xác thực từ Supabase (cách lấy token mới hơn)
        const { data: { session } } = await supabase.auth.getSession();
        const token = session?.access_token;
        
        if (!token) {
          throw new Error(t('authError', 'Authentication token not available'));
        }
        
        // Gọi API endpoint để tạo provider key
        const response = await fetch('/api/v1/provider-keys/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            provider_name: providerName,
            name: item.description || null,
            api_key: item.key.trim()
          })
        });
        
        if (!response.ok) {
          // Ghi log lỗi chi tiết từ API
          const errorData = await response.json();
          console.error('Error importing key:', errorData);
          stats.failed++;
          continue;
        }
        
        // Đã thêm key thành công
        const responseData = await response.json();
        stats.success++;
        
        // Ghi log
        await addProviderKeyLog(
          'ADD',
          providerName,
          responseData.id,
          `Imported key ${item.description ? `"${item.description}"` : ''} for ${providerDisplayNames[providerName] || providerName}`
        );
      } catch (error) {
        console.error('Error importing key:', error);
        stats.failed++;
      }
    }
    
    // Cập nhật danh sách sau khi import
    fetchProviderKeys();
    
    return stats;
  };

  // Tạo danh sách nhóm Provider từ danh sách key
  const providerGroups = React.useMemo(() => {
    // Tạo mảng các Provider keys duy nhất để hiển thị
    const allProviders = Object.keys(providerDisplayNames);
    
    // Nhóm key theo provider_name
    const groups = allProviders.map(providerName => {
      const providerKeysForGroup = providerKeys.filter(key => key.provider_name === providerName);
      const hasSelectedKey = providerKeysForGroup.some(key => key.is_selected);
      
      return {
        providerName,
        displayName: providerDisplayNames[providerName],
        count: providerKeysForGroup.length,
        keys: providerKeysForGroup,
        hasSelectedKey
      };
    });
    
    // Chỉ giữ lại các Provider có key hoặc có trong danh sách mặc định
    return groups.filter(group => group.count > 0);
  }, [providerKeys]);
  
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

      // Lấy thông tin key để hiển thị tên trong log
      const { data: keyData } = await supabase
        .from('user_provider_keys')
        .select('name')
        .eq('id', keyId)
        .single();

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
      
      // Ghi nhật ký với format mới cho description
      await addProviderKeyLog(
        logAction, 
        providerName, 
        keyId, 
        logAction === 'SELECT' ? 
          `Selected ${keyData?.name ? `"${keyData.name}"` : ''} as default key for ${providerDisplayNames[providerName] || providerName}` : 
          `Unselected ${keyData?.name ? `"${keyData.name}"` : ''} as default key for ${providerDisplayNames[providerName] || providerName}`
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
    setKeyToDelete({id: keyId, providerName});
    setDeleteDialogOpen(true);
  };

  const handleDeleteKeyConfirm = async () => {
    if (!keyToDelete) return;
    const {id, providerName} = keyToDelete;
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
        .eq('id', id)
        .single();
        
      const { error } = await supabase
        .from('user_provider_keys')
        .delete()
        .eq('id', id);
      
      if (error) throw error;
      
      // Use translation for success toast
      toast.success(t('providerList.deleteSuccess', { provider: providerDisplayNames[providerName] || providerName }));
      
      // Ghi nhật ký với format mới cho description
      await addProviderKeyLog(
        'DELETE',
        providerName,
        id,
        `Deleted key ${keyData?.name ? `"${keyData.name}"` : ''} for ${providerDisplayNames[providerName] || providerName}`
      );
      
      // Refresh the list
      fetchProviderKeys();
    } catch (error: any) {
      console.error('Error deleting provider key:', error);
      // Use translation for error toast
      toast.error(`${t('providerList.deleteError', 'Error deleting key:')} ${error.message}`);
    } finally {
      setDeleteDialogOpen(false);
      setKeyToDelete(null);
    }
  };

  // Hàm xử lý việc mở rộng/thu gọn khi click vào Provider
  const toggleProviderExpanded = (providerName: string) => {
    setExpandedProviders(prev => ({
      ...prev,
      [providerName]: !prev[providerName]
    }));
  };

  // Hàm xóa toàn bộ key của một Provider
  const handleDeleteAllKeysForProvider = async (providerName: string) => {
    setProviderToDeleteAll(providerName);
    setDeleteAllDialogOpen(true);
  };

  const handleDeleteAllKeysForProviderConfirm = async () => {
    const providerName = providerToDeleteAll;
    if (!providerName) return;
    // Yêu cầu xác nhận từ người dùng
    try {
      if (!supabase) {
        throw new Error(t('authError', 'Supabase client not initialized'));
      }
      
      // Xóa tất cả key của Provider này
      const { error } = await supabase
        .from('user_provider_keys')
        .delete()
        .eq('provider_name', providerName);
      
      if (error) throw error;
      
      // Thông báo thành công
      toast.success(t('providerList.deleteAllSuccess', { 
        provider: providerDisplayNames[providerName] || providerName 
      }));
      
      // Ghi log
      await addProviderKeyLog(
        'DELETE',
        providerName,
        null,
        `Deleted all keys for ${providerDisplayNames[providerName] || providerName}`
      );
      
      // Refresh danh sách
      fetchProviderKeys();
    } catch (error: any) {
      console.error(`Error deleting all keys for ${providerName}:`, error);
      toast.error(`${t('providerList.deleteAllError', 'Error deleting keys:')} ${error.message}`);
    } finally {
      setDeleteAllDialogOpen(false);
      setProviderToDeleteAll(null);
    }
  };

  // Hàm xử lý việc tìm kiếm trong một provider cụ thể
  const handleSearchTermChange = (providerName: string, value: string) => {
    setSearchTerms(prev => ({
      ...prev,
      [providerName]: value
    }));
  };

  // Hàm lọc keys theo search term cho từng provider
  const getFilteredKeysForProvider = (keys: ProviderKey[], providerName: string) => {
    const searchTerm = searchTerms[providerName] || '';
    if (!searchTerm.trim()) return keys;
    
    return keys.filter(key => {
      const searchLower = searchTerm.toLowerCase();
      // Tìm kiếm theo description
      if (key.name && key.name.toLowerCase().includes(searchLower)) {
        return true;
      }
      // Tìm kiếm theo thời gian tạo
      if (new Date(key.created_at).toLocaleString().toLowerCase().includes(searchLower)) {
        return true;
      }
      return false;
    });
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
      {/* Hàng 1: Bố cục 2 cột - Danh sách Keys và About */}
      <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', md: 'row' }, mb: 3 }}>
        {/* Cột trái: Danh sách Provider Keys */}
        <Box sx={{ flex: '5', minWidth: 0 }}>
          {/* Tiêu đề Provider Keys */}
          <Typography variant="h6" gutterBottom>
            {t('providerList.title')}
          </Typography>
          
          {/* Display initial fetch error if it occurred before rendering the list */}
          {error && !loading && providerKeys.length === 0 && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          
          {/* Danh sách Provider Keys */}
          {providerKeys.length === 0 && !loading && !error ? (
            <Alert severity="info">
              {t('providerView.noKeys')} {/* Use translation */}
            </Alert>
          ) : (
            <Box>
              {providerGroups.map((group) => (
                <Card key={group.providerName} sx={{ mb: 2 }}>
                  <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <Box 
                      sx={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center',
                        cursor: 'pointer'
                      }}
                      onClick={() => toggleProviderExpanded(group.providerName)}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Chip 
                          label={group.displayName} 
                          color={
                            group.providerName === 'google' ? 'primary' :
                            group.providerName === 'xai' ? 'secondary' :
                            group.providerName === 'gigachat' ? 'success' :
                            group.providerName === 'perplexity' ? 'warning' : 'default'
                          }
                          sx={{ mr: 2 }}
                        />
                        {group.hasSelectedKey && (
                          <Chip 
                            label={t('providerList.hasDefault', 'Has Default')} 
                            color="success" 
                            size="small" 
                            icon={<CheckIcon />}
                          />
                        )}
                      </Box>
                      <Box>
                        <Badge 
                          badgeContent={group.count}
                          color={
                            group.providerName === 'google' ? 'primary' :
                            group.providerName === 'xai' ? 'secondary' :
                            group.providerName === 'gigachat' ? 'success' :
                            group.providerName === 'perplexity' ? 'warning' : 'default'
                          }
                          sx={{ mr: 1 }}
                        >
                          <IconButton 
                            size="small" 
                            color="error" 
                            onClick={(e) => {
                              e.stopPropagation(); // Ngăn không cho event click lan đến parent
                              handleDeleteAllKeysForProvider(group.providerName);
                            }}
                            aria-label={t('providerList.deleteAllButton', 'Delete All Keys')}
                          >
                            <FolderDeleteIcon />
                          </IconButton>
                        </Badge>
                        {expandedProviders[group.providerName] ? (
                          <ExpandLessIcon />
                        ) : (
                          <ExpandMoreIcon />
                        )}
                      </Box>
                    </Box>
                  </CardContent>
                  
                  <Collapse in={!!expandedProviders[group.providerName]}>
                    <Divider />
                    <Box sx={{ p: 2, pb: 1, display: 'flex', gap: 1 }}>
                      <TextField
                        fullWidth
                        variant="outlined"
                        size="small"
                        placeholder={t('providerList.searchProvider', 'Search keys...')}
                        value={searchTerms[group.providerName] || ''}
                        onChange={(e) => handleSearchTermChange(group.providerName, e.target.value)}
                        InputProps={{
                          startAdornment: (
                            <InputAdornment position="start">
                              <SearchIcon fontSize="small" />
                            </InputAdornment>
                          ),
                        }}
                      />
                      {/* Nút Import from CSV */}
                      <IconButton
                        size="small"
                        onClick={(e) => handleImportClick(group.providerName, e)}
                        color={
                          group.providerName === 'google' ? 'primary' :
                          group.providerName === 'xai' ? 'secondary' :
                          group.providerName === 'gigachat' ? 'success' :
                          group.providerName === 'perplexity' ? 'warning' : 'primary'
                        }
                        disabled={importing[group.providerName]}
                        sx={{ border: 1, borderColor: 'divider', p: 1 }}
                      >
                        {importing[group.providerName] 
                          ? <CircularProgress size={16} />
                          : <InsertDriveFileIcon />}
                      </IconButton>
                      {/* Hidden file input cho import CSV */}
                      <input 
                        type="file"
                        accept=".csv,.txt"
                        style={{ display: 'none' }}
                        ref={el => fileInputRefs.current[group.providerName] = el}
                        onChange={(e) => handleCsvFileChange(group.providerName, e)}
                      />
                    </Box>
                    <TableContainer sx={{ maxHeight: 300, overflow: 'auto' }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>{t('providerList.headerDescription', 'Description')}</TableCell>
                            <TableCell>{t('providerList.headerCreated', 'Created')}</TableCell>
                            <TableCell align="center">{t('providerList.headerDefault', 'Default')}</TableCell>
                            <TableCell align="right">{t('providerList.headerActions', 'Actions')}</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {getFilteredKeysForProvider(group.keys, group.providerName).map((key) => (
                            <TableRow key={key.id}>
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
                                  aria-label={t('providerList.deleteButton')}
                                >
                                  <CancelIcon />
                                </IconButton>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Collapse>
                </Card>
              ))}

            </Box>
          )}
        </Box>

        {/* Cột phải: About Provider API Keys */}
        <Box sx={{ flex: '3', minWidth: 250 }}>
          <Paper 
            sx={{ 
              p: 3, 
              height: '100%', 
              backgroundColor: 'info.dark', // Thay đổi từ 'grey.800' sang 'info.dark' (màu xanh dương đậm)
              color: 'white',
              '& ul': { 
                color: 'white' 
              },
              boxShadow: 3
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <InfoIcon sx={{ mr: 1 }} />
              <Typography variant="h6" component="h2">
                {t('providerView.aboutTitle')}
              </Typography>
            </Box>
            
            <Typography variant="body2" paragraph sx={{ opacity: 0.9, fontSize: '0.85rem' }}>
              {t('providerView.aboutIntro')}
            </Typography>
            
            <Typography variant="body2" paragraph sx={{ mt: 1.5, fontWeight: 'medium', fontSize: '0.85rem' }}>
              {t('providerView.aboutBenefitsTitle')}
            </Typography>
            
            <Box component="ul" sx={{ mt: 0, pl: 2 }}>
              <Typography component="li" variant="body2" sx={{ mb: 0.75, fontSize: '0.8rem' }}>
                {t('providerView.aboutBenefit1')}
              </Typography>
              <Typography component="li" variant="body2" sx={{ mb: 0.75, fontSize: '0.8rem' }}>
                {t('providerView.aboutBenefit2')}
              </Typography>
              <Typography component="li" variant="body2" sx={{ fontSize: '0.8rem' }}>
                {t('providerView.aboutBenefit3')}
              </Typography>
            </Box>
            
            <Typography 
              variant="body2" 
              paragraph 
              sx={{ 
                mt: 1.5, 
                fontStyle: 'italic', 
                borderTop: '1px solid rgba(255, 255, 255, 0.3)',
                pt: 1,
                fontSize: '0.8rem'
              }}
            >
              {t('providerView.aboutSecurity')}
            </Typography>
          </Paper>
        </Box>
      </Box>

      {/* Hàng 2: Activity Log chiếm toàn bộ chiều rộng */}
      <Box>
        <Typography variant="h6" gutterBottom>
          {t('providerLogs.title', 'Activity Log')}
        </Typography>
        <ProviderKeyLogs logs={logs} loading={loadingLogs} />
      </Box>

      {/* Dialog xác nhận xóa key */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
      >
        <DialogTitle>{t('providerList.deleteConfirmTitle')}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('providerList.deleteConfirmMessage', { provider: keyToDelete?.providerName })}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} color="primary">
            {t('action.cancel')}
          </Button>
          <Button onClick={handleDeleteKeyConfirm} color="secondary">
            {t('action.delete')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog xác nhận xóa tất cả key của một Provider */}
      <Dialog
        open={deleteAllDialogOpen}
        onClose={() => setDeleteAllDialogOpen(false)}
      >
        <DialogTitle>{t('providerList.deleteAllConfirmTitle')}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('providerList.deleteAllConfirmMessage', { 
              provider: providerDisplayNames[providerToDeleteAll || ''] || providerToDeleteAll 
            })}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteAllDialogOpen(false)} color="primary">
            {t('action.cancel')}
          </Button>
          <Button onClick={handleDeleteAllKeysForProviderConfirm} color="secondary">
            {t('action.deleteAll')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Dialog hiển thị kết quả import CSV */}
      <Dialog
        open={importDialogOpen}
        onClose={() => {
          if (!importing[currentImportProvider || '']) {
            setImportDialogOpen(false);
            setCurrentImportProvider(null);
          }
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {importing[currentImportProvider || ''] 
            ? t('providerList.importingTitle', 'Importing API Keys...') 
            : t('providerList.importResultTitle', 'Import Results')}
        </DialogTitle>
        <DialogContent>
          {importing[currentImportProvider || ''] ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 2 }}>
              <CircularProgress sx={{ mb: 2 }} />
              <Typography>
                {t('providerList.importingMessage', 'Processing CSV file...')}
              </Typography>
            </Box>
          ) : (
            currentImportProvider && importStats[currentImportProvider] && (
              <Box>
                <Typography variant="subtitle1" gutterBottom>
                  {t('providerList.importResultSummary', 'Import Summary for {{provider}}', {
                    provider: providerDisplayNames[currentImportProvider] || currentImportProvider
                  })}
                </Typography>

                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
                  <Box sx={{ textAlign: 'center', flex: 1 }}>
                    <Typography variant="h5">{importStats[currentImportProvider].total}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {t('providerList.importResultTotal', 'Total Keys')}
                    </Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center', flex: 1 }}>
                    <Typography variant="h5" color="success.main">{importStats[currentImportProvider].success}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {t('providerList.importResultSuccess', 'Successfully Imported')}
                    </Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center', flex: 1 }}>
                    <Typography variant="h5" color="error.main">{importStats[currentImportProvider].failed}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {t('providerList.importResultFailed', 'Failed/Duplicate')}
                    </Typography>
                  </Box>
                </Box>

                {importStats[currentImportProvider].failed > 0 && (
                  <Alert severity="info" sx={{ mt: 2 }}>
                    {t('providerList.importResultFailedNote', 'Note: Failed keys may already exist or have invalid formats.')}
                  </Alert>
                )}
              </Box>
            )
          )}
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => {
              setImportDialogOpen(false);
              setCurrentImportProvider(null);
            }} 
            color="primary"
            disabled={importing[currentImportProvider || '']}
          >
            {t('action.close', 'Close')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Component hiển thị nhật ký Provider Keys */}
      <Box sx={{ display: 'none' }}>This is a placeholder</Box>
    </Box>
  );
};

// Component hiển thị nhật ký
interface ProviderKeyLogsProps {
  logs: ProviderKeyLog[];
  loading: boolean;
}

const ProviderKeyLogs: React.FC<ProviderKeyLogsProps> = ({ logs, loading }) => {
  const { t } = useTranslation();
  
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" my={2}>
        <CircularProgress size={24} />
      </Box>
    );
  }
  
  if (logs.length === 0) {
    return (
      <Alert severity="info">
        {t('providerLogs.noLogs', 'No recent activity with provider keys.')}
      </Alert>
    );
  }
  
  return (
    <TableContainer component={Paper} sx={{ maxHeight: 250 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>{t('providerLogs.action', 'Action')}</TableCell>
            <TableCell>{t('providerLogs.description', 'Description')}</TableCell>
            <TableCell>{t('providerLogs.time', 'Time')}</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {logs.map((log) => (
            <TableRow key={log.id}>
              <TableCell>
                <Chip
                  label={log.action}
                  size="small"
                  color={
                    log.action === 'ADD' ? 'success' :
                    log.action === 'DELETE' ? 'error' :
                    log.action === 'SELECT' ? 'primary' :
                    log.action === 'UNSELECT' ? 'warning' : 'default'
                  }
                />
              </TableCell>
              <TableCell>{log.description}</TableCell>
              <TableCell>{new Date(log.created_at).toLocaleString()}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default ProviderKeyList;