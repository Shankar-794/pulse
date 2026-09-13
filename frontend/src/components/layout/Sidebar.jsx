import React, { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Compass,
  Globe,
  Cpu,
  Bot,
  FlaskConical,
  TrendingUp,
  ShieldAlert,
  Rocket,
  Bookmark,
  Hash,
  Search,
  Sliders,
  UserCheck
} from 'lucide-react';
import { StorageService } from '../../services/storage';

const NAV_ITEMS = [
  { to: '/for-you', label: 'For You', icon: Compass },
  { to: '/world', label: 'World', icon: Globe },
  { to: '/technology', label: 'Technology', icon: Cpu },
  { to: '/ai', label: 'AI', icon: Bot },
  { to: '/science', label: 'Science', icon: FlaskConical },
  { to: '/business', label: 'Business', icon: TrendingUp },
  { to: '/cybersecurity', label: 'Cybersecurity', icon: ShieldAlert },
  { to: '/space', label: 'Space', icon: Rocket },
];

const UTILITY_ITEMS = [
  { to: '/saved', label: 'Saved Stories', icon: Bookmark, isDynamicBadge: true },
  { to: '/topics', label: 'Topics', icon: Hash },
  { to: '/search', label: 'Search', icon: Search },
  { to: '/settings', label: 'Feed Preferences', icon: Sliders },
];

export default function Sidebar() {
  const location = useLocation();
  const [savedCount, setSavedCount] = useState(StorageService.getSavedStoryIds().length);

  useEffect(() => {
    const handleSavedUpdated = () => {
      setSavedCount(StorageService.getSavedStoryIds().length);
    };
    window.addEventListener('pulse_saved_updated', handleSavedUpdated);
    return () => {
      window.removeEventListener('pulse_saved_updated', handleSavedUpdated);
    };
  }, []);

  const isActiveRoute = (item) => {
    if (item.to === '/for-you' && (location.pathname === '/' || location.pathname === '/for-you')) {
      return true;
    }
    return location.pathname === item.to;
  };

  return (
    <aside className="w-full h-full flex flex-col justify-between select-none py-4 px-3 overflow-y-auto">
      {/* Navigation Streams */}
      <div className="space-y-6">
        <div>
          <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 dark:text-neutral-500 uppercase">
            News Sections
          </div>
          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const active = isActiveRoute(item);
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                    active
                      ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 font-semibold'
                      : 'text-slate-600 dark:text-neutral-400 hover:bg-slate-100 dark:hover:bg-neutral-800/60 hover:text-slate-900 dark:hover:text-neutral-100'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${active ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400 dark:text-neutral-500'}`} />
                    <span>{item.label}</span>
                  </div>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Reading List & Settings */}
        <div>
          <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 dark:text-neutral-500 uppercase">
            Your Library
          </div>
          <nav className="space-y-1">
            {UTILITY_ITEMS.map((item) => {
              const active = location.pathname === item.to;
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                    active
                      ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 font-semibold'
                      : 'text-slate-600 dark:text-neutral-400 hover:bg-slate-100 dark:hover:bg-neutral-800/60 hover:text-slate-900 dark:hover:text-neutral-100'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${active ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400 dark:text-neutral-500'}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.isDynamicBadge && savedCount > 0 && (
                    <span className="text-xs px-2 py-0.5 bg-slate-100 dark:bg-neutral-800 text-slate-600 dark:text-neutral-300 rounded-full font-medium">
                      {savedCount}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Reader Profile Footer */}
      <div className="pt-4 border-t border-news-border">
        <div className="flex items-center gap-3 p-2.5 rounded-lg bg-slate-50 dark:bg-[#121316] border border-news-border">
          <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center text-blue-600 dark:text-blue-400 shrink-0">
            <UserCheck className="w-4 h-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold text-news-text-primary truncate">
              Technology Student
            </div>
            <div className="text-[11px] text-news-text-secondary truncate">
              AI · Systems · Software
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
