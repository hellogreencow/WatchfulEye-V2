import React from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom';
import Dashboard from './Dashboard';
import WatchfulEyeLogo from './components/WatchfulEyeLogo';
import ChimeraCockpit from './components/ChimeraCockpit';
import FigmaPreview from './FigmaPreview';
import { LandingPage } from './components/landing/LandingPage';
import { NewsPage } from './components/landing/NewsPage';
import { Login } from './components/landing/Login';
import { ManifestoSection } from './components/landing/ManifestoSection';
import { AuthProvider } from './Dashboard';

function App() {
  // IMPORTANT: The app must remain functional even if a build is accidentally produced with
  // REACT_APP_FIGMA_MODE enabled. Figma preview must never take over the homepage.
  const isFigmaMode = process.env.REACT_APP_FIGMA_MODE === 'true';
  // Don't check auth_token here - let Dashboard handle its own auth
  // This ensures landing page always shows for unauthenticated users
  const hasAuthToken = !!localStorage.getItem('auth_token');
  
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
        {/* Routes */}
        <Routes>
          {/* Public Landing Page - Always show landing page, Dashboard will handle its own auth */}
          <Route path="/" element={<LandingPage />} />
          
          {/* Public Pages */}
          <Route path="/news" element={<NewsPage />} />
          <Route path="/login" element={
            <AuthProvider>
              <Login onLogin={() => window.location.href = '/dashboard'} />
            </AuthProvider>
          } />
          <Route path="/features" element={<ManifestoSection />} />
          
          {/* Authenticated Routes - Dashboard handles its own auth check */}
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/chimera" element={hasAuthToken ? <ChimeraCockpit /> : <Navigate to="/login" replace />} />
          
          {/* Figma Preview (if enabled) */}
          {isFigmaMode && <Route path="/figma-preview" element={<FigmaPreview />} />}
          
          {/* Catch all - redirect to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
