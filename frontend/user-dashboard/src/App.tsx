import { useState, useEffect, useCallback } from 'react';
import { supabase } from './supabaseClient';
import { Auth } from '@supabase/auth-ui-react';
import { ThemeSupa } from '@supabase/auth-ui-shared';
import type { Session } from '@supabase/supabase-js';
import ApiKeyList from './components/ApiKeyList';
import ApiKeyCreateForm from './components/ApiKeyCreateForm';
import ProviderKeyManager from './components/ProviderKeyManager';
import {
  Tabs, Tab, Box, ThemeProvider, CssBaseline, PaletteMode, AppBar, Toolbar, IconButton, Typography, Drawer, List, ListItem, ListItemButton, ListItemIcon, ListItemText, Divider, useTheme, useMediaQuery, Button, Container, Paper, Alert, Avatar, Tooltip // Import Avatar, Tooltip
} from '@mui/material'; // Import layout components
import MenuIcon from '@mui/icons-material/Menu'; // Import Menu icon
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft'; // Import ChevronLeftIcon
import LogoutIcon from '@mui/icons-material/Logout'; // Import Logout icon
import Brightness4Icon from '@mui/icons-material/Brightness4'; // Dark mode icon
import Brightness7Icon from '@mui/icons-material/Brightness7'; // Light mode icon
import KeyIcon from '@mui/icons-material/Key'; // Example icon
import VpnKeyIcon from '@mui/icons-material/VpnKey'; // Example icon
import { getAppTheme } from './theme';
import ErrorBoundary from './components/ErrorBoundary'; // Import ErrorBoundary
import './App.css';

// Kiểu dữ liệu cho theme (sử dụng PaletteMode từ MUI)
// type Theme = 'light' | 'dark'; // No longer needed, use PaletteMode

// No longer need the separate Dashboard component
// const drawerWidth = 240; // Defined below

const drawerWidth = 240;

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [themeMode, setThemeMode] = useState<PaletteMode>(() => {
    const storedTheme = localStorage.getItem('app-theme');
    return (storedTheme === 'light' || storedTheme === 'dark') ? storedTheme : 'dark';
  });
  const muiTheme = getAppTheme(themeMode);
  const isMobile = useMediaQuery(muiTheme.breakpoints.down('md'));
  const [drawerOpen, setDrawerOpen] = useState(!isMobile);
  const [activeView, setActiveView] = useState<'gateway' | 'provider'>('gateway');
  const [refreshGatewayCounter, setRefreshGatewayCounter] = useState(0); // State to refresh gateway list

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

  // Hàm chuyển đổi theme mode
  const toggleTheme = () => {
    setThemeMode(prevMode => (prevMode === 'light' ? 'dark' : 'light'));
  };

  if (loading && !session) { // Show loading only when checking session initially
     // Basic loading indicator, can be replaced with MUI Skeleton later
    return (
        <ThemeProvider theme={muiTheme}>
            <CssBaseline />
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <Typography>Loading...</Typography>
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
          <Box sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', p: 2 }}> {/* Added flexDirection and padding */}
             {/* Add Header for Login Page */}
             <Typography variant="h4" component="h1" gutterBottom color="primary" sx={{ mb: 4 }}> {/* Added margin bottom */}
                AI Gateway
             </Typography>
            <Box sx={{ maxWidth: '400px', width: '100%' }}> {/* Removed padding here, added to parent */}
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
            <Alert severity="error">Error: Supabase client not initialized.</Alert>
          </Container>
        )
      ) : (
        // --- Logged In View (With Drawer and Main Content) ---
        <>
          {/* Menu button positioned fixed top-left (only when logged in) */}
          <IconButton
            color="inherit" // Will inherit color from theme's text.primary
            aria-label="toggle drawer"
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
                  backgroundColor: muiTheme.palette.background.paper, // Ensure consistent background
                },
              }}
            >
              {/* Drawer Header */}
              <Toolbar sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 1 }}>
                <Typography variant="h6" noWrap component="div" color="primary">
                  AI Gateway
                </Typography>
              </Toolbar>
              <Divider />

              {/* Navigation List */}
              <List sx={{ px: 1 }}>
                <ListItem key="Gateway Keys" disablePadding sx={{ display: 'block', my: 0.5 }}>
                  <ListItemButton
                    selected={activeView === 'gateway'}
                    onClick={() => { setActiveView('gateway'); handleDrawerClose(); }}
                    sx={{
                      borderRadius: '24px',
                      '&.Mui-selected': {
                        backgroundColor: muiTheme.palette.action.selected,
                        '&:hover': {
                          backgroundColor: muiTheme.palette.action.hover,
                        },
                      },
                      py: 1,
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: '40px' }}><KeyIcon color={activeView === 'gateway' ? 'primary' : 'inherit'} /></ListItemIcon>
                    <ListItemText primary="Gateway Keys" />
                  </ListItemButton>
                </ListItem>
                <ListItem key="Provider Keys" disablePadding sx={{ display: 'block', my: 0.5 }}>
                  <ListItemButton
                    selected={activeView === 'provider'}
                    onClick={() => { setActiveView('provider'); handleDrawerClose(); }}
                    sx={{
                      borderRadius: '24px',
                      '&.Mui-selected': {
                        backgroundColor: muiTheme.palette.action.selected,
                        '&:hover': {
                          backgroundColor: muiTheme.palette.action.hover,
                        },
                      },
                      py: 1,
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: '40px' }}><VpnKeyIcon color={activeView === 'provider' ? 'primary' : 'inherit'} /></ListItemIcon>
                    <ListItemText primary="Provider Keys" />
                  </ListItemButton>
                </ListItem>
              </List>

              {/* Spacer */}
              <Box sx={{ flexGrow: 1 }} />

              {/* User Info / Logout */}
              <Box sx={{ p: 2 }}>
                <Divider sx={{ mb: 1 }} />
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', overflow: 'hidden' }}>
                    <Avatar sx={{ width: 32, height: 32, mr: 1, bgcolor: 'primary.main' }}>
                      {session.user.email ? session.user.email[0].toUpperCase() : '?'}
                    </Avatar>
                    <Typography variant="body2" noWrap sx={{ flexShrink: 1 }}>
                      {session.user.email}
                    </Typography>
                  </Box>
                  <Tooltip title="Sign Out">
                    <IconButton onClick={() => supabase?.auth.signOut()} size="small">
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
                  {activeView === 'gateway' ? 'Gateway API Keys' : 'Provider API Keys'}
                </Typography>
                <Box>
                  <IconButton sx={{ ml: 1 }} onClick={toggleTheme} color="inherit" title={`Switch to ${themeMode === 'light' ? 'Dark' : 'Light'} Mode`}>
                    {themeMode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
                  </IconButton>
                </Box>
              </Box>

              {/* Main Content Area Wrapped in Error Boundary */}
              <ErrorBoundary>
                <Container maxWidth="lg" sx={{ px: 3, mb: 4 }}>
                  {activeView === 'gateway' && (
                    <>
                      <Typography variant="body1" gutterBottom sx={{ mb: 3 }}>
                        Manage API keys for accessing the AI Model Gateway.
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
    </ThemeProvider>
  );
}

export default App;
