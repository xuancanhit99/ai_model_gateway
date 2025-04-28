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

interface DeleteKeyConfirmationDialogProps {
  open: boolean;
  providerName: string | null | undefined; // Allow null/undefined for safety
  onClose: () => void;
  onConfirm: () => void;
}

const DeleteKeyConfirmationDialog: React.FC<DeleteKeyConfirmationDialogProps> = ({
  open,
  providerName,
  onClose,
  onConfirm,
}) => {
  const { t } = useTranslation();

  return (
    <Dialog
      open={open}
      onClose={onClose}
    >
      <DialogTitle>{t('providerList.deleteConfirmTitle')}</DialogTitle>
      <DialogContent>
        <DialogContentText>
          {t('providerList.deleteConfirmMessage', { provider: providerName || 'this provider' })}
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="primary">
          {t('action.cancel')}
        </Button>
        <Button onClick={onConfirm} color="secondary">
          {t('action.delete')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default DeleteKeyConfirmationDialog;