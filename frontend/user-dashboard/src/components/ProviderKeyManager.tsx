import React from 'react';
import { 
  Box, 
  Paper,
} from '@mui/material';
import ProviderKeyList from './ProviderKeyList';

const ProviderKeyManager: React.FC = () => {
  return (
    <Box sx={{ my: 4 }}>
      <Paper sx={{ p: 3 }}>
        <ProviderKeyList />
      </Paper>
    </Box>
  );
};

export default ProviderKeyManager;