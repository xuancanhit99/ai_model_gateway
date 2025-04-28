import React from 'react';
import { useTranslation } from 'react-i18next';
import { Box, Paper, Typography } from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';

const AboutProviderKeys: React.FC = () => {
  const { t } = useTranslation();

  return (
    <Paper
      sx={{
        p: 3,
        height: '100%',
        backgroundColor: 'info.dark', // Màu xanh dương đậm
        color: 'white',
        '& ul': {
          color: 'white'
        },
        boxShadow: 3
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <InfoIcon sx={{ mr: 1 }} />
        <Typography variant="h6" component="h2">
          {t('providerView.aboutTitle')}
        </Typography>
      </Box>

      <Typography variant="body2" paragraph sx={{ opacity: 0.9, fontSize: '0.85rem' }}>
        {t('providerView.aboutIntro')}
      </Typography>

      <Typography variant="body2" paragraph sx={{ mt: 1.5, fontWeight: 'medium', fontSize: '0.85rem' }}>
        {t('providerView.aboutBenefitsTitle')}
      </Typography>

      <Box component="ul" sx={{ mt: 0, pl: 2 }}>
        <Typography component="li" variant="body2" sx={{ mb: 0.75, fontSize: '0.8rem' }}>
          {t('providerView.aboutBenefit1')}
        </Typography>
        <Typography component="li" variant="body2" sx={{ mb: 0.75, fontSize: '0.8rem' }}>
          {t('providerView.aboutBenefit2')}
        </Typography>
        <Typography component="li" variant="body2" sx={{ fontSize: '0.8rem' }}>
          {t('providerView.aboutBenefit3')}
        </Typography>
      </Box>

      <Typography
        variant="body2"
        paragraph
        sx={{
          mt: 1.5,
          fontStyle: 'italic',
          borderTop: '1px solid rgba(255, 255, 255, 0.3)',
          pt: 1,
          fontSize: '0.8rem'
        }}
      >
        {t('providerView.aboutSecurity')}
      </Typography>
    </Paper>
  );
};

export default AboutProviderKeys;