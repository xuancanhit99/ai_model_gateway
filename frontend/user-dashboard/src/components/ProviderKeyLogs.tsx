import React, { useState, useMemo } from 'react'; // Import useState and useMemo
import { useTranslation } from 'react-i18next';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  Chip,
  TextField, // Import TextField
  InputAdornment, // Import InputAdornment
  useTheme, // Import useTheme hook
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search'; // Import SearchIcon

// Import interface ProviderKeyLog từ component cha hoặc file types chung
import type { ProviderKeyLog } from './ProviderKeyList'; // Giả sử import từ ProviderKeyList

interface ProviderKeyLogsProps {
  logs: ProviderKeyLog[];
  loading: boolean;
}

const ProviderKeyLogs: React.FC<ProviderKeyLogsProps> = ({ logs, loading }) => {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState(''); // State for search term
  const theme = useTheme(); // Lấy theme hiện tại

  // Filter logs based on search term (case-insensitive search in description)
  const filteredLogs = useMemo(() => {
    if (!searchTerm.trim()) {
      return logs;
    }
    const lowerCaseSearchTerm = searchTerm.toLowerCase();
    return logs.filter(log =>
      log.description.toLowerCase().includes(lowerCaseSearchTerm)
    );
  }, [logs, searchTerm]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" my={2}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  return (
    <Box>
      {/* Search Input */}
      <Box sx={{ mb: 2 }}>
        <TextField
          fullWidth
          variant="outlined"
          size="small"
          placeholder={t('providerLogs.searchPlaceholder', 'Search logs by description...')}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
        />
      </Box>

      {/* Logs Table */}
      {filteredLogs.length === 0 ? (
         <Alert severity="info">
           {searchTerm.trim()
             ? t('providerLogs.noResults', 'No logs found matching your search.')
             : t('providerLogs.noLogs', 'No recent activity with provider keys.')}
         </Alert>
       ) : (
        <TableContainer component={Paper} sx={{ maxHeight: 400 }}> {/* Increased height from 250px to 400px */}
          <Table size="small" stickyHeader> {/* Add stickyHeader */}
            <TableHead>
              <TableRow>
                <TableCell sx={{ 
                  backgroundColor: theme.palette.mode === 'dark' 
                    ? theme.palette.background.paper 
                    : '#ffffff' 
                }}>{t('providerLogs.action', 'Action')}</TableCell>
                <TableCell sx={{ 
                  backgroundColor: theme.palette.mode === 'dark' 
                    ? theme.palette.background.paper 
                    : '#ffffff' 
                }}>{t('providerLogs.description', 'Description')}</TableCell>
                <TableCell sx={{ 
                  backgroundColor: theme.palette.mode === 'dark' 
                    ? theme.palette.background.paper 
                    : '#ffffff' 
                }}>{t('providerLogs.time', 'Time')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredLogs.map((log) => (
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
       )}
    </Box>
  );
};

export default ProviderKeyLogs;

// Không cần export type ở đây nữa