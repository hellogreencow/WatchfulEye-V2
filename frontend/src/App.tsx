import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import Dashboard from './Dashboard';
import ThemeToggle from './components/ThemeToggle';
import WatchfulEyeLogo from './components/WatchfulEyeLogo';
import ChimeraCockpit from './components/ChimeraCockpit';

function App() {
  const isAuthed = !!localStorage.getItem('auth_token');
  return (
    <Router>
      <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
        {/* Navigation (hidden until authenticated) */}
        {isAuthed && (
          <nav className="bg-white dark:bg-slate-900 shadow-sm border-b border-slate-200 dark:border-slate-700">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between h-16">
                <div className="flex items-center text-gray-900 dark:text-white">
                  <WatchfulEyeLogo size={22} textClassName="text-xl" />
                </div>
                <div className="flex items-center space-x-4">
                  <Link 
                    to="/" 
                    className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white px-3 py-2 rounded-md text-sm font-medium"
                  >
                    Dashboard
                  </Link>
                  <Link 
                    to="/chimera" 
                    className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white px-3 py-2 rounded-md text-sm font-medium"
                  >
                    Chimera Intelligence
                  </Link>
                </div>
              </div>
            </div>
          </nav>
        )}

        {/* Routes */}
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chimera" element={isAuthed ? <ChimeraCockpit /> : <Navigate to="/" replace />} />
        </Routes>
        {/* Always-available theme toggle */}
        <ThemeToggle />
      </div>
    </Router>
  );
}

export default App;
