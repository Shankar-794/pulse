import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { LoginModal } from './components/auth/LoginModal';
import AppLayout from './components/layout/AppLayout';
import ForYouPage from './pages/ForYouPage';
import CategoryFeedPage from './pages/CategoryFeedPage';
import StoryDetailPage from './pages/StoryDetailPage';
import SearchPage from './pages/SearchPage';
import SavedPage from './pages/SavedPage';
import TopicsPage from './pages/TopicsPage';
import SettingsPage from './pages/SettingsPage';
import OperationsPage from './pages/OperationsPage';
import { AuthCallbackPage } from './pages/AuthCallbackPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <LoginModal />
        <Routes>
          {/* OAuth Callback route outside main layout */}
          <Route path="/auth/callback" element={<AuthCallbackPage />} />

          <Route element={<AppLayout />}>
            {/* Main Feed Routes */}
            <Route path="/" element={<ForYouPage />} />
            <Route path="/for-you" element={<ForYouPage />} />

            {/* Intelligence Category Feeds */}
            <Route path="/world" element={<CategoryFeedPage category="world" />} />
            <Route path="/technology" element={<CategoryFeedPage category="technology" />} />
            <Route path="/ai" element={<CategoryFeedPage category="ai" />} />
            <Route path="/science" element={<CategoryFeedPage category="science" />} />
            <Route path="/business" element={<CategoryFeedPage category="business" />} />
            <Route path="/economy" element={<CategoryFeedPage category="economy" />} />
            <Route path="/cybersecurity" element={<CategoryFeedPage category="cybersecurity" />} />
            <Route path="/space" element={<CategoryFeedPage category="space" />} />
            <Route path="/category/:category" element={<CategoryFeedPage />} />

            {/* Story Detail Page */}
            <Route path="/story/:id" element={<StoryDetailPage />} />

            {/* Workspace Routes */}
            <Route path="/saved" element={<SavedPage />} />
            <Route path="/topics" element={<TopicsPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/settings" element={<SettingsPage />} />

            {/* System Operations */}
            <Route path="/operations" element={<OperationsPage />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/for-you" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
