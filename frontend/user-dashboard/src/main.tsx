// @ts-ignore - React import is needed for JSX in some environments
import React, { StrictMode, Suspense } from 'react' // Import Suspense
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import './i18n'; // Import i18n configuration to initialize it

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* Wrap App with Suspense for loading translations */}
    <Suspense fallback={<div>Loading translations...</div>}>
      <App />
    </Suspense>
  </StrictMode>,
)
