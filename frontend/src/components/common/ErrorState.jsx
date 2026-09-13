import React from 'react';
import { AlertCircle, RotateCcw } from 'lucide-react';

export default function ErrorState({
  title = 'Something went wrong',
  message = "We couldn't load this right now. Please try again.",
  onRetry,
  actionText = 'Retry'
}) {
  return (
    <div className="p-12 sm:p-16 bg-news-surface border border-news-border rounded-xl text-center space-y-4 max-w-md mx-auto shadow-card">
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/50 text-red-600 dark:text-red-400">
        <AlertCircle className="w-6 h-6" />
      </div>
      <div>
        <h3 className="text-lg font-bold text-news-text-primary">
          {title}
        </h3>
        <p className="text-sm text-news-text-secondary leading-relaxed mt-1">
          {message}
        </p>
      </div>
      {onRetry && (
        <div className="pt-2">
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-sm transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>{actionText}</span>
          </button>
        </div>
      )}
    </div>
  );
}
