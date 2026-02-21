import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { supabase } from '../supabaseClient';
import { getAccessToken } from '../authHelper';
import toast from 'react-hot-toast';
import {
  Box,
  Typography,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Collapse,
} from '@mui/material';

// Import các component con
import ProviderKeyLogs from './ProviderKeyLogs';
import AboutProviderKeys from './AboutProviderKeys';
import ProviderGroupHeader from './ProviderGroupHeader';
import ProviderKeyTable from './ProviderKeyTable';
import DeleteKeyConfirmationDialog from './DeleteKeyConfirmationDialog';
import DeleteAllKeysConfirmationDialog from './DeleteAllKeysConfirmationDialog';
import ImportResultDialog from './ImportResultDialog';
import AddProviderKeyDialog from './AddProviderKeyDialog'; // Import dialog mới

// --- Interfaces (Định nghĩa và Export) ---
export interface ProviderKey {
  id: string;
  provider_name: string;
  name: string | null;
  is_selected: boolean;
  created_at: string;
}

export interface ProviderKeyLog {
  id: string;
  user_id: string;
  action: 'ADD' | 'DELETE' | 'SELECT' | 'UNSELECT';
  provider_name: string;
  key_id: string | null;
  description: string;
  created_at: string;
}

export interface ImportStats {
  total: number;
  success: number;
  failed: number;
}
// --- Kết thúc Interfaces ---

const providerDisplayNames: Record<string, string> = {
  'google': 'Google AI (Gemini)',
  'xai': 'X.AI (Grok)',
  'gigachat': 'GigaChat',
  'perplexity': 'Perplexity (Sonar)'
};

const ProviderKeyList: React.FC = () => {
  const { t } = useTranslation();
  const [providerKeys, setProviderKeys] = useState<ProviderKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<ProviderKeyLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(true);
  const [expandedProviders, setExpandedProviders] = useState<Record<string, boolean>>({});
  const [searchTerms, setSearchTerms] = useState<Record<string, string>>({});
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);
  const [keyToDelete, setKeyToDelete] = useState<{ id: string, providerName: string } | null>(null);
  const [providerToDeleteAll, setProviderToDeleteAll] = useState<string | null>(null);
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const [importing, setImporting] = useState<Record<string, boolean>>({});
  const [importStats, setImportStats] = useState<Record<string, ImportStats | null>>({});
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [currentImportProvider, setCurrentImportProvider] = useState<string | null>(null);

  // Add key dialog state
  const [addKeyDialogOpen, setAddKeyDialogOpen] = useState(false);
  const [providerToAddKey, setProviderToAddKey] = useState<string | null>(null);

  // --- Fetching Data ---
  const fetchProviderKeys = async () => {
    try {
      setLoading(true);
      setError(null);

      const token = await getAccessToken();

      // Gọi API backend để lấy keys
      const response = await fetch('/api/v1/provider-keys/', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(`API Error (${response.status}): ${errorData.detail || 'Failed to fetch provider keys'}`);
      }

      const data = await response.json();
      // Sắp xếp lại dữ liệu nếu cần (API backend có thể đã sắp xếp)
      const sortedData = (data || []).sort((a: ProviderKey, b: ProviderKey) => {
        if (a.provider_name < b.provider_name) return -1;
        if (a.provider_name > b.provider_name) return 1;
        // Nếu provider_name giống nhau, sắp xếp theo created_at giảm dần
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
      setProviderKeys(sortedData);

    } catch (err: any) {
      console.error('Error fetching provider keys via API:', err);
      setError(`${t('providerList.fetchError', 'Error fetching provider keys:')} ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchProviderKeyLogs = async () => {
    try {
      setLoadingLogs(true);

      let token: string;
      try {
        token = await getAccessToken();
      } catch {
        console.warn('Cannot fetch logs: User not authenticated.');
        setLogs([]);
        return;
      }

      // Gọi API backend để lấy logs
      const response = await fetch('/api/v1/activity-logs/?limit=50', { // Thêm limit vào query
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        // Không throw lỗi để không ảnh hưởng UI chính, chỉ log lỗi
        console.error(`API Error (${response.status}) fetching logs: ${errorData.detail || 'Failed to fetch activity logs'}`);
        setLogs([]); // Xóa log cũ nếu fetch lỗi
        return;
      }

      const data = await response.json();
      setLogs(data || []); // API đã sắp xếp sẵn

    } catch (err: any) {
      console.error('Error fetching provider key logs via API:', err);
      // Không hiển thị lỗi log trên UI
      setLogs([]); // Xóa log cũ nếu có lỗi khác
    } finally {
      setLoadingLogs(false);
    }
  };

  // --- Logging ---
  const addProviderKeyLog = async (action: 'ADD' | 'DELETE' | 'SELECT' | 'UNSELECT', providerName: string, keyId: string | null = null, description: string = '') => {
    try {
      let token: string;
      try {
        token = await getAccessToken();
      } catch {
        console.error('Authentication token not available for logging.');
        return;
      }

      const logPayload = {
        action,
        provider_name: providerName,
        key_id: keyId,
        description: description || `${action} key for ${providerDisplayNames[providerName] || providerName}`
      };

      const response = await fetch('/api/v1/activity-logs/', { // Sử dụng đường dẫn tương đối
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(logPayload)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' })); // Bắt lỗi nếu response không phải JSON
        throw new Error(`API Error (${response.status}): ${errorData.detail || 'Failed to log activity'}`);
      }

      // Log thành công, fetch lại logs để cập nhật UI
      // Không cần fetch logs thủ công nữa, realtime sẽ cập nhật
      // fetchProviderKeyLogs();

    } catch (err: any) {
      console.error('Error adding activity log via API:', err);
      // Có thể hiển thị thông báo lỗi nhẹ nhàng cho người dùng nếu cần
      // toast.error(t('providerList.logError', 'Could not record activity: {{message}}', { message: err.message }));
    }
  };

  // Effect để fetch dữ liệu ban đầu
  useEffect(() => {
    fetchProviderKeys();
    fetchProviderKeyLogs(); // Fetch logs ban đầu khi component mount
  }, []);

  // Effect để thiết lập và dọn dẹp Realtime subscription cho logs
  useEffect(() => {
    /* 
    // Tạm thời vô hiệu hoá Realtime Subscription của Supabase.
    // Vì hiện tại Frontend đang dùng Keycloak JWT để xác thực (thông qua Backend),
    // việc kết nối trực tiếp từ Frontend lên Supabase Realtime bằng Anon Key 
    // sẽ bị từ chối truy cập (401/WebSocket Error).
    if (!supabase) return;

    let realtimeChannel: RealtimeChannel | null = null;
    const setupSubscription = async () => { ... }
    setupSubscription();

    return () => {
      if (realtimeChannel && supabase) {
        supabase.removeChannel(realtimeChannel);
      }
    };
    */
  }, [supabase]); // Chỉ chạy lại nếu instance supabase thay đổi (thường là không)

  // --- Key Handlers ---
  const handleSelectKey = async (keyId: string, providerName: string, currentIsSelected: boolean) => {
    try {
      const newIsSelectedValue = !currentIsSelected;
      const logAction: 'SELECT' | 'UNSELECT' = newIsSelectedValue ? 'SELECT' : 'UNSELECT';

      const token = await getAccessToken();

      // Gọi API backend để cập nhật (PATCH)
      const response = await fetch(`/api/v1/provider-keys/${keyId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ is_selected: newIsSelectedValue })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(`API Error (${response.status}): ${errorData.detail || 'Failed to update selection'}`);
      }

      const updatedKeyData = await response.json(); // Lấy dữ liệu key đã cập nhật (bao gồm cả name)

      // Thông báo thành công
      const successMsg = newIsSelectedValue
        ? t('providerList.selectSuccess', { provider: providerDisplayNames[providerName] || providerName })
        : t('providerList.unselectSuccess', { provider: providerDisplayNames[providerName] || providerName });
      toast.success(successMsg);

      // Ghi log qua API
      const keyName = updatedKeyData?.name; // Lấy name từ response API
      await addProviderKeyLog(
        logAction,
        providerName,
        keyId,
        logAction === 'SELECT' ?
          `Selected ${keyName ? `"${keyName}"` : ''} as default key for ${providerDisplayNames[providerName] || providerName}` :
          `Unselected ${keyName ? `"${keyName}"` : ''} as default key for ${providerDisplayNames[providerName] || providerName}`
      );

      // Fetch lại danh sách keys
      fetchProviderKeys();

    } catch (err: any) {
      console.error('Error updating provider key selection via API:', err);
      toast.error(t('providerList.updateSelectionError', 'Error updating selection: {{message}}', { message: err.message }));
    }
  };

  const handleDeleteKey = (keyId: string, providerName: string) => {
    setKeyToDelete({ id: keyId, providerName });
    setDeleteDialogOpen(true);
  };

  const handleDeleteKeyConfirm = async () => {
    if (!keyToDelete) return;
    const { id, providerName } = keyToDelete;
    // Lấy name trước khi xóa để ghi log (cần fetch trước hoặc lấy từ state nếu có)
    const keyData = providerKeys.find(k => k.id === id); // Lấy từ state hiện tại
    const keyNameForLog = keyData?.name;

    try {
      const token = await getAccessToken();

      // Gọi API backend để xóa (DELETE)
      const response = await fetch(`/api/v1/provider-keys/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      // Check status 204 No Content for successful deletion
      if (response.status !== 204) {
        // Nếu không phải 204, cố gắng đọc lỗi
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(`API Error (${response.status}): ${errorData.detail || 'Failed to delete key'}`);
      }

      // Thông báo thành công
      toast.success(t('providerList.deleteSuccess', { provider: providerDisplayNames[providerName] || providerName }));

      // Ghi log qua API
      await addProviderKeyLog(
        'DELETE',
        providerName,
        id,
        `Deleted key ${keyNameForLog ? `"${keyNameForLog}"` : ''} for ${providerDisplayNames[providerName] || providerName}`
      );

      // Fetch lại danh sách keys
      fetchProviderKeys();

    } catch (err: any) {
      console.error('Error deleting provider key via API:', err);
      toast.error(t('providerList.deleteError', 'Error deleting key: {{message}}', { message: err.message }));
    } finally {
      setDeleteDialogOpen(false);
      setKeyToDelete(null);
    }
  };

  const handleDeleteAllKeysForProvider = (providerName: string) => {
    setProviderToDeleteAll(providerName);
    setDeleteAllDialogOpen(true);
  };

  const handleDeleteAllKeysForProviderConfirm = async () => {
    const providerName = providerToDeleteAll;
    if (!providerName) return;
    try {
      const token = await getAccessToken();

      // Gọi API backend để xóa tất cả theo provider (DELETE với query param)
      const response = await fetch(`/api/v1/provider-keys/?provider_name=${encodeURIComponent(providerName)}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      // Check status 204 No Content for successful deletion
      if (response.status !== 204) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(`API Error (${response.status}): ${errorData.detail || 'Failed to delete keys'}`);
      }

      // Thông báo thành công
      toast.success(t('providerList.deleteAllSuccess', { provider: providerDisplayNames[providerName] || providerName }));

      // Ghi log qua API
      await addProviderKeyLog(
        'DELETE',
        providerName,
        null, // keyId là null khi xóa tất cả
        `Deleted all keys for ${providerDisplayNames[providerName] || providerName}`
      );

      // Fetch lại danh sách keys
      fetchProviderKeys();

    } catch (err: any) {
      console.error(`Error deleting all keys for ${providerName} via API:`, err);
      toast.error(t('providerList.deleteAllError', 'Error deleting keys: {{message}}', { message: err.message }));
    } finally {
      setDeleteAllDialogOpen(false);
      setProviderToDeleteAll(null);
    }
  };

  // --- UI Handlers ---
  const toggleProviderExpanded = (providerName: string) => {
    setExpandedProviders(prev => ({ ...prev, [providerName]: !prev[providerName] }));
  };

  const handleSearchTermChange = (providerName: string, value: string) => {
    setSearchTerms(prev => ({ ...prev, [providerName]: value }));
  };

  // --- Import Handlers ---
  const handleImportClick = (providerName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    fileInputRefs.current[providerName]?.click();
  };

  const handleCsvFileChange = async (providerName: string, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setImporting(prev => ({ ...prev, [providerName]: true }));
      setCurrentImportProvider(providerName);
      setImportDialogOpen(true);

      const keys = await readCsvFile(file);
      if (keys.length === 0) throw new Error(t('providerList.importError.noKeys', 'No keys found in CSV file'));

      const stats = await importKeysToProvider(keys, providerName);
      setImportStats(prev => ({ ...prev, [providerName]: stats }));

      toast.success(t('providerList.importSuccess', { count: stats.success, provider: providerDisplayNames[providerName] || providerName }));
      fetchProviderKeys(); // Refresh list after import
      await addProviderKeyLog('ADD', providerName, null, `Imported ${stats.success} keys from CSV for ${providerDisplayNames[providerName] || providerName}`);

    } catch (err: any) {
      console.error('Error importing CSV:', err);
      toast.error(`${t('providerList.importError.general', 'Error importing CSV:')} ${err.message}`);
      // Reset stats for the failed provider on error
      setImportStats(prev => ({ ...prev, [providerName]: null }));
    } finally {
      if (e.target) e.target.value = ''; // Reset file input
      // Keep dialog open to show results/error, but mark importing as false
      setImporting(prev => ({ ...prev, [providerName]: false }));
    }
  };

  const readCsvFile = (file: File): Promise<{ description: string, key: string }[]> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const content = event.target?.result as string;
          if (!content) throw new Error(t('providerList.importError.readError', 'Could not read file content'));

          const lines = content.split(/\r\n|\n/).filter(line => line.trim());
          const keys = lines.map(line => {
            const separator = line.includes(',') ? ',' : line.includes(';') ? ';' : '\t';
            const parts = line.split(separator);
            return {
              description: (parts[0] || '').trim(),
              key: (parts[1] || '').trim()
            };
          }).filter(item => item.key && item.key.length > 0);
          resolve(keys);
        } catch (error) { reject(error); }
      };
      reader.onerror = () => reject(new Error(t('providerList.importError.readError', 'Error reading file')));
      reader.readAsText(file);
    });
  };

  const importKeysToProvider = async (keys: { description: string, key: string }[], providerName: string): Promise<ImportStats> => {
    const stats: ImportStats = { total: keys.length, success: 0, failed: 0 };
    const token = await getAccessToken();

    for (const item of keys) {
      if (!item.key || item.key.trim() === '') {
        stats.failed++;
        continue;
      }
      try {
        const response = await fetch('/api/v1/provider-keys/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ provider_name: providerName, name: item.description || null, api_key: item.key.trim() })
        });

        if (!response.ok) {
          const errorData = await response.json();
          console.error('Error importing key via API:', errorData);
          stats.failed++;
        } else {
          // const responseData = await response.json(); // Removed unused variable
          stats.success++;
          // Log individual key addition success? Maybe too verbose. Logged after loop.
          // await addProviderKeyLog('ADD', providerName, responseData.id, `Imported key ${item.description ? `"${item.description}"` : ''}`);
        }
      } catch (error) {
        console.error('Network or other error importing key:', error);
        stats.failed++;
      }
    }
    // No need to call fetchProviderKeys here, it's called in handleCsvFileChange
    return stats;
  };

  // --- Derived State & Filtering ---
  const providerGroups = useMemo(() => {
    const allProviders = Object.keys(providerDisplayNames);
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
    // Keep all providers defined in providerDisplayNames, even if they have 0 keys initially
    return groups;
    // Filter only providers with keys: return groups.filter(group => group.count > 0);
  }, [providerKeys]);

  const getFilteredKeysForProvider = (keys: ProviderKey[], providerName: string) => {
    const searchTerm = searchTerms[providerName] || '';
    if (!searchTerm.trim()) return keys;
    const searchLower = searchTerm.toLowerCase();
    return keys.filter(key =>
      (key.name && key.name.toLowerCase().includes(searchLower)) ||
      new Date(key.created_at).toLocaleString().toLowerCase().includes(searchLower)
    );
  };

  // Handler for adding new key
  const handleAddKeyClick = (providerName: string) => {
    setProviderToAddKey(providerName);
    setAddKeyDialogOpen(true);
  };

  const handleAddKeySuccess = () => {
    fetchProviderKeys();
    // Không cần fetch logs thủ công nữa
    // fetchProviderKeyLogs();
  };

  // --- Render Logic ---
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" my={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Row 1: Key List & About Section */}
      <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', md: 'row' }, mb: 3 }}>
        {/* Left Column: Provider Key List */}
        <Box sx={{ flex: '5', minWidth: 0 }}>
          <Typography variant="h6" gutterBottom>
            {t('providerList.title')}
          </Typography>

          {error && !loading && providerKeys.length === 0 && (
            <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
          )}

          {/* Luôn render Box chứa các group, ngay cả khi providerKeys ban đầu rỗng */}
          <Box>
            {providerGroups.map((group) => (
              <Card key={group.providerName} sx={{ mb: 2 }}>
                <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                  <ProviderGroupHeader
                    providerName={group.providerName}
                    displayName={group.displayName}
                    count={group.count} // Sẽ là 0 nếu không có key
                    hasSelectedKey={group.hasSelectedKey} // Sẽ là false nếu không có key
                    isExpanded={!!expandedProviders[group.providerName]}
                    onToggleExpand={toggleProviderExpanded}
                    onDeleteAll={handleDeleteAllKeysForProvider}
                  />
                </CardContent>
                <Collapse in={!!expandedProviders[group.providerName]}>
                  <ProviderKeyTable
                    keys={getFilteredKeysForProvider(group.keys, group.providerName)} // Sẽ là mảng rỗng nếu không có key
                    providerName={group.providerName}
                    searchTerm={searchTerms[group.providerName] || ''}
                    importing={!!importing[group.providerName]}
                    fileInputRef={el => fileInputRefs.current[group.providerName] = el}
                    onSearchChange={handleSearchTermChange}
                    onImportClick={handleImportClick}
                    onFileChange={handleCsvFileChange}
                    onSelectKey={handleSelectKey}
                    onDeleteKey={handleDeleteKey}
                    onAddKeyClick={handleAddKeyClick} // Nút Add sẽ hiển thị trong ProviderKeyTable
                  />
                </Collapse>
              </Card>
            ))}
          </Box>
        </Box>

        {/* Right Column: About Section - Align to top */}
        <Box sx={{ flex: '3', minWidth: 250, alignSelf: 'flex-start' }}>
          <AboutProviderKeys />
        </Box>
      </Box>

      {/* Row 2: Activity Log */}
      <Box>
        <Typography variant="h6" gutterBottom>
          {t('providerLogs.title', 'Activity Log')}
        </Typography>
        <ProviderKeyLogs logs={logs} loading={loadingLogs} />
      </Box>

      {/* Dialogs */}
      <DeleteKeyConfirmationDialog
        open={deleteDialogOpen}
        providerName={keyToDelete ? providerDisplayNames[keyToDelete.providerName] : ''}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleDeleteKeyConfirm}
      />

      <DeleteAllKeysConfirmationDialog
        open={deleteAllDialogOpen}
        providerDisplayName={providerToDeleteAll ? providerDisplayNames[providerToDeleteAll] : ''}
        onClose={() => setDeleteAllDialogOpen(false)}
        onConfirm={handleDeleteAllKeysForProviderConfirm}
      />

      <ImportResultDialog
        open={importDialogOpen}
        importing={!!importing[currentImportProvider || '']}
        providerDisplayName={currentImportProvider ? providerDisplayNames[currentImportProvider] : ''}
        importStats={currentImportProvider ? importStats[currentImportProvider] : null}
        onClose={() => {
          // Only close if not importing
          if (!importing[currentImportProvider || '']) {
            setImportDialogOpen(false);
            setCurrentImportProvider(null);
            // Optionally clear stats after closing
            // if (currentImportProvider) {
            //   setImportStats(prev => ({ ...prev, [currentImportProvider!]: null }));
            // }
          }
        }}
      />

      {/* Add Provider Key Dialog */}
      {providerToAddKey && (
        <AddProviderKeyDialog
          open={addKeyDialogOpen}
          providerName={providerToAddKey}
          providerDisplayName={providerDisplayNames[providerToAddKey] || providerToAddKey}
          onClose={() => {
            setAddKeyDialogOpen(false);
            setProviderToAddKey(null);
          }}
          onSuccess={handleAddKeySuccess}
        />
      )}
    </Box>
  );
};

export default ProviderKeyList;