import React, { useState } from 'react';
import { useTranslation } from 'react-i18next'; // Import useTranslation
import { 
  Box, 
  Paper, 
  Tabs, 
  Tab
} from '@mui/material';
import ProviderKeyList from './ProviderKeyList';
import ProviderKeyCreateForm from './ProviderKeyCreateForm';

const ProviderKeyManager: React.FC = () => {
  const { t } = useTranslation(); // Use the hook
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [activeTab, setActiveTab] = useState(0);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleKeyCreated = () => {
    // Trigger a refresh of the key list
    setRefreshTrigger(prev => prev + 1);
    // Switch to the list tab
    setActiveTab(0);
  };

  return (
    <Box sx={{ my: 4 }}>
      <Paper sx={{ mb: 3 }}>
        <Tabs 
          value={activeTab} 
          onChange={handleTabChange}
          indicatorColor="primary"
          textColor="primary"
          centered
        >
          {/* Use translation for tab labels */}
          <Tab label={t('providerList.title')} />
          <Tab label={t('providerCreateForm.title')} />
        </Tabs>
      </Paper>

      {activeTab === 0 && (
        <ProviderKeyList key={refreshTrigger} />
      )}

      {activeTab === 1 && (
        <ProviderKeyCreateForm onSuccess={handleKeyCreated} />
      )}
    </Box>
  );
};

export default ProviderKeyManager;