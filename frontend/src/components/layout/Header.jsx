import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Search, Settings, Sun, Moon, Newspaper, LogOut, Bookmark, LogIn, ChevronDown, Menu } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';
import { useAuth } from '../../context/AuthContext';
import NotificationPopover from './NotificationPopover';

export default function Header({ onToggleMobileMenu }) {
  const navigate = useNavigate();
  const { toggleTheme, isDark } = useTheme();
  const { user, isAuthenticated, logout, openLoginModal, savedCount } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef(null);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery('');
    }
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target)) {
        setIsProfileMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getInitials = (name, email) => {
    if (name) {
      const parts = name.trim().split(' ');
      if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
      return name.slice(0, 2).toUpperCase();
    }
    if (email) return email.slice(0, 2).toUpperCase();
    return 'U';
  };

  return (
    <header className="h-16 shrink-0 bg-news-surface border-b border-news-border px-4 sm:px-6 flex items-center justify-between gap-6 z-30 transition-colors">
      {/* Left: Brand Identity */}
      <div className="flex items-center gap-3 sm:gap-6 shrink-0">
        <button
          type="button"
          onClick={onToggleMobileMenu}
          className="p-1.5 md:hidden text-slate-600 dark:text-neutral-400 hover:text-slate-900 dark:hover:text-neutral-100 hover:bg-slate-100 dark:hover:bg-neutral-800/80 rounded-lg transition-colors"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>
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

      {/* Right: Actions, Live Indicator, Theme Toggle, User Profile */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        {/* Subtle Live Feed Indicator linking to Operations */}
        <Link
          to="/operations"
          title="System Operations & Pipeline Health"
          className="flex items-center gap-2 px-2.5 sm:px-3 py-1 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-800/40 rounded-full text-xs font-medium text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 transition-colors"
        >
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
          <span className="hidden sm:inline">Live Feed Active</span>
          <span className="sm:hidden">Live</span>
        </Link>

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

        {/* Settings Shortcut */}
        <Link
          to="/settings"
          title="Settings & Preferences"
          className="p-2 text-slate-600 dark:text-neutral-400 hover:text-slate-900 dark:hover:text-neutral-100 hover:bg-slate-100 dark:hover:bg-neutral-800/80 rounded-full transition-colors"
        >
          <Settings className="w-4 h-4" />
        </Link>

        {/* User Authentication Profile or Sign In Button */}
        {isAuthenticated && user ? (
          <div className="relative" ref={profileMenuRef}>
            <button
              onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)}
              className="flex items-center gap-2 pl-2 pr-2.5 py-1 rounded-full bg-slate-100 dark:bg-neutral-800/80 hover:bg-slate-200 dark:hover:bg-neutral-700/80 border border-slate-200 dark:border-neutral-700 text-xs font-medium text-news-text-primary transition-all"
              aria-expanded={isProfileMenuOpen}
              aria-haspopup="true"
            >
              {user.picture_url ? (
                <img
                  src={user.picture_url}
                  alt={user.full_name || user.email}
                  className="w-6 h-6 rounded-full object-cover"
                />
              ) : (
                <div className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-[10px]">
                  {getInitials(user.full_name, user.email)}
                </div>
              )}
              <span className="hidden sm:inline max-w-[100px] truncate">
                {user.full_name || user.email.split('@')[0]}
              </span>
              <ChevronDown className="w-3 h-3 text-slate-400 dark:text-neutral-500" />
            </button>

            {/* Profile Dropdown Menu */}
            {isProfileMenuOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-neutral-900 border border-slate-200 dark:border-neutral-700 rounded-xl shadow-xl py-1.5 z-50 animate-fade-in">
                <div className="px-3.5 py-2 border-b border-slate-100 dark:border-neutral-800">
                  <p className="text-xs font-semibold text-news-text-primary truncate">
                    {user.full_name || 'Pulse Operator'}
                  </p>
                  <p className="text-[11px] text-news-text-secondary truncate mt-0.5">
                    {user.email}
                  </p>
                  <div className="mt-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300">
                    {user.oauth_provider === 'google' ? 'Google Account' : 'Authenticated User'}
                  </div>
                </div>

                <div className="py-1">
                  <Link
                    to="/saved"
                    onClick={() => setIsProfileMenuOpen(false)}
                    className="flex items-center justify-between px-3.5 py-2 text-xs text-news-text-primary hover:bg-slate-50 dark:hover:bg-neutral-800 transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <Bookmark className="w-3.5 h-3.5 text-blue-500" />
                      Saved Stories
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 dark:bg-neutral-800 font-semibold">
                      {savedCount}
                    </span>
                  </Link>
                  <Link
                    to="/settings"
                    onClick={() => setIsProfileMenuOpen(false)}
                    className="flex items-center gap-2 px-3.5 py-2 text-xs text-news-text-primary hover:bg-slate-50 dark:hover:bg-neutral-800 transition-colors"
                  >
                    <Settings className="w-3.5 h-3.5 text-slate-400" />
                    Personalization
                  </Link>
                </div>

                <div className="border-t border-slate-100 dark:border-neutral-800 pt-1">
                  <button
                    onClick={() => {
                      setIsProfileMenuOpen(false);
                      logout();
                    }}
                    className="w-full flex items-center gap-2 px-3.5 py-2 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors text-left"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <button
            type="button"
            onClick={openLoginModal}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-sm transition-all active:scale-95"
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Sign In</span>
          </button>
        )}
      </div>
    </header>
  );
}


