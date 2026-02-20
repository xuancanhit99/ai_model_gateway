import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import { getAccessToken } from '../authHelper';
import {
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Chip, Typography, Box, CircularProgress, Alert, IconButton, Tooltip,
    Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, TextField, Button // Added Dialog components
} from '@mui/material'; // Import MUI components
import CancelIcon from '@mui/icons-material/Cancel';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline'; // Activate icon
import PauseCircleOutlineIcon from '@mui/icons-material/PauseCircleOutline'; // Deactivate icon

// Định nghĩa kiểu dữ liệu cho một API key (lấy từ schemas.py backend)
interface ApiKeyInfo {
    key_prefix: string;
    name: string | null;
    created_at: string; // Dạng ISO string
    last_used_at: string | null;
    is_active: boolean;
    user_id: string;
}

interface ApiKeyListProps {
    session: any; // Session proxy from App.tsx (Keycloak token)
    onListChange: () => void;
    refreshTrigger: number;
}

const ApiKeyList: React.FC<ApiKeyListProps> = ({ session, onListChange, refreshTrigger }) => {
    const { t } = useTranslation(); // Sử dụng hook useTranslation
    const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [deactivating, setDeactivating] = useState<string | null>(null); // State for deactivation loading
    const [activating, setActivating] = useState<string | null>(null); // State for activation loading
    const [deleting, setDeleting] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null); // Keep for initial fetch error
    // const [successMessage, setSuccessMessage] = useState<string | null>(null); // Remove success message state
    const [confirmDeleteDialogOpen, setConfirmDeleteDialogOpen] = useState(false);
    const [keyToDelete, setKeyToDelete] = useState<string | null>(null);
    const [deleteConfirmationInput, setDeleteConfirmationInput] = useState('');

    // Dialog states for deactivate/activate confirmation
    const [deactivateDialogOpen, setDeactivateDialogOpen] = useState(false);
    const [activateDialogOpen, setActivateDialogOpen] = useState(false);
    const [keyToToggle, setKeyToToggle] = useState<string | null>(null);

    useEffect(() => {
        const fetchApiKeys = async () => {
            setLoading(true);
            setError(null);

            try {
                const token = await getAccessToken();

                // Use a relative path. Assumes the reverse proxy/ingress is configured
                // to route /api/v1/* requests to the backend service.
                const apiUrl = '/api/v1/keys';

                const response = await fetch(apiUrl, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `Failed to fetch API keys: ${response.statusText}`);
                }

                const data: { keys: ApiKeyInfo[] } = await response.json();
                // Sort keys: active first, then by creation date descending
                data.keys.sort((a, b) => {
                    if (a.is_active && !b.is_active) return -1;
                    if (!a.is_active && b.is_active) return 1;
                    // Add safety check for date parsing during sort
                    const dateA = new Date(a.created_at).getTime();
                    const dateB = new Date(b.created_at).getTime();
                    if (isNaN(dateA) || isNaN(dateB)) {
                        console.error("Invalid date found during sorting:", a, b);
                        return 0; // Avoid crash, maintain relative order or default
                    }
                    return dateB - dateA;
                });
                setKeys(data.keys); // Update state with sorted keys

            } catch (err: any) {
                console.error("Error fetching API keys:", err);
                // Ensure error message is always a string
                const errorMessage = err instanceof Error ? err.message : String(err);
                setError(errorMessage || 'An unexpected error occurred.');
                setKeys([]); // Clear keys on fetch error to avoid rendering stale/bad data
            } finally {
                setLoading(false);
            }
        };

        fetchApiKeys();
        // Add refreshTrigger to dependency array
    }, [session, onListChange, refreshTrigger]); // Re-fetch if session, list changes, or refreshTrigger changes

    // Function to open deactivate confirmation dialog
    const openDeactivateDialog = (keyPrefix: string) => {
        setKeyToToggle(keyPrefix);
        setDeactivateDialogOpen(true);
    };

    // Function to open activate confirmation dialog
    const openActivateDialog = (keyPrefix: string) => {
        setKeyToToggle(keyPrefix);
        setActivateDialogOpen(true);
    };

    const handleDeactivate = async (keyPrefix: string) => {
        setDeactivateDialogOpen(false);
        setDeactivating(keyPrefix);
        setError(null);

        try {
            const token = await getAccessToken();

            // Use a relative path (DELETE endpoint for deactivation)
            const apiUrl = `/api/v1/keys/${keyPrefix}`;

            const response = await fetch(apiUrl, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            const responseData = await response.json();

            if (!response.ok) {
                throw new Error(responseData.detail || `Failed to deactivate API key: ${response.statusText}`);
            }

            // Thành công! Cập nhật state cục bộ và hiển thị thông báo
            setKeys(prevKeys => prevKeys.map(k => k.key_prefix === keyPrefix ? { ...k, is_active: false } : k));
            toast.success(responseData.message || 'API Key deactivated successfully.');
            // onListChange(); // Optional: Trigger list refresh if needed elsewhere

        } catch (err: any) {
            console.error("Error deactivating API key:", err);
            const errorMessage = err instanceof Error ? err.message : String(err);
            toast.error(errorMessage || 'An unexpected error occurred during deactivation.');
        } finally {
            setDeactivating(null); // Clear loading state for this key
            setKeyToToggle(null);
        }
    };

    const handleActivate = async (keyPrefix: string) => {
        setActivateDialogOpen(false);
        setActivating(keyPrefix);
        setError(null);

        try {
            const token = await getAccessToken();

            // *** Assume a PATCH endpoint exists for activation ***
            // If the backend uses a different method/endpoint, update here.
            const apiUrl = `/api/v1/keys/${keyPrefix}`;

            const response = await fetch(apiUrl, {
                method: 'PATCH', // Use PATCH to update the resource status
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json' // Important if sending a body
                },
                // Send body to explicitly set is_active to true
                body: JSON.stringify({ is_active: true })
            });

            const responseData = await response.json();

            if (!response.ok) {
                // Handle potential 404 if key was deleted elsewhere, or other errors
                throw new Error(responseData.detail || `Failed to activate API key: ${response.statusText}`);
            }

            // Thành công! Cập nhật state cục bộ và hiển thị thông báo
            setKeys(prevKeys => prevKeys.map(k => k.key_prefix === keyPrefix ? { ...k, is_active: true } : k));
            toast.success(responseData.message || 'API Key activated successfully.');
            // onListChange(); // Optional: Trigger list refresh if needed elsewhere

        } catch (err: any) {
            console.error("Error activating API key:", err);
            const errorMessage = err instanceof Error ? err.message : String(err);
            toast.error(errorMessage || 'An unexpected error occurred during activation.');
        } finally {
            setActivating(null); // Clear loading state for this key
            setKeyToToggle(null);
        }
    };

    // Function to open the confirmation dialog
    const openDeleteConfirmationDialog = (keyPrefix: string) => {
        setKeyToDelete(keyPrefix);
        setDeleteConfirmationInput(''); // Reset input field
        setConfirmDeleteDialogOpen(true);
    };

    // Function to close the confirmation dialog
    const handleCloseDeleteConfirmationDialog = () => {
        setConfirmDeleteDialogOpen(false);
        setKeyToDelete(null);
    };

    // Function to handle the actual deletion after confirmation
    const handleConfirmDeletion = useCallback(async () => {
        if (deleteConfirmationInput !== 'DELETE' || !keyToDelete) {
            toast.error('Incorrect confirmation text entered. Deletion cancelled.');
            handleCloseDeleteConfirmationDialog();
            return;
        }

        const keyPrefix = keyToDelete;
        handleCloseDeleteConfirmationDialog();

        setDeleting(keyPrefix);
        setError(null);

        try {
            const token = await getAccessToken();

            // Call the new permanent delete endpoint
            const apiUrl = `/api/v1/keys/${keyPrefix}/permanent`;

            const response = await fetch(apiUrl, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            const responseData = await response.json();

            if (!response.ok) {
                // Handle potential 404 if key was already deleted, or other errors
                throw new Error(responseData.detail || `Failed to permanently delete API key: ${response.statusText}`);
            }

            // Thành công! Cập nhật state cục bộ và hiển thị thông báo
            setKeys(prevKeys => prevKeys.filter(k => k.key_prefix !== keyPrefix));
            // Sử dụng i18n cho thông báo, bỏ qua responseData.message
            toast.success(t('apiKeys.deleteSuccess', 'API Key permanently deleted successfully.'));
            // No need to call onListChange here

        } catch (err: any) {
            console.error("Error permanently deleting API key:", err);
            const errorMessage = err instanceof Error ? err.message : String(err);
            toast.error(errorMessage || 'An unexpected error occurred during permanent deletion.');
        } finally {
            setDeleting(null); // Clear loading state for this key
        }
    }, [keyToDelete, deleteConfirmationInput]);


    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 3 }}>
                <CircularProgress />
                <Typography sx={{ ml: 2 }}>Loading API Keys...</Typography>
            </Box>
        );
    }

    if (error) {
        // Use Alert for better visibility
        return <Alert severity="error" sx={{ mt: 2 }}>Error: {error}</Alert>;
    }

    return (
        <Box> {/* Use Box as the main container */}
            <Typography variant="h6" component="h3" gutterBottom>
                Your API Keys
            </Typography>

            {/* Display Initial Fetch Error Message */}
            {error && <Alert severity="error" sx={{ mt: 2, mb: 2 }}>{error}</Alert>}
            {/* Success messages are now handled by react-hot-toast */}

            {keys.length === 0 ? (
                <Typography sx={{ mt: 2 }}>You haven't created any API keys yet.</Typography>
            ) : (
                <TableContainer component={Paper} sx={{ mt: 2 }}> {/* Wrap table in Paper */}
                    <Table sx={{ minWidth: 650 }} aria-label="api keys table">
                        <TableHead>
                            <TableRow>{/* Ensure no whitespace between TableRow and TableCell */}
                                <TableCell>Name</TableCell><TableCell>Prefix</TableCell><TableCell>Created</TableCell><TableCell>Status</TableCell><TableCell align="right">Actions</TableCell>{/* Align actions to the right */}
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {keys.map((key) => {
                                try {
                                    // Attempt to render the row
                                    return (
                                        <TableRow
                                            key={key.key_prefix}
                                            sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                                        >{/* Ensure no whitespace between TableRow and TableCell */}
                                            <TableCell component="th" scope="row">
                                                {key.name || '-'}
                                            </TableCell><TableCell>{`hp_${key.key_prefix}...`}</TableCell><TableCell>
                                                {(() => {
                                                    try {
                                                        return new Date(key.created_at).toLocaleString();
                                                    } catch (dateError) {
                                                        console.error(`Error formatting date for key ${key.key_prefix}:`, dateError);
                                                        return 'Invalid Date';
                                                    }
                                                })()}
                                            </TableCell><TableCell>
                                                <Chip
                                                    icon={key.is_active ? <CheckCircleIcon /> : <CancelIcon />}
                                                    label={key.is_active ? 'Active' : 'Inactive'}
                                                    color={key.is_active ? 'success' : 'default'}
                                                    size="small"
                                                    variant="outlined"
                                                />
                                            </TableCell><TableCell align="right">
                                                {/* Activate/Deactivate Buttons */}
                                                {key.is_active ? (
                                                    <Tooltip title="Deactivate this key">
                                                        <span>
                                                            <IconButton
                                                                size="small"
                                                                onClick={() => openDeactivateDialog(key.key_prefix)} // Use dialog to confirm deactivation
                                                                disabled={deactivating === key.key_prefix || activating === key.key_prefix || deleting === key.key_prefix}
                                                                color="warning"
                                                            >
                                                                {deactivating === key.key_prefix ? <CircularProgress size={20} color="inherit" /> : <PauseCircleOutlineIcon fontSize="small" />}
                                                            </IconButton>
                                                        </span>
                                                    </Tooltip>
                                                ) : (
                                                    <Tooltip title="Activate this key">
                                                        <span>
                                                            <IconButton
                                                                size="small"
                                                                onClick={() => openActivateDialog(key.key_prefix)} // Use dialog to confirm activation
                                                                disabled={activating === key.key_prefix || deactivating === key.key_prefix || deleting === key.key_prefix}
                                                                color="success"
                                                            >
                                                                {activating === key.key_prefix ? <CircularProgress size={20} color="inherit" /> : <PlayCircleOutlineIcon fontSize="small" />}
                                                            </IconButton>
                                                        </span>
                                                    </Tooltip>
                                                )}
                                                {/* Delete Button */}
                                                <Tooltip title="Permanently delete this key (irreversible)">
                                                    <IconButton
                                                        size="small"
                                                        onClick={() => openDeleteConfirmationDialog(key.key_prefix)} // Open dialog instead
                                                        disabled={deleting === key.key_prefix || activating === key.key_prefix || deactivating === key.key_prefix}
                                                        color="error"
                                                        sx={{ ml: 1 }}
                                                    >
                                                        {deleting === key.key_prefix ? <CircularProgress size={20} color="inherit" /> : <CancelIcon fontSize="small" />}
                                                    </IconButton>
                                                </Tooltip>
                                            </TableCell>
                                        </TableRow>
                                    );
                                } catch (renderError: any) {
                                    // Log the error and render an error row
                                    console.error(`Error rendering row for key ${key?.key_prefix}:`, renderError);
                                    return (
                                        <TableRow key={key?.key_prefix || `error-${Math.random()}`}>
                                            <TableCell colSpan={5}>
                                                {/* Removed invalid size="small" prop from Alert */}
                                                <Alert severity="error" variant="outlined">
                                                    Error rendering this API key row. Check console for details.
                                                </Alert>
                                            </TableCell>
                                        </TableRow>
                                    );
                                }
                            })}
                        </TableBody>
                    </Table>
                </TableContainer>
            )}

            {/* Confirmation Dialog for Deletion */}
            <Dialog open={confirmDeleteDialogOpen} onClose={handleCloseDeleteConfirmationDialog}>
                <DialogTitle>Confirm Permanent Deletion</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Are you sure you want to permanently delete the key starting with hp_{keyToDelete}?
                        This action is irreversible. Type DELETE to confirm.
                    </DialogContentText>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Type DELETE to confirm"
                        type="text"
                        fullWidth
                        value={deleteConfirmationInput}
                        onChange={(e) => setDeleteConfirmationInput(e.target.value)}
                        error={deleteConfirmationInput !== '' && deleteConfirmationInput !== 'DELETE'}
                        helperText={deleteConfirmationInput !== '' && deleteConfirmationInput !== 'DELETE' ? 'Please type DELETE exactly as shown' : ''}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleCloseDeleteConfirmationDialog}>Cancel</Button>
                    <Button
                        onClick={handleConfirmDeletion}
                        color="error"
                        disabled={deleteConfirmationInput !== 'DELETE'}
                    >
                        Delete Permanently
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Deactivate confirmation dialog */}
            <Dialog open={deactivateDialogOpen} onClose={() => setDeactivateDialogOpen(false)}>
                <DialogTitle>Confirm Deactivation</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Are you sure you want to deactivate the key starting with hp_{keyToToggle}?
                        This will make the key unusable until reactivated.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeactivateDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={() => keyToToggle && handleDeactivate(keyToToggle)}
                        color="warning"
                    >
                        Deactivate
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Activate confirmation dialog */}
            <Dialog open={activateDialogOpen} onClose={() => setActivateDialogOpen(false)}>
                <DialogTitle>Confirm Activation</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Are you sure you want to activate the key starting with hp_{keyToToggle}?
                        This will make the key usable for API requests.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setActivateDialogOpen(false)}>Cancel</Button>
                    <Button
                        onClick={() => keyToToggle && handleActivate(keyToToggle)}
                        color="success"
                    >
                        Activate
                    </Button>
                </DialogActions>
            </Dialog>

        </Box> // Closing tag of the main Box
    );
};

export default ApiKeyList;