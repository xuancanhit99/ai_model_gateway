import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Button,
  Box,
  CircularProgress,
  Typography,
  Alert
} from '@mui/material';

// ImportStats is imported from ProviderKeyList

interface ImportResultDialogProps {
  open: boolean;
  importing: boolean;
  providerDisplayName: string | null | undefined;
  importStats: ImportStats | null | undefined;
  onClose: () => void;
}

const ImportResultDialog: React.FC<ImportResultDialogProps> = ({
  open,
  importing,
  providerDisplayName,
  importStats,
  onClose,
}) => {
  const { t } = useTranslation();

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle>
        {importing
          ? t('providerList.importingTitle', 'Importing API Keys...')
          : t('providerList.importResultTitle', 'Import Results')}
      </DialogTitle>
      <DialogContent>
        {importing ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 2 }}>
            <CircularProgress sx={{ mb: 2 }} />
            <Typography>
              {t('providerList.importingMessage', 'Processing CSV file...')}
            </Typography>
          </Box>
        ) : (
          providerDisplayName && importStats && (
            <Box>
              <Typography variant="subtitle1" gutterBottom>
                {t('providerList.importResultSummary', 'Import Summary for {{provider}}', {
                  provider: providerDisplayName
                })}
              </Typography>

              <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
                <Box sx={{ textAlign: 'center', flex: 1 }}>
                  <Typography variant="h5">{importStats.total}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t('providerList.importResultTotal', 'Total Keys')}
                  </Typography>
                </Box>
                <Box sx={{ textAlign: 'center', flex: 1 }}>
                  <Typography variant="h5" color="success.main">{importStats.success}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t('providerList.importResultSuccess', 'Successfully Imported')}
                  </Typography>
                </Box>
                <Box sx={{ textAlign: 'center', flex: 1 }}>
                  <Typography variant="h5" color="error.main">{importStats.failed}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t('providerList.importResultFailed', 'Failed/Duplicate')}
                  </Typography>
                </Box>
              </Box>

              {importStats.failed > 0 && (
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
          onClick={onClose}
          color="primary"
          disabled={importing}
        >
          {t('action.close', 'Close')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ImportResultDialog;
// Import type ImportStats từ component cha hoặc file types chung
import type { ImportStats } from './ProviderKeyList'; // Giả sử import từ ProviderKeyList