import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Search, Settings, Sun, Moon, Newspaper } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';
import NotificationPopover from './NotificationPopover';

export default function Header() {
  const navigate = useNavigate();
  const { theme, toggleTheme, isDark } = useTheme();
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery('');
    }
  };

  return (
    <header className="h-16 shrink-0 bg-news-surface border-b border-news-border px-4 sm:px-6 flex items-center justify-between gap-6 z-30 transition-colors">
      {/* Left: Brand Identity */}
      <div className="flex items-center gap-6 shrink-0">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm transition-transform group-hover:scale-105">
            <Newspaper className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-sans font-bold text-news-text-primary tracking-tight text-xl">
                Pulse
              </span>
              <span className="text-[11px] font-medium px-2 py-0.5 bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 rounded-full">
                Personalized News
              </span>
            </div>
            <p className="text-xs text-news-text-secondary tracking-normal hidden sm:block">
              Your world, filtered intelligently.
            </p>
          </div>
        </Link>
      </div>

      {/* Center: Large Clean Search Bar */}
      <form onSubmit={handleSearchSubmit} className="flex-1 max-w-xl hidden md:block">
        <div className="relative flex items-center">
          <Search className="absolute left-3.5 w-4 h-4 text-slate-400 dark:text-neutral-500 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search the news..."
            className="w-full bg-slate-50 dark:bg-[#121316] border border-news-border focus:border-blue-500 focus:bg-white dark:focus:bg-[#16171B] text-news-text-primary text-sm font-sans placeholder:text-slate-400 dark:placeholder:text-neutral-500 rounded-full pl-10 pr-10 py-2 outline-none transition-all"
          />
        </div>
      </form>

      {/* Right: Actions, Live Indicator, Theme Toggle, Settings */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Subtle Live Feed Indicator */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-800/40 rounded-full text-xs font-medium text-emerald-700 dark:text-emerald-400">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Live Feed Active</span>
        </div>

        {/* Anchored Notifications Popover */}
        <NotificationPopover />

        {/* Theme Toggle (Light / Dark Mode) */}
        <button
          type="button"
          onClick={toggleTheme}
          title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
          aria-label="Toggle theme"
          className="p-2 text-slate-600 dark:text-neutral-400 hover:text-slate-900 dark:hover:text-neutral-100 hover:bg-slate-100 dark:hover:bg-neutral-800/80 rounded-full transition-colors"
        >
          {isDark ? (
            <Sun className="w-4 h-4 text-amber-400 transition-transform hover:rotate-45" />
          ) : (
            <Moon className="w-4 h-4 text-slate-600 transition-transform hover:-rotate-12" />
          )}
        </button>

        {/* Profile / Settings Link */}
        <Link
          to="/settings"
          title="Settings & Preferences"
          className="p-2 text-slate-600 dark:text-neutral-400 hover:text-slate-900 dark:hover:text-neutral-100 hover:bg-slate-100 dark:hover:bg-neutral-800/80 rounded-full transition-colors"
        >
          <Settings className="w-4 h-4" />
        </Link>
      </div>
    </header>
  );
}

