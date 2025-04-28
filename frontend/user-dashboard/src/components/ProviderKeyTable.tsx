import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Divider,
  TextField,
  InputAdornment,
  IconButton,
  TableContainer,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  CircularProgress,
  useTheme, // Import useTheme
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import CheckIcon from '@mui/icons-material/Check';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import CancelIcon from '@mui/icons-material/Cancel';
import AddIcon from '@mui/icons-material/Add'; // Import thêm AddIcon

// Interface ProviderKey sẽ được import hoặc định nghĩa ở cuối file

interface ProviderKeyTableProps {
  keys: ProviderKey[]; // Sử dụng interface ProviderKey được export ở dưới
  providerName: string;
  searchTerm: string;
  importing: boolean;
  fileInputRef: React.RefCallback<HTMLInputElement>; // Thay đổi từ RefObject sang RefCallback
  onSearchChange: (providerName: string, value: string) => void;
  onImportClick: (providerName: string, e: React.MouseEvent) => void;
  onFileChange: (providerName: string, e: React.ChangeEvent<HTMLInputElement>) => void;
  onSelectKey: (keyId: string, providerName: string, currentIsSelected: boolean) => void;
  onDeleteKey: (keyId: string, providerName: string) => void;
  onAddKeyClick: (providerName: string) => void; // Add new prop for handling Add Key click
}

const ProviderKeyTable: React.FC<ProviderKeyTableProps> = ({
  keys,
  providerName,
  searchTerm,
  importing,
  fileInputRef,
  onSearchChange,
  onImportClick,
  onFileChange,
  onSelectKey,
  onDeleteKey,
  onAddKeyClick, // Include the new prop
}) => {
  const { t } = useTranslation();
  const theme = useTheme(); // Khai báo sử dụng theme

  const getProviderColor = (name: string) => {
    switch (name) {
      case 'google': return 'primary';
      case 'xai': return 'secondary';
      case 'gigachat': return 'success';
      case 'perplexity': return 'warning';
      default: return 'primary'; // Default color for import button
    }
  };

  const providerColor = getProviderColor(providerName);

  return (
    <>
      <Divider />
      <Box sx={{ p: 2, pb: 1, display: 'flex', gap: 1 }}>
        <TextField
          fullWidth
          variant="outlined"
          size="small"
          placeholder={t('providerList.searchProvider', 'Search keys...')}
          value={searchTerm}
          onChange={(e) => onSearchChange(providerName, e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
        />
        {/* Nút Add Key */}
        <IconButton
          size="small"
          onClick={() => onAddKeyClick(providerName)}
          color={providerColor}
          sx={{ border: 1, borderColor: 'divider', p: 1 }}
        >
          <AddIcon />
        </IconButton>
        {/* Nút Import from CSV */}
        <IconButton
          size="small"
          onClick={(e) => onImportClick(providerName, e)}
          color={providerColor}
          disabled={importing}
          sx={{ border: 1, borderColor: 'divider', p: 1 }}
        >
          {importing
            ? <CircularProgress size={16} />
            : <InsertDriveFileIcon />}
        </IconButton>
        {/* Hidden file input cho import CSV */}
        <input
          type="file"
          accept=".csv,.txt"
          style={{ display: 'none' }}
          ref={fileInputRef} // Sử dụng ref được truyền vào
          onChange={(e) => onFileChange(providerName, e)}
        />
      </Box>
      <TableContainer sx={{ maxHeight: 300, overflow: 'auto' }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ 
                backgroundColor: theme.palette.mode === 'dark' 
                  ? theme.palette.background.paper 
                  : '#ffffff' 
              }}>{t('providerList.headerDescription', 'Description')}</TableCell>
              <TableCell sx={{ 
                backgroundColor: theme.palette.mode === 'dark' 
                  ? theme.palette.background.paper 
                  : '#ffffff' 
              }}>{t('providerList.headerCreated', 'Created')}</TableCell>
              <TableCell sx={{ 
                backgroundColor: theme.palette.mode === 'dark' 
                  ? theme.palette.background.paper 
                  : '#ffffff' 
              }} align="center">{t('providerList.headerDefault', 'Default')}</TableCell>
              <TableCell sx={{ 
                backgroundColor: theme.palette.mode === 'dark' 
                  ? theme.palette.background.paper 
                  : '#ffffff' 
              }} align="right">{t('providerList.headerActions', 'Actions')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {keys.map((key) => (
              <TableRow key={key.id}>
                <TableCell>{key.name || t('providerList.noDescription', 'No description')}</TableCell>
                <TableCell>{new Date(key.created_at).toLocaleString()}</TableCell>
                <TableCell align="center">
                  <IconButton
                    size="small"
                    onClick={() => onSelectKey(key.id, key.provider_name, key.is_selected)}
                    color={key.is_selected ? "primary" : "default"}
                  >
                    {key.is_selected ? <CheckIcon /> : <RadioButtonUncheckedIcon />}
                  </IconButton>
                </TableCell>
                <TableCell align="right">
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => onDeleteKey(key.id, key.provider_name)}
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
    </>
  );
};

export default ProviderKeyTable;

// Import interface ProviderKey từ component cha hoặc file types chung
import type { ProviderKey } from './ProviderKeyList'; // Giả sử import từ ProviderKeyList