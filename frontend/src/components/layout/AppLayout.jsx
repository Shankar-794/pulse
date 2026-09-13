import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Header from './Header';
import Sidebar from './Sidebar';

export default function AppLayout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="h-screen flex flex-col bg-news-canvas text-news-text-primary antialiased overflow-hidden font-sans selection:bg-blue-100 selection:text-blue-900 dark:selection:bg-blue-950 dark:selection:text-blue-200">
      {/* Fixed Top Header */}
      <Header onToggleMobileMenu={() => setMobileMenuOpen((prev) => !prev)} />

      {/* Main Container - Full height minus header */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Fixed Left Sidebar - Desktop */}
        <div className="hidden md:flex flex-col w-64 h-full shrink-0 border-r border-news-border bg-news-surface z-20">
          <Sidebar />
        </div>

        {/* Mobile Slide-over Drawer */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-40 md:hidden">
            {/* Backdrop */}
            <div
              className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
              onClick={() => setMobileMenuOpen(false)}
            />
            {/* Drawer */}
            <div className="relative w-72 max-w-[80vw] h-full bg-news-surface border-r border-news-border shadow-2xl z-50 flex flex-col">
              <Sidebar onCloseMobile={() => setMobileMenuOpen(false)} />
            </div>
          </div>
        )}

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
