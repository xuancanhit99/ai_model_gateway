import React, { useState, useEffect } from 'react';
import { supabase } from '../supabaseClient'; // Import Supabase client for auth token
import type { Session } from '@supabase/supabase-js';

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
    session: Session; // Nhận session để lấy token
    onListChange: () => void; // Callback để thông báo thay đổi (tạo/xóa/cập nhật)
}

const ApiKeyList: React.FC<ApiKeyListProps> = ({ session, onListChange }) => {
    const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [deactivating, setDeactivating] = useState<string | null>(null); // State for deactivation loading
    const [activating, setActivating] = useState<string | null>(null); // State for activation loading
    const [deleting, setDeleting] = useState<string | null>(null); // State for permanent deletion loading
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchApiKeys = async () => {
            setLoading(true);
            setError(null);

            // Check if supabase client is available
            if (!supabase) {
                setError("Supabase client is not initialized. Check environment variables.");
                setLoading(false);
                return; // Exit early if no client
            }

            try {
                // Now safe to use supabase
                const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
                if (sessionError || !sessionData.session) {
                    throw new Error(sessionError?.message || 'Could not get user session.');
                }
                const token = sessionData.session.access_token;

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
                    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
                });
                setKeys(data.keys);

            } catch (err: any) {
                console.error("Error fetching API keys:", err);
                setError(err.message || 'An unexpected error occurred.');
            } finally {
                setLoading(false);
            }
        };

        fetchApiKeys();
    // Wrap fetchApiKeys in useCallback if needed, but dependency array handles it for now
    }, [session, onListChange]); // Re-fetch if session or list changes externally

    const handleDeactivate = async (keyPrefix: string) => {
        if (!confirm(`Are you sure you want to deactivate the key starting with hp_${keyPrefix}?`)) {
            return;
        }

        setDeactivating(keyPrefix); // Set loading state for this specific key
        setError(null);

        if (!supabase) {
            setError("Supabase client is not initialized.");
            setDeactivating(null);
            return;
        }

        try {
            const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
            if (sessionError || !sessionData.session) {
                throw new Error(sessionError?.message || 'Could not get user session.');
            }
            const token = sessionData.session.access_token;

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

            // Thành công! Cập nhật state cục bộ và gọi callback
            setKeys(prevKeys => prevKeys.map(k => k.key_prefix === keyPrefix ? { ...k, is_active: false } : k));
            alert(responseData.message || 'API Key deactivated successfully.');
            // onListChange(); // Trigger list refresh in parent component (optional now)

        } catch (err: any) {
            console.error("Error deactivating API key:", err);
            setError(err.message || 'An unexpected error occurred during deactivation.');
        } finally {
            setDeactivating(null); // Clear loading state for this key
        }
    };

    const handleActivate = async (keyPrefix: string) => {
        if (!confirm(`Are you sure you want to activate the key starting with hp_${keyPrefix}?`)) {
            return;
        }

        setActivating(keyPrefix); // Set loading state for this specific key
        setError(null);

        if (!supabase) {
            setError("Supabase client is not initialized.");
            setActivating(null);
            return;
        }

        try {
            const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
            if (sessionError || !sessionData.session) {
                throw new Error(sessionError?.message || 'Could not get user session.');
            }
            const token = sessionData.session.access_token;

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

            // Thành công! Cập nhật state cục bộ và gọi callback
            setKeys(prevKeys => prevKeys.map(k => k.key_prefix === keyPrefix ? { ...k, is_active: true } : k));
            alert(responseData.message || 'API Key activated successfully.');
            // onListChange(); // Trigger list refresh in parent component (optional now)

        } catch (err: any) {
            console.error("Error activating API key:", err);
            setError(err.message || 'An unexpected error occurred during activation.');
        } finally {
            setActivating(null); // Clear loading state for this key
        }
    };

    const handleDeletePermanently = async (keyPrefix: string) => {
        // Stronger confirmation for permanent deletion
        const confirmation = prompt(`DANGER ZONE! This action is irreversible. To confirm permanent deletion of the key starting with hp_${keyPrefix}, please type "DELETE" below:`);
        if (confirmation !== 'DELETE') {
            alert("Deletion cancelled.");
            return;
        }

        setDeleting(keyPrefix); // Set loading state for this specific key
        setError(null);

        if (!supabase) {
            setError("Supabase client is not initialized.");
            setDeleting(null);
            return;
        }

        try {
            const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
            if (sessionError || !sessionData.session) {
                throw new Error(sessionError?.message || 'Could not get user session.');
            }
            const token = sessionData.session.access_token;

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

            // Thành công! Cập nhật state cục bộ (remove the key)
            setKeys(prevKeys => prevKeys.filter(k => k.key_prefix !== keyPrefix));
            alert(responseData.message || 'API Key permanently deleted successfully.');
            // No need to call onListChange here as the key is gone from local state

        } catch (err: any) {
            console.error("Error permanently deleting API key:", err);
            setError(err.message || 'An unexpected error occurred during permanent deletion.');
        } finally {
            setDeleting(null); // Clear loading state for this key
        }
    };


    if (loading) {
        return <div>Loading API Keys...</div>;
    }

    if (error) {
        return <div style={{ color: 'var(--color-error)' }}>Error: {error}</div>; // Use CSS variable for color
    }

    return (
        <div>
            <h3>Your API Keys</h3>
            {keys.length === 0 ? (
                <p>You haven't created any API keys yet.</p>
            ) : (
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Prefix</th>
                            <th>Created</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {keys.map((key) => (
                            <tr key={key.key_prefix} className={!key.is_active ? 'inactive-key' : ''}>
                                <td>{key.name || '-'}</td>
                                <td>{`hp_${key.key_prefix}...`}</td>
                                <td>{new Date(key.created_at).toLocaleString()}</td>
                                <td>
                                    <span className={`status ${key.is_active ? 'status-active' : 'status-inactive'}`}>
                                        {key.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                                <td className="action-buttons"> {/* Add class for easier styling */}
                                    {key.is_active ? (
                                        // Show Deactivate button if key is active
                                        <button
                                            onClick={() => handleDeactivate(key.key_prefix)}
                                            disabled={deactivating === key.key_prefix || activating === key.key_prefix || deleting === key.key_prefix}
                                            className="action-btn deactivate-btn"
                                            title="Deactivate this key"
                                        >
                                            {deactivating === key.key_prefix ? 'Deactivating...' : 'Deactivate'}
                                        </button>
                                    ) : (
                                        // Show Activate button if key is inactive
                                        <button
                                            onClick={() => handleActivate(key.key_prefix)}
                                            disabled={activating === key.key_prefix || deactivating === key.key_prefix || deleting === key.key_prefix}
                                            className="action-btn activate-btn"
                                            title="Activate this key"
                                        >
                                            {activating === key.key_prefix ? 'Activating...' : 'Activate'}
                                        </button>
                                    )}
                                    {/* Add Permanent Delete Button */}
                                    <button
                                        onClick={() => handleDeletePermanently(key.key_prefix)}
                                        disabled={deleting === key.key_prefix || activating === key.key_prefix || deactivating === key.key_prefix}
                                        className="action-btn delete-btn" // Reuse delete-btn class or create a new one
                                        title="Permanently delete this key (irreversible)"
                                        style={{ marginLeft: '5px' }} // Keep margin for spacing
                                    >
                                        {deleting === key.key_prefix ? 'Deleting...' : 'Delete'}
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    );
};

export default ApiKeyList;