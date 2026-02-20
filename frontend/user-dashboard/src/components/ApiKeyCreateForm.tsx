import React, { useState } from 'react';
import { getAccessToken } from '../authHelper';
import toast from 'react-hot-toast'; // Import toast
import {
    TextField, Button, Box, Typography, CircularProgress, Alert, IconButton, InputAdornment, Tooltip // Removed Snackbar
} from '@mui/material'; // Import MUI components
import ContentCopyIcon from '@mui/icons-material/ContentCopy'; // Import copy icon

interface ApiKeyCreateFormProps {
    // session: Session; // Removed unused session prop
    onKeyCreated: () => void; // Callback để thông báo cho component cha làm mới danh sách
}

const ApiKeyCreateForm: React.FC<ApiKeyCreateFormProps> = ({ onKeyCreated }) => { // Removed session from destructuring
    const [name, setName] = useState<string>('');
    const [loading, setLoading] = useState<boolean>(false);
    // const [error, setError] = useState<string | null>(null); // Remove error state
    const [newKey, setNewKey] = useState<string | null>(null);
    // const [snackbarOpen, setSnackbarOpen] = useState(false); // Remove Snackbar state

    const handleCreateKey = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault(); // Ngăn chặn gửi form mặc định
        setLoading(true);
        // setError(null); // Remove error state reset
        setNewKey(null);

        try {
            const token = await getAccessToken();

            // Use a relative path
            const apiUrl = '/api/v1/keys';

            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ name: name || null }), // Gửi name hoặc null nếu trống
            });

            const responseData = await response.json();

            if (!response.ok) {
                throw new Error(responseData.detail || `Failed to create API key: ${response.statusText}`);
            }

            // Thành công! Hiển thị key mới và gọi callback
            setNewKey(responseData.full_api_key);
            setName(''); // Xóa trường input name
            toast.success('API Key created successfully!'); // Add success toast
            onKeyCreated(); // Thông báo cho component cha

        } catch (err: any) {
            console.error("Error creating API key:", err);
            // Ensure error message is always a string before showing toast
            const errorMessage = err instanceof Error ? err.message : String(err);
            toast.error(errorMessage || 'An unexpected error occurred.');
        } finally {
            setLoading(false);
        }
    };

    const copyToClipboard = () => {
        if (newKey) {
            navigator.clipboard.writeText(newKey)
                .then(() => {
                    toast.success('API Key copied to clipboard!'); // Show toast on success
                    // Keep the key visible for a bit or hide immediately based on UX preference
                    // setNewKey(null); // Optional: Hide the key after copying
                })
                .catch(err => {
                    console.error('Failed to copy key: ', err);
                    toast.error('Failed to copy key automatically. Please copy it manually.'); // Show toast on error
                });
        }
    };

    // Remove handleSnackbarClose as Snackbar is removed
    // const handleSnackbarClose = (_event?: React.SyntheticEvent | Event, reason?: string) => {
    //     if (reason === 'clickaway') {
    //         return;
    //     }
    //     setSnackbarOpen(false);
    // };

    return (
        <Box component="div" sx={{ mt: 3 }}> {/* Use Box as container */}
            <Typography variant="h6" component="h4" gutterBottom>
                Create New API Key
            </Typography>
            <Box component="form" onSubmit={handleCreateKey} noValidate sx={{ mt: 1 }}>
                <TextField
                    margin="normal"
                    fullWidth
                    id="keyName"
                    label="Key Name (Optional)"
                    name="keyName"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., My Test Key"
                    disabled={loading}
                    variant="outlined" // Use outlined variant
                />
                <Button
                    type="submit"
                    variant="contained" // Use contained style
                    disabled={loading}
                    sx={{ mt: 2, mb: 2 }} // Add margin
                    startIcon={loading ? <CircularProgress size={20} color="inherit" /> : null} // Show spinner inside button
                >
                    {loading ? 'Creating...' : 'Create Key'}
                </Button>
            </Box>

            {/* Error messages are now handled by react-hot-toast */}
            {/* {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>} */}

            {newKey && (
                <Alert severity="success" sx={{ mt: 3, display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                    <Typography variant="subtitle1" gutterBottom>
                        <strong>API Key Created Successfully!</strong>
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 1 }}>
                        Please copy your new API key. You won't be able to see it again.
                    </Typography>
                    <TextField
                        fullWidth
                        // readOnly prop removed, use InputProps instead
                        value={newKey}
                        variant="outlined"
                        size="small"
                        sx={{
                            mb: 1,
                            '& .MuiInputBase-input': {
                                fontFamily: 'monospace',
                                fontSize: '0.9rem',
                            },
                        }}
                        InputProps={{
                            readOnly: true, // Set readOnly via InputProps
                            endAdornment: (
                                <InputAdornment position="end">
                                    <Tooltip title="Copy API Key">
                                        <IconButton
                                            aria-label="copy api key"
                                            onClick={copyToClipboard}
                                            edge="end"
                                        >
                                            <ContentCopyIcon fontSize='small' />
                                        </IconButton>
                                    </Tooltip>
                                </InputAdornment>
                            ),
                        }}
                    />
                    {/* Optional: Add a button to explicitly close/hide the key */}
                    <Button size="small" onClick={() => setNewKey(null)} sx={{ alignSelf: 'flex-end' }}>
                        Close
                    </Button>
                </Alert>
            )}
            {/* Snackbar removed, confirmation handled by react-hot-toast */}
        </Box>
    );
};

export default ApiKeyCreateForm;