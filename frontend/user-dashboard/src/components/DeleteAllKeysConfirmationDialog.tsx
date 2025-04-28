import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Button
} from '@mui/material';

interface DeleteAllKeysConfirmationDialogProps {
  open: boolean;
  providerDisplayName: string | null | undefined; // Use display name for clarity
  onClose: () => void;
  onConfirm: () => void;
}

const DeleteAllKeysConfirmationDialog: React.FC<DeleteAllKeysConfirmationDialogProps> = ({
  open,
  providerDisplayName,
  onClose,
  onConfirm,
}) => {
  const { t } = useTranslation();

  return (
    <Dialog
      open={open}
      onClose={onClose}
    >
      <DialogTitle>{t('providerList.deleteAllConfirmTitle')}</DialogTitle>
      <DialogContent>
        <DialogContentText>
          {t('providerList.deleteAllConfirmMessage', {
            provider: providerDisplayName || 'this provider'
          })}
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="primary">
          {t('action.cancel', 'Cancel')}
        </Button>
        <Button onClick={onConfirm} color="secondary">
          {t('action.deleteAll', 'Delete All')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default DeleteAllKeysConfirmationDialog;