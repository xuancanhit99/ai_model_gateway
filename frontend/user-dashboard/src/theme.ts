import { createTheme, ThemeOptions } from '@mui/material/styles'; // Import ThemeOptions
import { PaletteMode } from '@mui/material'; // Import PaletteMode separately
import { deepmerge } from '@mui/utils'; // Import deepmerge

// --- Base Theme Configuration ---
const baseThemeOptions: ThemeOptions = { // Explicitly type baseThemeOptions
  typography: {
    fontFamily: '"Averta", "Poppins", "Helvetica", "Arial", sans-serif', // Use Averta first
    h1: { fontWeight: 700 },
    h2: { fontWeight: 700 },
    h3: { fontWeight: 500 },
    h4: { fontWeight: 500 },
    h5: { fontWeight: 500 },
    h6: { fontWeight: 500 },
    button: {
      textTransform: 'none', // Keep button text case as defined
      fontWeight: 500,
    },
  },
  shape: {
    borderRadius: 8, // Slightly rounded corners
  },
  // --- Component Overrides (Optional - Add as needed) ---
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          // Example: Add slight shadow on hover
          // '&:hover': {
          //   boxShadow: '0px 2px 4px -1px rgba(0,0,0,0.2), 0px 4px 5px 0px rgba(0,0,0,0.14), 0px 1px 10px 0px rgba(0,0,0,0.12)',
          // },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          // Add subtle background pattern or keep plain
        },
      },
      defaultProps: {
        elevation: 1, // Default elevation for Paper components
      }
    },
    MuiAppBar: {
        styleOverrides: {
            root: {
                // Remove default box-shadow if using border or other styles
                boxShadow: 'none',
                borderBottom: '1px solid', // Add a subtle border
            }
        }
    },
    MuiDrawer: {
        styleOverrides: {
            paper: {
                borderRight: '1px solid', // Add border to Drawer paper
                // Background color will be set per theme below
            }
        }
    }
    // Add overrides for other components like Card, TextField, etc.
  },
};

// --- Light Theme Palette (Material 3 Inspired) ---
const lightPalette = {
  mode: 'light' as PaletteMode,
  primary: {
    main: '#6750A4', // M3 Primary
    light: '#EADDFF', // M3 Primary Container
    dark: '#4F378B', // Darker shade for contrast
    contrastText: '#FFFFFF', // Text on Primary
  },
  secondary: {
    main: '#625B71', // M3 Secondary
    light: '#E8DEF8', // M3 Secondary Container
    dark: '#4A4458', // Darker shade
    contrastText: '#FFFFFF', // Text on Secondary
  },
  error: {
    main: '#B3261E', // M3 Error
    light: '#F9DEDC', // M3 Error Container
    contrastText: '#FFFFFF',
  },
  warning: {
    main: '#ffab40', // Material Design Warning
    light: '#fff8e1',
    contrastText: 'rgba(0, 0, 0, 0.87)',
  },
  info: {
    main: '#2196f3', // Material Design Info
    light: '#e3f2fd',
    contrastText: '#FFFFFF',
  },
  success: {
    main: '#4caf50', // Material Design Success
    light: '#e8f5e9',
    contrastText: '#FFFFFF',
  },
  background: {
    default: '#f5f7fb', // Custom light background
    paper: '#ffffff', // Custom card background (white)
  },
  text: {
    primary: '#1C1B1F', // M3 On Surface
    secondary: '#49454F', // M3 On Surface Variant
    disabled: 'rgba(0, 0, 0, 0.38)',
  },
  divider: '#CAC4D0', // M3 Outline Variant
};

// --- Dark Theme Palette (Material 3 Inspired) ---
const darkPalette = {
  mode: 'dark' as PaletteMode,
  primary: {
    main: '#D0BCFF', // M3 Primary (Dark)
    light: '#4F378B', // M3 Primary Container (Dark)
    dark: '#B69DF8', // Lighter shade for contrast
    contrastText: '#381E72', // Text on Primary (Dark)
  },
  secondary: {
    main: '#CCC2DC', // M3 Secondary (Dark)
    light: '#4A4458', // M3 Secondary Container (Dark)
    dark: '#E8DEF8', // Lighter shade
    contrastText: '#332D41', // Text on Secondary (Dark)
  },
  error: {
    main: '#F2B8B5', // M3 Error (Dark)
    light: '#601410', // M3 Error Container (Dark)
    contrastText: '#370B1E',
  },
  warning: {
    main: '#ffd54f', // Material Design Warning (Dark)
    light: '#424242', // Darker background for warning container
    contrastText: 'rgba(0, 0, 0, 0.87)',
  },
  info: {
    main: '#64b5f6', // Material Design Info (Dark)
    light: '#424242',
    contrastText: '#FFFFFF',
  },
  success: {
    main: '#81c784', // Material Design Success (Dark)
    light: '#424242',
    contrastText: 'rgba(0, 0, 0, 0.87)',
  },
  background: {
    default: '#1C1B1F', // M3 Surface (Dark)
    paper: '#1C1B1F', // M3 Surface (Dark) - Use for cards, dialogs etc.
  },
  text: {
    primary: '#E6E1E5', // M3 On Surface (Dark)
    secondary: '#CAC4D0', // M3 On Surface Variant (Dark)
    disabled: 'rgba(255, 255, 255, 0.5)',
  },
  divider: '#49454F', // M3 Outline Variant (Dark)
};

// --- Create Themes by Merging Base and Palettes ---
// Use deepmerge to combine base options with specific palettes
const lightTheme = createTheme(deepmerge(baseThemeOptions, { palette: lightPalette }));
const darkTheme = createTheme(deepmerge(baseThemeOptions, { palette: darkPalette }));

// --- Export Function to Get Theme Based on Mode ---
export const getAppTheme = (mode: PaletteMode) => {
  return mode === 'light' ? lightTheme : darkTheme;
};