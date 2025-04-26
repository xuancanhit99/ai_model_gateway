import { useState, useEffect } from 'react';
import { supabase } from './supabaseClient'; // Import Supabase client
import { Auth } from '@supabase/auth-ui-react'; // Import Auth UI component
import { ThemeSupa } from '@supabase/auth-ui-shared'; // Import default theme
import type { Session } from '@supabase/supabase-js'; // Import Session type
import './App.css'; // Keep default CSS for now

// Placeholder for the main dashboard component after login
function Dashboard({ session }: { session: Session }) {
  // In a real app, this would fetch and display API keys, allow creation/deletion
  // It would use session.user.id to make authenticated requests to the backend API
  return (
    <div>
      <h2>Dashboard</h2>
      <p>Welcome, {session.user.email}!</p>
      <p>User ID: {session.user.id}</p>
      {/* TODO: Add API Key Management UI here */}
      <button onClick={() => supabase?.auth.signOut()}>Sign Out</button>
    </div>
  );
}

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing session on initial load
    supabase?.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    }).catch(error => {
      console.error("Error getting session:", error);
      setLoading(false); // Ensure loading stops even on error
    });

    // Listen for changes in authentication state (login, logout)
    const { data: { subscription } } = supabase?.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session);
      }
    ) ?? { data: { subscription: null } }; // Handle potential null supabase client

    // Cleanup listener on component unmount
    return () => {
      subscription?.unsubscribe();
    };
  }, []); // Empty dependency array ensures this runs only once on mount

  if (loading) {
    return <div>Loading...</div>; // Show loading indicator
  }

  // Render Auth UI if no session, otherwise render the Dashboard
  return (
    <div className="container" style={{ padding: '50px 0 100px 0' }}>
      {!session ? (
        supabase ? ( // Check if supabase client exists before rendering Auth
          <Auth
            supabaseClient={supabase}
            appearance={{ theme: ThemeSupa }} // Use the default Supabase theme
            providers={['google', 'github']} // Optional: Add social providers
            theme="dark" // Optional: Set theme (dark/light)
          />
        ) : (
          <div>Error: Supabase client not initialized. Check environment variables.</div>
        )
      ) : (
        <Dashboard session={session} />
      )}
    </div>
  );
}

export default App;
