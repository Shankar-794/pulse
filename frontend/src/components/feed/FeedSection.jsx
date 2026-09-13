import React from 'react';

export default function FeedSection({
  title,
  subtitle,
  badge,
  icon: Icon,
  count,
  children,
  action,
  className = ''
}) {
  return (
    <section className={`mb-10 ${className}`}>
      {/* Section Header */}
      <div className="flex items-center justify-between gap-4 pb-3 mb-5 border-b border-news-border">
        <div className="flex items-center gap-2.5 flex-wrap">
          {Icon && <Icon className="w-5 h-5 text-blue-600 dark:text-blue-400" />}
          <h2 className="text-lg font-bold text-news-text-primary tracking-tight flex items-center gap-2">
            {title}
            {count !== undefined && (
              <span className="text-xs px-2 py-0.5 bg-slate-100 dark:bg-neutral-800 text-slate-500 dark:text-neutral-400 rounded-full font-medium">
                {count}
              </span>
            )}
          </h2>
          {badge}
          {subtitle && (
            <span className="hidden sm:inline-block text-xs text-news-text-secondary border-l border-slate-200 dark:border-neutral-800 pl-3">
              {subtitle}
            </span>
          )}
        </div>
        {action && <div>{action}</div>}
      </div>

      {/* Section Content */}
      {children}
    </section>
  );
}
