import React, { useState } from 'react';
import { Box, Typography, Paper, Tabs, Tab } from '@mui/material';
import ProviderKeyList from './ProviderKeyList';
import ProviderKeyCreateForm from './ProviderKeyCreateForm';

const ProviderKeyManager: React.FC = () => {
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
          <Tab label="My Provider API Keys" />
          <Tab label="Add New Key" />
        </Tabs>
      </Paper>

      {activeTab === 0 && (
        <ProviderKeyList key={refreshTrigger} />
      )}

      {activeTab === 1 && (
        <ProviderKeyCreateForm onSuccess={handleKeyCreated} />
      )}

      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant="h6" gutterBottom>
          About Provider API Keys
        </Typography>
        <Typography variant="body2" paragraph>
          Provider API keys allow you to use your personal API keys for services like Google AI (Gemini), 
          X.AI (Grok), GigaChat, and Perplexity (Sonar) when making requests through our gateway.
        </Typography>
        <Typography variant="body2" paragraph>
          By storing your own keys, you can:
        </Typography>
        <ul>
          <Typography component="li" variant="body2">
            Ensure your requests are billed to your own account with these providers
          </Typography>
          <Typography component="li" variant="body2">
            Use models or features that may not be enabled on our system's default keys
          </Typography>
          <Typography component="li" variant="body2">
            Prevent hitting rate limits that might be shared across other users
          </Typography>
        </ul>
        <Typography variant="body2" paragraph>
          Your API keys are encrypted before storage and securely managed.
        </Typography>
      </Paper>
    </Box>
  );
};

export default ProviderKeyManager;