import React from 'react';

export default function SourceBadge({ sourceCount = 1, timestamp, sourceName, className = '' }) {
  const formatTimeAgo = (isoString) => {
    if (!isoString) return 'recently';
    const date = new Date(isoString);
    const diffHours = Math.max(1, Math.round((Date.now() - date.getTime()) / (1000 * 60 * 60)));
    if (diffHours < 24) {
      return `${diffHours}h ago`;
    }
    const days = Math.floor(diffHours / 24);
    return `${days}d ago`;
  };

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs text-news-text-secondary ${className}`}>
      {sourceName && (
        <span className="font-semibold text-news-text-primary">{sourceName}</span>
      )}
      {sourceCount > 1 && (
        <>
          <span className="text-slate-300 dark:text-neutral-600">·</span>
          <span>{sourceCount} sources</span>
        </>
      )}
      <span className="text-slate-300 dark:text-neutral-600">·</span>
      <span>{formatTimeAgo(timestamp)}</span>
    </span>
  );
}
