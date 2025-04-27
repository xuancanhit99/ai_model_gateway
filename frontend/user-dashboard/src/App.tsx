import { useState, useEffect, useCallback } from 'react';
import { supabase } from './supabaseClient';
import { Auth } from '@supabase/auth-ui-react';
import { ThemeSupa } from '@supabase/auth-ui-shared';
import type { Session } from '@supabase/supabase-js';
import ApiKeyList from './components/ApiKeyList';
import ApiKeyCreateForm from './components/ApiKeyCreateForm';
import ProviderKeyManager from './components/ProviderKeyManager';
import { Tabs, Tab, Box } from '@mui/material';
import './App.css';

// Kiểu dữ liệu cho theme
type Theme = 'light' | 'dark';

// Main dashboard component after login
function Dashboard({ session }: { session: Session }) {
  const [refreshCounter, setRefreshCounter] = useState(0);
  const [activeTab, setActiveTab] = useState(0);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleKeyCreated = useCallback(() => {
    console.log("New key created, triggering list refresh...");
    setRefreshCounter(prev => prev + 1);
  }, []);

  return (
    <div className="dashboard-content">
      <h2>Dashboard</h2>
      <p>Welcome, {session.user.email}!</p>
      
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs 
          value={activeTab} 
          onChange={handleTabChange}
          aria-label="dashboard tabs"
          centered
        >
          <Tab label="Gateway API Keys" />
          <Tab label="Provider API Keys" />
        </Tabs>
      </Box>

      {activeTab === 0 && (
        <>
          <ApiKeyList key={refreshCounter} session={session} onListChange={handleKeyCreated} />
          <hr />
          <ApiKeyCreateForm onKeyCreated={handleKeyCreated} />
        </>
      )}

      {activeTab === 1 && (
        <ProviderKeyManager />
      )}
    </div>
  );
}

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  // State cho theme, đọc từ localStorage hoặc mặc định là 'dark'
  const [theme, setTheme] = useState<Theme>(() => {
    const storedTheme = localStorage.getItem('app-theme');
    return (storedTheme === 'light' || storedTheme === 'dark') ? storedTheme : 'dark';
  });

  // Effect để lấy session và lắng nghe thay đổi auth state
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

  // Effect để áp dụng theme vào body và lưu vào localStorage
  useEffect(() => {
    document.body.classList.remove('light', 'dark'); // Xóa class cũ
    document.body.classList.add(theme); // Thêm class mới
    localStorage.setItem('app-theme', theme); // Lưu lựa chọn
    setLoading(false); // Kết thúc loading sau khi theme được áp dụng
  }, [theme]); // Chạy lại khi theme thay đổi

  // Hàm chuyển đổi theme
  const toggleTheme = () => {
    setTheme(prevTheme => (prevTheme === 'light' ? 'dark' : 'light'));
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    // Thêm class theme vào container chính để CSS có thể target
    <div className={`app-container ${theme}`}> {/* Use a more specific class */}
      {/* App Bar */}
      <div className="app-bar">
        <div className="app-bar-title">AI Model Gateway Keys</div>
        <div className="app-bar-actions">
          {/* Theme Switch Component */}
          <label htmlFor="theme-switch-checkbox" className="theme-switch" title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}>
            <input
              id="theme-switch-checkbox"
              type="checkbox"
              checked={theme === 'dark'}
              onChange={toggleTheme}
              style={{ display: 'none' }} // Hide the actual checkbox
            />
            <span className="switch-track">
              <span className="switch-thumb">
                {/* Icons inside the thumb */}
                <span className="switch-icon">{theme === 'light' ? '☀️' : '🌙'}</span>
              </span>
            </span>
          </label>
          {session && (
            <button onClick={() => supabase?.auth.signOut()} className="signout-btn">
              Sign Out
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="main-content">
        {!session ? (
        supabase ? (
          <div style={{ maxWidth: '400px', margin: '50px auto 0' }}> {/* Center Auth UI */}
            <Auth
              supabaseClient={supabase}
              appearance={{
                theme: ThemeSupa,
                // Tùy chỉnh biến CSS nếu cần, hoặc để ThemeSupa tự xử lý
                // variables: { default: { colors: { brand: 'red', brandAccent: 'darkred' } } }
              }}
              providers={['google', 'github']}
              theme={theme} // Truyền theme hiện tại vào Auth UI
            />
          </div>
        ) : (
          <div>Error: Supabase client not initialized. Check environment variables.</div>
        )
      ) : (
        <Dashboard session={session} />
      )}
      </div> {/* End main-content */}
    </div> /* End app-container */
  );
}

export default App;
