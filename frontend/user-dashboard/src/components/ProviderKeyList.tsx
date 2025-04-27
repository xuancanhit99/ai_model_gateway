import React, { useState, useEffect } from 'react';
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
  const [providerKeys, setProviderKeys] = useState<ProviderKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchProviderKeys = async () => {
    try {
      setLoading(true);
      setError(null);
      
      if (!supabase) {
        throw new Error('Supabase client not initialized');
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
      setError(`Error fetching provider keys: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProviderKeys();
  }, []);

  const handleSelectKey = async (keyId: string, providerName: string) => {
    try {
      setError(null);
      
      if (!supabase) {
        throw new Error('Supabase client not initialized');
      }
      
      // First unselect all keys for this provider (not needed but safer)
      await supabase
        .from('user_provider_keys')
        .update({ is_selected: false })
        .eq('provider_name', providerName);
      
      // Then select this key
      const { error } = await supabase
        .from('user_provider_keys')
        .update({ is_selected: true })
        .eq('id', keyId);
      
      if (error) throw error;
      
      setSuccessMessage(`Successfully selected key for ${providerDisplayNames[providerName] || providerName}`);
      setTimeout(() => setSuccessMessage(null), 3000);
      
      // Refresh the list
      fetchProviderKeys();
    } catch (error: any) {
      console.error('Error selecting provider key:', error);
      setError(`Error selecting key: ${error.message}`);
    }
  };

  const handleDeleteKey = async (keyId: string, providerName: string) => {
    if (!window.confirm(`Are you sure you want to delete this ${providerDisplayNames[providerName] || providerName} API key?`)) {
      return;
    }
    
    try {
      setError(null);
      
      if (!supabase) {
        throw new Error('Supabase client not initialized');
      }
      
      const { error } = await supabase
        .from('user_provider_keys')
        .delete()
        .eq('id', keyId);
      
      if (error) throw error;
      
      setSuccessMessage(`Successfully deleted ${providerDisplayNames[providerName] || providerName} API key`);
      setTimeout(() => setSuccessMessage(null), 3000);
      
      // Refresh the list
      fetchProviderKeys();
    } catch (error: any) {
      console.error('Error deleting provider key:', error);
      setError(`Error deleting key: ${error.message}`);
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
      <Typography variant="h6" gutterBottom>
        Manage Provider API Keys
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
          You haven't added any provider API keys yet. Add your own keys to use them instead of the system defaults.
        </Alert>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Provider</TableCell>
                <TableCell>Description</TableCell>
                <TableCell>Created</TableCell>
                <TableCell align="center">Default</TableCell>
                <TableCell align="right">Actions</TableCell>
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
                  <TableCell>{key.name || 'No description'}</TableCell>
                  <TableCell>{new Date(key.created_at).toLocaleString()}</TableCell>
                  <TableCell align="center">
                    <IconButton 
                      size="small" 
                      onClick={() => handleSelectKey(key.id, key.provider_name)}
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