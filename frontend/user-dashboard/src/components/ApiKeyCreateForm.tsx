import React, { useState } from 'react';
import { supabase } from '../supabaseClient';
// Session type might not be needed here anymore if not used
// import type { Session } from '@supabase/supabase-js';

interface ApiKeyCreateFormProps {
    // session: Session; // Removed unused session prop
    onKeyCreated: () => void; // Callback để thông báo cho component cha làm mới danh sách
}

const ApiKeyCreateForm: React.FC<ApiKeyCreateFormProps> = ({ onKeyCreated }) => { // Removed session from destructuring
    const [name, setName] = useState<string>('');
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [newKey, setNewKey] = useState<string | null>(null); // Để hiển thị key mới tạo

    const handleCreateKey = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault(); // Ngăn chặn gửi form mặc định
        setLoading(true);
        setError(null);
        setNewKey(null); // Xóa key cũ nếu có

        if (!supabase) {
            setError("Supabase client is not initialized.");
            setLoading(false);
            return;
        }

        try {
            const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
            if (sessionError || !sessionData.session) {
                throw new Error(sessionError?.message || 'Could not get user session.');
            }
            const token = sessionData.session.access_token;

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
            onKeyCreated(); // Thông báo cho component cha

        } catch (err: any) {
            console.error("Error creating API key:", err);
            setError(err.message || 'An unexpected error occurred.');
        } finally {
            setLoading(false);
        }
    };

    const copyToClipboard = () => {
        if (newKey) {
            navigator.clipboard.writeText(newKey)
                .then(() => alert('API Key copied to clipboard!'))
                .catch(err => console.error('Failed to copy key: ', err));
        }
    };

    return (
        <div>
            <h4>Create New API Key</h4>
            <form onSubmit={handleCreateKey}>
                <div>
                    <label htmlFor="keyName">Key Name (Optional): </label>
                    <input
                        id="keyName"
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g., My Test Key"
                        disabled={loading}
                    />
                </div>
                <button type="submit" disabled={loading}>
                    {loading ? 'Creating...' : 'Create Key'}
                </button>
            </form>

            {error && <p style={{ color: 'red' }}>Error: {error}</p>}

            {newKey && (
                <div className="success-message"> {/* Use CSS class */}
                    <p><strong>API Key Created Successfully!</strong></p>
                    <p>Please copy your new API key. You won't be able to see it again.</p>
                    {/* Inline style removed from pre, handled by index.css */}
                    <pre>
                        <code>{newKey}</code>
                    </pre>
                    <button onClick={copyToClipboard}>Copy Key</button> {/* Removed inline margin */}
                </div>
            )}
        </div>
    );
};

export default ApiKeyCreateForm;