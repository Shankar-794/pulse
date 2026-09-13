import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import ForYouPage from './pages/ForYouPage';
import CategoryFeedPage from './pages/CategoryFeedPage';
import StoryDetailPage from './pages/StoryDetailPage';
import SearchPage from './pages/SearchPage';
import SavedPage from './pages/SavedPage';
import TopicsPage from './pages/TopicsPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          {/* Main Feed Routes */}
          <Route path="/" element={<ForYouPage />} />
          <Route path="/for-you" element={<ForYouPage />} />

          {/* Intelligence Category Feeds */}
          <Route path="/world" element={<CategoryFeedPage />} />
          <Route path="/technology" element={<CategoryFeedPage />} />
          <Route path="/ai" element={<CategoryFeedPage />} />
          <Route path="/science" element={<CategoryFeedPage />} />
          <Route path="/business" element={<CategoryFeedPage />} />
          <Route path="/cybersecurity" element={<CategoryFeedPage />} />
          <Route path="/space" element={<CategoryFeedPage />} />

          {/* Story Detail Page */}
          <Route path="/story/:id" element={<StoryDetailPage />} />

          {/* Workspace Routes */}
          <Route path="/saved" element={<SavedPage />} />
          <Route path="/topics" element={<TopicsPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/settings" element={<SettingsPage />} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/for-you" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
