import React from 'react';
import { Check, Plus, Hash } from 'lucide-react';
import CategoryBadge from '../common/CategoryBadge';

export default function TopicCard({ topic, onToggleFollow }) {
  if (!topic) return null;

  const isFollowed = topic.is_followed;

  const formatFollowers = (count) => {
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}k followers`;
    }
    return `${count} followers`;
  };

  return (
    <div className={`p-5 rounded-xl border transition-all duration-150 flex flex-col justify-between shadow-card hover:shadow-card-hover ${
      isFollowed 
        ? 'bg-blue-50/40 dark:bg-blue-950/20 border-blue-200 dark:border-blue-900/50' 
        : 'bg-news-surface border-news-border'
    }`}>
      <div>
        <div className="flex items-center justify-between gap-2 mb-3">
          <CategoryBadge category={topic.category} />
          <span className="text-xs text-news-text-secondary">
            {formatFollowers(topic.follower_count)}
          </span>
        </div>

        <div className="flex items-center gap-2 mb-2">
          <Hash className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          <h3 className="font-sans font-bold text-news-text-primary text-base">
            {topic.name}
          </h3>
        </div>

        <p className="text-xs text-news-text-secondary leading-relaxed line-clamp-2 mb-5">
          {topic.description}
        </p>
      </div>

      <div className="pt-3 border-t border-news-border flex items-center justify-between text-xs">
        <span className="text-news-text-secondary">
          #{topic.slug}
        </span>
        <button
          type="button"
          onClick={() => onToggleFollow(topic.id, !isFollowed)}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            isFollowed
              ? 'bg-blue-600 text-white hover:bg-red-600'
              : 'bg-slate-100 dark:bg-neutral-800 hover:bg-slate-200 dark:hover:bg-neutral-700 text-slate-700 dark:text-neutral-200'
          }`}
        >
          {isFollowed ? (
            <>
              <Check className="w-3.5 h-3.5" />
              <span>Following</span>
            </>
          ) : (
            <>
              <Plus className="w-3.5 h-3.5" />
              <span>Follow</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
