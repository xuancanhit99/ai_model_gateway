import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { supabase } from '../supabaseClient';
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
  const [keyToDelete, setKeyToDelete] = useState<{id: string, providerName: string} | null>(null);
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
      if (!supabase) throw new Error(t('authError', 'Supabase client not initialized'));

      const { data, error: fetchError } = await supabase
        .from('user_provider_keys')
        .select('*')
        .order('provider_name', { ascending: true })
        .order('created_at', { ascending: false });

      if (fetchError) throw fetchError;
      setProviderKeys(data || []);
    } catch (err: any) {
      console.error('Error fetching provider keys:', err);
      setError(`${t('providerList.fetchError', 'Error fetching provider keys:')} ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchProviderKeyLogs = async () => {
    try {
      setLoadingLogs(true);
      if (!supabase) throw new Error(t('authError', 'Supabase client not initialized'));

      const { data, error: fetchError } = await supabase
        .from('provider_key_logs')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(50);

      if (fetchError) throw fetchError;
      setLogs(data || []);
    } catch (err: any) {
      console.error('Error fetching provider key logs:', err);
      // Không hiển thị lỗi log trên UI
    } finally {
      setLoadingLogs(false);
    }
  };

  // --- Logging ---
  const addProviderKeyLog = async (action: 'ADD' | 'DELETE' | 'SELECT' | 'UNSELECT', providerName: string, keyId: string | null = null, description: string = '') => {
    try {
      if (!supabase) throw new Error('Supabase client not initialized');

      const { error: insertError } = await supabase
        .from('provider_key_logs')
        .insert({
          action,
          provider_name: providerName,
          key_id: keyId,
          description: description || `${action} key for ${providerDisplayNames[providerName] || providerName}`
        });

      if (insertError) throw insertError;
      fetchProviderKeyLogs(); // Refresh logs
    } catch (err: any) {
      console.error('Error adding log:', err);
    }
  };

  useEffect(() => {
    fetchProviderKeys();
    fetchProviderKeyLogs();
  }, []);

  // --- Key Handlers ---
  const handleSelectKey = async (keyId: string, providerName: string, currentIsSelected: boolean) => {
    try {
      if (!supabase) throw new Error(t('authError', 'Supabase client not initialized'));

      let newIsSelectedValue = !currentIsSelected;
      let successMsg = '';
      let logAction: 'SELECT' | 'UNSELECT' = newIsSelectedValue ? 'SELECT' : 'UNSELECT';

      const { data: keyData } = await supabase.from('user_provider_keys').select('name').eq('id', keyId).single();

      if (newIsSelectedValue) {
        await supabase.from('user_provider_keys').update({ is_selected: false }).eq('provider_name', providerName);
        successMsg = t('providerList.selectSuccess', { provider: providerDisplayNames[providerName] || providerName }, `Set "${providerDisplayNames[providerName] || providerName}" key as default`);
      } else {
        successMsg = t('providerList.unselectSuccess', { provider: providerDisplayNames[providerName] || providerName }, `Removed "${providerDisplayNames[providerName] || providerName}" key from default`);
      }

      const { error: updateError } = await supabase.from('user_provider_keys').update({ is_selected: newIsSelectedValue }).eq('id', keyId);
      if (updateError) throw updateError;

      toast.success(successMsg);
      await addProviderKeyLog(
        logAction,
        providerName,
        keyId,
        logAction === 'SELECT' ?
          `Selected ${keyData?.name ? `"${keyData.name}"` : ''} as default key for ${providerDisplayNames[providerName] || providerName}` :
          `Unselected ${keyData?.name ? `"${keyData.name}"` : ''} as default key for ${providerDisplayNames[providerName] || providerName}`
      );
      fetchProviderKeys();
    } catch (err: any) {
      console.error('Error updating provider key selection:', err);
      toast.error(t('providerList.updateSelectionError', 'Error updating selection: {{message}}', { message: err.message }, `Error updating selection: ${err.message}`));
    }
  };

  const handleDeleteKey = (keyId: string, providerName: string) => {
    setKeyToDelete({id: keyId, providerName});
    setDeleteDialogOpen(true);
  };

  const handleDeleteKeyConfirm = async () => {
    if (!keyToDelete) return;
    const {id, providerName} = keyToDelete;
    try {
      if (!supabase) throw new Error(t('authError', 'Supabase client not initialized'));

      const { data: keyData } = await supabase.from('user_provider_keys').select('name, is_selected').eq('id', id).single();
      const { error: deleteError } = await supabase.from('user_provider_keys').delete().eq('id', id);
      if (deleteError) throw deleteError;

      toast.success(t('providerList.deleteSuccess', { provider: providerDisplayNames[providerName] || providerName }, `Successfully deleted key for ${providerDisplayNames[providerName] || providerName}`));
      await addProviderKeyLog(
        'DELETE',
        providerName,
        id,
        `Deleted key ${keyData?.name ? `"${keyData.name}"` : ''} for ${providerDisplayNames[providerName] || providerName}`
      );
      fetchProviderKeys();
    } catch (err: any) {
      console.error('Error deleting provider key:', err);
      toast.error(t('providerList.deleteError', 'Error deleting key: {{message}}', { message: err.message }, `Error deleting key: ${err.message}`));
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
      if (!supabase) throw new Error(t('authError', 'Supabase client not initialized'));

      const { error: deleteError } = await supabase.from('user_provider_keys').delete().eq('provider_name', providerName);
      if (deleteError) throw deleteError;

      toast.success(t('providerList.deleteAllSuccess', 
        { provider: providerDisplayNames[providerName] || providerName }, 
        `Successfully deleted all keys for ${providerDisplayNames[providerName] || providerName}`
      ));
      await addProviderKeyLog(
        'DELETE',
        providerName,
        null,
        `Deleted all keys for ${providerDisplayNames[providerName] || providerName}`
      );
      fetchProviderKeys();
    } catch (err: any) {
      console.error(`Error deleting all keys for ${providerName}:`, err);
      toast.error(t('providerList.deleteAllError', 
        'Error deleting keys: {{message}}', 
        { message: err.message }, 
        `Error deleting keys: ${err.message}`
      ));
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

      toast.success(t('providerList.importSuccess', 
        { count: stats.success, provider: providerDisplayNames[providerName] || providerName }, 
        `Successfully imported ${stats.success} keys for ${providerDisplayNames[providerName] || providerName}`
      ));
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
    if (!supabase) throw new Error(t('authError', 'Supabase client not initialized'));

    const stats: ImportStats = { total: keys.length, success: 0, failed: 0 };
    const { data: { session } } = await supabase.auth.getSession();
    const token = session?.access_token;
    if (!token) throw new Error(t('authError', 'Authentication token not available'));

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
    fetchProviderKeyLogs();
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

          {providerKeys.length === 0 && !loading && !error ? (
             <Alert severity="info">{t('providerView.noKeys')}</Alert>
          ) : (
            <Box>
              {providerGroups.map((group) => (
                <Card key={group.providerName} sx={{ mb: 2 }}>
                  <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <ProviderGroupHeader
                      providerName={group.providerName}
                      displayName={group.displayName}
                      count={group.count}
                      hasSelectedKey={group.hasSelectedKey}
                      isExpanded={!!expandedProviders[group.providerName]}
                      onToggleExpand={toggleProviderExpanded}
                      onDeleteAll={handleDeleteAllKeysForProvider}
                    />
                  </CardContent>
                  <Collapse in={!!expandedProviders[group.providerName]}>
                    <ProviderKeyTable
                      keys={getFilteredKeysForProvider(group.keys, group.providerName)}
                      providerName={group.providerName}
                      searchTerm={searchTerms[group.providerName] || ''}
                      importing={!!importing[group.providerName]}
                      fileInputRef={el => fileInputRefs.current[group.providerName] = el} 
                      onSearchChange={handleSearchTermChange}
                      onImportClick={handleImportClick}
                      onFileChange={handleCsvFileChange}
                      onSelectKey={handleSelectKey}
                      onDeleteKey={handleDeleteKey}
                      onAddKeyClick={handleAddKeyClick} // Thêm prop onAddKeyClick
                    />
                  </Collapse>
                </Card>
              ))}
            </Box>
          )}
        </Box>

        {/* Right Column: About Section */}
        <Box sx={{ flex: '3', minWidth: 250 }}>
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