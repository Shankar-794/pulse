import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Check, CheckCheck, RefreshCw, Sparkles, Flame, ShieldAlert, ArrowUpRight } from 'lucide-react';

const INITIAL_NOTIFICATIONS = [
  {
    id: 'notif-1',
    title: 'Live feed updated',
    description: '166 articles synchronized from 8 verified sources',
    time: 'Just now',
    category: 'System',
    read: false,
    link: '/for-you'
  },
  {
    id: 'notif-2',
    title: 'AI research benchmark published',
    description: 'Anthropic researcher warning on AI model development',
    time: '15m ago',
    category: 'AI',
    read: false,
    link: '/ai'
  },
  {
    id: 'notif-3',
    title: 'NASA APOD release',
    description: 'Comet NEOWISE observation update from deep space sensors',
    time: '1h ago',
    category: 'Space',
    read: false,
    link: '/space'
  }
];

export default function NotificationPopover() {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState(INITIAL_NOTIFICATIONS);
  const popoverRef = useRef(null);
  const buttonRef = useRef(null);
  const navigate = useNavigate();

  const unreadCount = notifications.filter((n) => !n.read).length;

  // Handle outside click & escape key
  useEffect(() => {
    function handleClickOutside(event) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target)
      ) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
        buttonRef.current?.focus();
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('touchstart', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const handleMarkAllAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const handleItemClick = (notif) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === notif.id ? { ...n, read: true } : n))
    );
    setIsOpen(false);
    if (notif.link) {
      navigate(notif.link);
    }
  };

  return (
    <div className="relative inline-block text-left">
      {/* Notification Bell Button */}
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        title="Notifications"
        aria-expanded={isOpen}
        aria-label="Open notifications menu"
        className={`p-2 rounded-full transition-colors relative ${
          isOpen
            ? 'bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400 ring-2 ring-blue-500/20'
            : 'text-slate-600 dark:text-neutral-400 hover:text-slate-900 dark:hover:text-neutral-100 hover:bg-slate-100 dark:hover:bg-neutral-800/80'
        }`}
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-blue-600 dark:bg-blue-500 rounded-full ring-2 ring-white dark:ring-[#18191E]" />
        )}
      </button>

      {/* Anchored Popover */}
      {isOpen && (
        <div
          ref={popoverRef}
          role="dialog"
          aria-label="Notifications panel"
          className="absolute right-0 top-full mt-2 w-80 sm:w-96 max-w-[calc(100vw-2rem)] bg-news-surface border border-news-border rounded-xl shadow-popover z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-100"
        >
          {/* Popover Header */}
          <div className="px-4 py-3 border-b border-news-border flex items-center justify-between gap-2 bg-slate-50/50 dark:bg-[#121316]/50">
            <div>
              <h3 className="font-semibold text-sm text-news-text-primary">
                Notifications
              </h3>
              <p className="text-[11px] text-news-text-secondary">
                {unreadCount > 0 ? `${unreadCount} unread update${unreadCount === 1 ? '' : 's'}` : 'All caught up'}
              </p>
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllAsRead}
                className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                <span>Mark all as read</span>
              </button>
            )}
          </div>

          {/* Notifications List */}
          <div className="max-h-[70vh] overflow-y-auto divide-y divide-news-border">
            {notifications.length === 0 || unreadCount === 0 && notifications.every((n) => n.read) && notifications.length === 0 ? (
              <div className="p-8 text-center space-y-2">
                <Check className="w-8 h-8 text-slate-300 dark:text-neutral-600 mx-auto" />
                <p className="text-sm font-semibold text-news-text-primary">No new updates</p>
                <p className="text-xs text-news-text-secondary">You're all caught up.</p>
              </div>
            ) : (
              notifications.map((notif) => (
                <button
                  key={notif.id}
                  type="button"
                  onClick={() => handleItemClick(notif)}
                  className={`w-full text-left p-3.5 hover:bg-slate-50 dark:hover:bg-[#1D1E24] transition-colors flex items-start gap-3 ${
                    !notif.read ? 'bg-blue-50/30 dark:bg-blue-950/10' : ''
                  }`}
                >
                  <div className="mt-0.5 shrink-0">
                    {!notif.read ? (
                      <span className="w-2 h-2 rounded-full bg-blue-600 dark:bg-blue-400 block mt-1" />
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-slate-300 dark:bg-neutral-700 block mt-1" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-medium text-blue-600 dark:text-blue-400 uppercase tracking-wider">
                        {notif.category}
                      </span>
                      <span className="text-[10px] text-news-text-muted">
                        {notif.time}
                      </span>
                    </div>
                    <div className="text-xs font-semibold text-news-text-primary leading-snug">
                      {notif.title}
                    </div>
                    <div className="text-xs text-news-text-secondary line-clamp-2 leading-relaxed">
                      {notif.description}
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-2.5 border-t border-news-border bg-slate-50/50 dark:bg-[#121316]/50 flex items-center justify-between text-[11px] text-news-text-secondary">
            <span>Verified RSS Wire Alerts</span>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                navigate('/settings');
              }}
              className="hover:text-news-text-primary hover:underline"
            >
              Configure alerts
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
