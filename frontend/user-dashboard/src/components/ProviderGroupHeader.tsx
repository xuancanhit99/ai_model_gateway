import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Chip,
  IconButton,
  Badge,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import FolderDeleteIcon from '@mui/icons-material/FolderDelete';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

interface ProviderGroupHeaderProps {
  providerName: string;
  displayName: string;
  count: number;
  hasSelectedKey: boolean;
  isExpanded: boolean;
  onToggleExpand: (providerName: string) => void;
  onDeleteAll: (providerName: string) => void;
}

const ProviderGroupHeader: React.FC<ProviderGroupHeaderProps> = ({
  providerName,
  displayName,
  count,
  hasSelectedKey,
  isExpanded,
  onToggleExpand,
  onDeleteAll,
}) => {
  const { t } = useTranslation();

  const getProviderColor = (name: string) => {
    switch (name) {
      case 'google': return 'primary';
      case 'xai': return 'secondary';
      case 'gigachat': return 'success';
      case 'perplexity': return 'warning';
      default: return 'default';
    }
  };

  const providerColor = getProviderColor(providerName);

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        cursor: 'pointer'
      }}
      onClick={() => onToggleExpand(providerName)}
    >
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Chip
          label={displayName}
          color={providerColor}
          sx={{ mr: 2 }}
        />
        {hasSelectedKey && (
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
          badgeContent={count}
          color={providerColor}
          sx={{ mr: 1 }}
        >
          <IconButton
            size="small"
            color="error"
            onClick={(e) => {
              e.stopPropagation(); // Ngăn không cho event click lan đến parent
              onDeleteAll(providerName);
            }}
            aria-label={t('providerList.deleteAllButton', 'Delete All Keys')}
            disabled={count === 0} // Disable if no keys
          >
            <FolderDeleteIcon />
          </IconButton>
        </Badge>
        {isExpanded ? (
          <ExpandLessIcon />
        ) : (
          <ExpandMoreIcon />
        )}
      </Box>
    </Box>
  );
};

export default ProviderGroupHeader;