import React from 'react';
import { BrowserRouter, HashRouter, Routes, Route, Link, Navigate } from 'react-router-dom';
import Dashboard from './Dashboard';
import WatchfulEyeLogo from './components/WatchfulEyeLogo';
import ChimeraCockpit from './components/ChimeraCockpit';
import FigmaPreview from './FigmaPreview';

function App() {
  const isFigmaMode = process.env.REACT_APP_FIGMA_MODE === 'true';
  const RouterImpl = isFigmaMode ? HashRouter : BrowserRouter;
  const isAuthed = isFigmaMode || !!localStorage.getItem('auth_token');
  return (
    <RouterImpl>
      <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
        {/* Navigation (hidden until authenticated) */}
        {isAuthed && (
          <nav className="bg-white dark:bg-slate-800 shadow-sm border-b border-gray-200 dark:border-slate-700">
            <div className="w-full px-0 sm:px-4 lg:px-8">
              <div className="flex justify-between h-16">
                <div className="flex items-center text-gray-900 dark:text-gray-100">
                  <WatchfulEyeLogo size={22} textClassName="text-xl" />
                </div>
                <div className="flex items-center space-x-4">
                  <Link 
                    to="/" 
                    className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 px-3 py-2 rounded-md text-sm font-medium"
                  >
                    {isFigmaMode ? 'Figma Preview' : 'Dashboard'}
                  </Link>
                  <div className="relative">
                    <span 
                      className="text-gray-400 px-3 py-2 rounded-md text-sm font-medium cursor-not-allowed blur-sm opacity-50"
                      title="Feature under development"
                    >
                      Chimera Intelligence
                    </span>
                    <div className="absolute inset-0 bg-gray-200/20 rounded-md pointer-events-none"></div>
                  </div>
                </div>
              </div>
            </div>
          </nav>
        )}

        {/* Routes */}
        <Routes>
          <Route path="/" element={isFigmaMode ? <FigmaPreview /> : <Dashboard />} />
          <Route path="/chimera" element={isAuthed ? <ChimeraCockpit /> : <Navigate to="/" replace />} />
        </Routes>
      </div>
    </RouterImpl>
  );
}

export default App;
