import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Toaster } from 'react-hot-toast';
import { supabase } from './supabaseClient';
import { Auth } from '@supabase/auth-ui-react';
import { ThemeSupa } from '@supabase/auth-ui-shared';
import type { Session } from '@supabase/supabase-js';
import ApiKeyList from './components/ApiKeyList';
import ApiKeyCreateForm from './components/ApiKeyCreateForm';
import ProviderKeyManager from './components/ProviderKeyManager';
import {
  Box, ThemeProvider, CssBaseline, PaletteMode, Toolbar, IconButton, Typography, Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Divider, useMediaQuery, Container, Paper, Alert, Avatar, Tooltip, Menu, MenuItem, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import LogoutIcon from '@mui/icons-material/Logout';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import TranslateIcon from '@mui/icons-material/Translate';
import KeyIcon from '@mui/icons-material/Key';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import { getAppTheme } from './theme';
import ErrorBoundary from './components/ErrorBoundary';
import HyperLogo from './assets/Hyper.svg'; // Import Hyper logo
import './App.css';

// Kiểu dữ liệu cho theme (sử dụng PaletteMode từ MUI)
// type Theme = 'light' | 'dark'; // No longer needed, use PaletteMode

// No longer need the separate Dashboard component
// const drawerWidth = 240; // Defined below

const drawerWidth = 240;

function App() {
  const { t, i18n } = useTranslation(); // Use the hook
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [themeMode, setThemeMode] = useState<PaletteMode>(() => {
    const storedTheme = localStorage.getItem('app-theme');
    return (storedTheme === 'light' || storedTheme === 'dark') ? storedTheme : 'dark';
  });
  const muiTheme = getAppTheme(themeMode);
  const isMobile = useMediaQuery(muiTheme.breakpoints.down('md'));
  const [drawerOpen, setDrawerOpen] = useState(!isMobile);
  const [activeView, setActiveView] = useState<'gateway' | 'provider'>('provider'); // Đổi từ 'gateway' thành 'provider'
  const [refreshGatewayCounter, setRefreshGatewayCounter] = useState(0); // State to refresh gateway list
  const [languageMenuAnchorEl, setLanguageMenuAnchorEl] = useState<null | HTMLElement>(null); // State for language menu anchor
  // Thêm state mới cho dialog đăng xuất
  const [logoutDialogOpen, setLogoutDialogOpen] = useState(false);

  // Callback for Gateway key creation
  const handleGatewayKeyCreated = useCallback(() => {
    console.log("New gateway key created, triggering list refresh...");
    setRefreshGatewayCounter(prev => prev + 1);
  }, []);

  // Toggle drawer state
  const handleDrawerToggle = () => {
    setDrawerOpen(!drawerOpen);
  };

  // Close drawer on mobile after item click (optional)
  const handleDrawerClose = () => {
    if (isMobile) {
      setDrawerOpen(false);
    }
  };

  // Effect to handle initial drawer state based on screen size
  useEffect(() => {
    setDrawerOpen(!isMobile);
  }, [isMobile]);


  // Effect to get session
  useEffect(() => {
    setLoading(true); // Bắt đầu loading khi effect chạy
    supabase?.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      // setLoading(false); // Chuyển setLoading vào cuối effect để đảm bảo theme được áp dụng
    }).catch(error => {
      console.error("Error getting session:", error);
      // setLoading(false);
    });

    const { data: { subscription } } = supabase?.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
      }
    ) ?? { data: { subscription: null } };

    return () => {
      subscription?.unsubscribe();
    };
  }, []);

  // Effect để lưu theme mode vào localStorage
  useEffect(() => {
    localStorage.setItem('app-theme', themeMode); // Lưu lựa chọn mode
    // Không cần áp class vào body nữa, ThemeProvider và CssBaseline sẽ xử lý
    setLoading(false); // Kết thúc loading
  }, [themeMode]); // Chạy lại khi themeMode thay đổi

  // Effect to save language to localStorage - No longer needed, LanguageDetector handles this
  // useEffect(() => {
  //   localStorage.setItem('app-language', language);
  //   // TODO: Integrate with i18n library here to actually change the language
  //   console.log(`App language set to: ${language}`); // Placeholder log
  // }, [language]);

  // Hàm chuyển đổi theme mode
  const toggleTheme = () => {
    setThemeMode(prevMode => (prevMode === 'light' ? 'dark' : 'light'));
  };

  // --- Language Menu Handlers ---
  const handleLanguageMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setLanguageMenuAnchorEl(event.currentTarget);
  };

  const handleLanguageMenuClose = () => {
    setLanguageMenuAnchorEl(null);
  };

  const changeLanguage = (lang: 'en' | 'vi') => {
    i18n.changeLanguage(lang);
    handleLanguageMenuClose();
  };
  // --- End Language Menu Handlers ---

  // --- Logout Dialog Handlers ---
  const handleLogoutDialogOpen = () => {
    setLogoutDialogOpen(true);
  };

  const handleLogoutDialogClose = () => {
    setLogoutDialogOpen(false);
  };

  const handleLogout = () => {
    supabase?.auth.signOut();
    setLogoutDialogOpen(false);
  };
  // --- End Logout Dialog Handlers ---

  // Function to toggle language using i18next - Replaced by menu
  // const toggleLanguage = () => {
  //   const newLang = i18n.language === 'en' ? 'vi' : 'en';
  //   i18n.changeLanguage(newLang);
  // };

  if (loading && !session) { // Show loading only when checking session initially
     // Basic loading indicator, can be replaced with MUI Skeleton later
    return (
        <ThemeProvider theme={muiTheme}>
            <CssBaseline />
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <Typography>{t('loading')}</Typography> {/* Use translation */}
            </Box>
        </ThemeProvider>
    );
  }


  return (
    <ThemeProvider theme={muiTheme}>
      <CssBaseline />
      {!session ? (
        // --- Auth View (No Drawer) ---
        supabase ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', p: 2 }}>
             {/* Add Logo and Header for Login Page */}
             <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 4 }}>
                <img src={HyperLogo} alt="Hyper Logo" style={{ height: '80px', marginBottom: '16px' }} />
                <Typography variant="h4" component="h1" gutterBottom color="primary">
                  {t('appTitle')}
                </Typography>
             </Box>
            <Box sx={{ maxWidth: '400px', width: '100%' }}>
              <Auth
                supabaseClient={supabase}
                appearance={{ theme: ThemeSupa }}
                providers={['google', 'github']}
                theme={themeMode}
              />
            </Box>
          </Box>
        ) : (
          <Container maxWidth="lg" sx={{ px: 3, pt: 5 }}> {/* Add padding top */}
            <Alert severity="error">{t('authError')}</Alert> {/* Use translation */}
          </Container>
        )
      ) : (
        // --- Logged In View (With Drawer and Main Content) ---
        <>
          {/* Menu button positioned fixed top-left (only when logged in) */}
          <IconButton
           color="inherit" // Will inherit color from theme's text.primary
           aria-label={t('toggleDrawer')} // Use translation
           edge="start"
           onClick={handleDrawerToggle}
            sx={{
              position: 'fixed', // Fix position
              top: 16, // Adjust position as needed
              left: 16,
              zIndex: (theme) => theme.zIndex.drawer + 2, // Ensure it's above AppBar/Drawer content
              display: { xs: 'inline-flex', md: 'none' } // Show only on mobile/tablet where drawer is temporary
            }}
          >
            <MenuIcon />
          </IconButton>

          <Box sx={{ display: 'flex' }}>
            {/* Drawer (only when logged in) */}
            <Drawer
              variant={isMobile ? "temporary" : "persistent"}
              open={drawerOpen}
              onClose={handleDrawerClose}
              ModalProps={{ keepMounted: true }}
              sx={{
                width: drawerWidth,
                flexShrink: 0,
                [`& .MuiDrawer-paper`]: {
                  width: drawerWidth,
                  boxSizing: 'border-box',
                  borderRight: 'none', // Remove border to match Figma
                  backgroundColor: themeMode === 'light' ? 'info.dark' : muiTheme.palette.background.paper, // Đổi từ primary.light sang info.dark cho chế độ sáng
                  color: themeMode === 'light' ? 'common.white' : 'inherit', // Text màu trắng trong light mode
                },
              }}
            >
              {/* Drawer Header */}
              <Toolbar sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', mb: 1, pt: 2 }}>
                <img src={HyperLogo} alt="Hyper Logo" style={{ height: '50px', marginBottom: '12px' }} />
                <Typography 
                  variant="h6" 
                  noWrap 
                  component="div" 
                  color={themeMode === 'light' ? 'common.white' : 'primary'}
                  sx={{ fontWeight: 'bold' }}
                >
                  {t('appTitle')}
                </Typography>
              </Toolbar>
              <Divider sx={{ 
                borderColor: themeMode === 'light' ? 'rgba(255, 255, 255, 0.2)' : undefined 
              }} />

              {/* Navigation List */}
              <List sx={{ px: 1 }}>
                <ListItem key="Provider Keys" disablePadding sx={{ display: 'block', my: 0.5 }}>
                  <ListItemButton
                    selected={activeView === 'provider'}
                    onClick={() => { setActiveView('provider'); handleDrawerClose(); }}
                    sx={{
                      borderRadius: '24px',
                      color: themeMode === 'light' ? 'white' : undefined,
                      '&.Mui-selected': {
                        backgroundColor: themeMode === 'light' ? 'rgba(255, 255, 255, 0.15)' : muiTheme.palette.action.selected,
                        '&:hover': {
                          backgroundColor: themeMode === 'light' ? 'rgba(255, 255, 255, 0.25)' : muiTheme.palette.action.hover,
                        },
                      },
                      '&:hover': {
                        backgroundColor: themeMode === 'light' ? 'rgba(255, 255, 255, 0.1)' : undefined,
                      },
                      py: 1,
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: '40px', color: themeMode === 'light' ? 'white' : undefined }}><VpnKeyIcon color={activeView === 'provider' && themeMode !== 'light' ? 'primary' : 'inherit'} /></ListItemIcon>
                    <ListItemText primary={t('menu.providerKeys')} />
                  </ListItemButton>
                </ListItem>
                <ListItem key="Gateway Keys" disablePadding sx={{ display: 'block', my: 0.5 }}>
                  <ListItemButton
                    selected={activeView === 'gateway'}
                    onClick={() => { setActiveView('gateway'); handleDrawerClose(); }}
                    sx={{
                      borderRadius: '24px',
                      color: themeMode === 'light' ? 'white' : undefined,
                      '&.Mui-selected': {
                        backgroundColor: themeMode === 'light' ? 'rgba(255, 255, 255, 0.15)' : muiTheme.palette.action.selected,
                        '&:hover': {
                          backgroundColor: themeMode === 'light' ? 'rgba(255, 255, 255, 0.25)' : muiTheme.palette.action.hover,
                        },
                      },
                      '&:hover': {
                        backgroundColor: themeMode === 'light' ? 'rgba(255, 255, 255, 0.1)' : undefined,
                      },
                      py: 1,
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: '40px', color: themeMode === 'light' ? 'white' : undefined }}><KeyIcon color={activeView === 'gateway' && themeMode !== 'light' ? 'primary' : 'inherit'} /></ListItemIcon>
                    <ListItemText primary={t('menu.gatewayKeys')} />
                  </ListItemButton>
                </ListItem>
              </List>

              {/* Spacer */}
              <Box sx={{ flexGrow: 1 }} />

              {/* User Info / Logout */}
              <Box sx={{ p: 2 }}>
                <Divider sx={{ 
                  mb: 1,
                  borderColor: themeMode === 'light' ? 'rgba(255, 255, 255, 0.2)' : undefined 
                }} />
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', overflow: 'hidden' }}>
                    <Avatar sx={{ 
                      width: 32, 
                      height: 32, 
                      mr: 1, 
                      bgcolor: themeMode === 'light' ? 'primary.light' : 'primary.main',
                      color: themeMode === 'light' ? 'text.primary' : 'white' // Thêm màu tối cho chữ cái
                    }}>
                      {session.user.email ? session.user.email[0].toUpperCase() : '?'}
                    </Avatar>
                    <Typography variant="body2" noWrap sx={{ flexShrink: 1, color: themeMode === 'light' ? 'white' : undefined }}>
                      {session.user.email}
                    </Typography>
                  </Box>
                  <Tooltip title={t('userInfo.signOut')}>
                    <IconButton 
                      onClick={handleLogoutDialogOpen} 
                      size="small" 
                      sx={{ color: themeMode === 'light' ? 'white' : undefined }}
                    >
                      <LogoutIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>
            </Drawer>

            {/* Main Content Area (only when logged in) */}
            <Box
              component="main"
              sx={{
                flexGrow: 1,
                p: 3,
                width: { md: `calc(100% - ${drawerWidth}px)` },
                transition: (theme) => theme.transitions.create('margin', {
                  easing: theme.transitions.easing.sharp,
                  duration: theme.transitions.duration.leavingScreen,
                }),
                marginLeft: { md: `-${drawerWidth}px` },
                ...(drawerOpen && !isMobile && {
                  transition: (theme) => theme.transitions.create('margin', {
                    easing: theme.transitions.easing.easeOut,
                    duration: theme.transitions.duration.enteringScreen,
                  }),
                  marginLeft: { md: 0 },
                }),
                pt: 4, // Keep padding top for content spacing
              }}
            >
              {/* Header integrated into Main Content */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, px: 3 }}>
                <Typography variant="h4" component="h1">
                  {activeView === 'gateway' ? t('header.gatewayApiKeys') : t('header.providerApiKeys')}
                </Typography>
                <Box>
                  {/* Language Menu Button */}
                  <Tooltip title={t('header.changeLanguage', 'Change Language')}>
                    {/* Removed comment inside Tooltip to fix TS error */}
                    <IconButton
                      sx={{ ml: 1 }}
                      onClick={handleLanguageMenuOpen}
                      color="inherit"
                      aria-controls={languageMenuAnchorEl ? 'language-menu' : undefined}
                      aria-haspopup="true"
                      aria-expanded={languageMenuAnchorEl ? 'true' : undefined}
                    >
                      <TranslateIcon />
                    </IconButton>
                  </Tooltip>
                  <Menu
                    id="language-menu"
                    anchorEl={languageMenuAnchorEl}
                    open={Boolean(languageMenuAnchorEl)}
                    onClose={handleLanguageMenuClose}
                    MenuListProps={{
                      'aria-labelledby': 'language-button',
                    }}
                  >
                    <MenuItem onClick={() => changeLanguage('en')} selected={i18n.language === 'en'}>English</MenuItem>
                    <MenuItem onClick={() => changeLanguage('vi')} selected={i18n.language === 'vi'}>Tiếng Việt</MenuItem>
                  </Menu>
                  {/* Theme Toggle Button */}
                  <Tooltip title={t(themeMode === 'light' ? 'header.switchToDark' : 'header.switchToLight')}>
                    <IconButton sx={{ ml: 1 }} onClick={toggleTheme} color="inherit">
                      {themeMode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>

              {/* Main Content Area Wrapped in Error Boundary */}
              <ErrorBoundary>
                <Container maxWidth="lg" sx={{ px: 3, mb: 4 }}>
                  {activeView === 'gateway' && (
                    <>
                      <Typography variant="body1" gutterBottom sx={{ mb: 3 }}>
                        {t('gatewayView.description')}
                      </Typography>
                      <Paper elevation={0} variant="outlined" sx={{ p: 3 }}>
                        <ApiKeyList refreshTrigger={refreshGatewayCounter} session={session} onListChange={handleGatewayKeyCreated} />
                        <Divider sx={{ my: 3 }} />
                        <ApiKeyCreateForm onKeyCreated={handleGatewayKeyCreated} />
                      </Paper>
                    </>
                  )}
                  {activeView === 'provider' && (
                    <>
                      <ProviderKeyManager />
                    </>
                  )}
                </Container>
              </ErrorBoundary>
            </Box> {/* End Main Content Box */}
          </Box> {/* End Flex Container */}
        </>
      )}
      <Toaster
        position="top-right" // Changed position to top-right
        reverseOrder={false}
        toastOptions={{
          // Define default options for all toasts
          duration: 5000, // 5 seconds for all toast types
          // style: {
          //   background: '#363636',
          //   color: '#fff',
          // },

          // Define options for specific types
          success: {
            style: {
              background: themeMode === 'light' ? '#27ae60' : '#abebc6', // Green background based on theme
              color: themeMode === 'light' ? '#FFFFFF' : '#1d6f42', // Text color based on theme
            },
            iconTheme: { // Optional: style the default checkmark icon
                primary: themeMode === 'light' ? '#FFFFFF' : '#1d6f42', // Icon color matches text
                secondary: themeMode === 'light' ? '#27ae60' : '#abebc6', // Icon background matches toast background
            },
          },
          error: {
            // You could define specific styles for error toasts here too
            // style: {
            //   background: muiTheme.palette.error.main,
            //   color: muiTheme.palette.error.contrastText,
            // },
          },
        }}
      />

      {/* Logout Confirmation Dialog */}
      <Dialog
        open={logoutDialogOpen}
        onClose={handleLogoutDialogClose}
        aria-labelledby="logout-dialog-title"
        aria-describedby="logout-dialog-description"
      >
        <DialogTitle id="logout-dialog-title">
          {t('logout.confirmTitle', 'Xác nhận đăng xuất')}
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="logout-dialog-description">
            {t('logout.confirmMessage', 'Bạn có chắc chắn muốn đăng xuất khỏi ứng dụng?')}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleLogoutDialogClose} color="primary">
            {t('logout.cancel', 'Hủy')}
          </Button>
          <Button onClick={handleLogout} color="primary" autoFocus>
            {t('logout.confirm', 'Đăng xuất')}
          </Button>
        </DialogActions>
      </Dialog>
    </ThemeProvider>
  );
}

export default App;
