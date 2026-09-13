import React from 'react';
import { Outlet } from 'react-router-dom';
import Header from './Header';
import Sidebar from './Sidebar';

export default function AppLayout() {
  return (
    <div className="h-screen flex flex-col bg-news-canvas text-news-text-primary antialiased overflow-hidden font-sans selection:bg-blue-100 selection:text-blue-900 dark:selection:bg-blue-950 dark:selection:text-blue-200">
      {/* Fixed Top Header */}
      <Header />

      {/* Main Container - Full height minus header */}
      <div className="flex-1 flex overflow-hidden">
        {/* Fixed Left Sidebar - Stays anchored when page scrolls */}
        <div className="hidden md:flex flex-col w-64 h-full shrink-0 border-r border-news-border bg-news-surface z-20">
          <Sidebar />
        </div>

        {/* Scrollable Content Area */}
        <main className="flex-1 h-full overflow-y-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="max-w-5xl mx-auto pb-12">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
