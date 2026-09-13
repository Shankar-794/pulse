import React from 'react';
import { Link } from 'react-router-dom';
import { Bookmark, BookmarkCheck, EyeOff, ArrowUpRight, Sparkles } from 'lucide-react';
import CategoryBadge from '../common/CategoryBadge';
import ImportanceBadge from '../common/ImportanceBadge';
import SourceBadge from '../common/SourceBadge';

export default function NewsCard({
  story,
  onSaveToggle,
  onHide,
  variant = 'standard' // 'featured' | 'standard' | 'compact'
}) {
  if (!story) return null;

  const isSaved = story.is_saved;
  const isLead = variant === 'featured' || story.is_breaking;
  const primarySource = story.articles && story.articles.length > 0 ? story.articles[0].source_name : null;

  if (variant === 'compact') {
    return (
      <article className="group bg-news-surface hover:bg-slate-50 dark:hover:bg-[#1E1F26] border border-news-border transition-all duration-150 p-4 rounded-xl flex items-start justify-between gap-4 shadow-card">
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-center gap-2.5 flex-wrap text-xs">
            <CategoryBadge category={story.category} topic={story.primary_topic} />
            {story.breaking_level === 'BREAKING' && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200 dark:border-rose-900/60">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                <span>Breaking</span>
              </span>
            )}
            {story.story_status === 'DEVELOPING' && story.breaking_level !== 'BREAKING' && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-200 dark:border-blue-900/60">
                Developing
              </span>
            )}
            <ImportanceBadge score={story.importance_score} tier={story.importance_tier} isBreaking={story.is_breaking} />
            <SourceBadge sourceName={primarySource} sourceCount={story.source_count} timestamp={story.created_at} />
          </div>
          <Link
            to={`/story/${story.id}`}
            className="block font-sans font-semibold text-news-text-primary group-hover:text-blue-600 dark:group-hover:text-blue-400 text-base leading-snug line-clamp-2 transition-colors"
          >
            {story.title}
          </Link>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 pt-1">
          <button
            type="button"
            onClick={() => onSaveToggle(story.id)}
            title={isSaved ? "Saved" : "Save Story"}
            className={`p-1.5 rounded-lg transition-colors ${
              isSaved
                ? 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50'
                : 'text-slate-400 hover:text-slate-700 dark:hover:text-neutral-200 hover:bg-slate-100 dark:hover:bg-neutral-800'
            }`}
          >
            {isSaved ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
          </button>
          <Link
            to={`/story/${story.id}`}
            className="p-1.5 text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-neutral-800 rounded-lg transition-colors"
            title="Read Story"
          >
            <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>
      </article>
    );
  }

  return (
    <article
      className={`group bg-news-surface hover:bg-slate-50/50 dark:hover:bg-[#1D1E24] border transition-all duration-150 rounded-xl flex flex-col justify-between shadow-card hover:shadow-card-hover ${
        isLead
          ? 'border-red-200 dark:border-red-950/60 p-5 sm:p-6'
          : 'border-news-border p-5'
      }`}
    >
      <div>
        {/* Top Header Row: Category, Breaking Tag, Source, Date */}
        <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
          <div className="flex items-center gap-2.5 flex-wrap">
            <CategoryBadge category={story.category} topic={story.primary_topic} />
            {story.breaking_level === 'BREAKING' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200 dark:border-rose-900/60">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                <span>Breaking</span>
              </span>
            )}
            {story.story_status === 'DEVELOPING' && story.breaking_level !== 'BREAKING' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-200 dark:border-blue-900/60">
                Developing
              </span>
            )}
            {story.story_status === 'ESCALATING' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-900/60">
                Escalating
              </span>
            )}
            <ImportanceBadge score={story.importance_score} tier={story.importance_tier} isBreaking={story.is_breaking} />
            {story.is_global_override && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-800/80">
                Global Event
              </span>
            )}
          </div>
          <SourceBadge sourceName={primarySource} sourceCount={story.source_count} timestamp={story.created_at} />
        </div>


        {/* Headline */}
        <h2 className="mb-2.5">
          <Link
            to={`/story/${story.id}`}
            className={`block font-sans font-bold text-news-text-primary group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors leading-snug tracking-tight ${
              isLead ? 'text-xl sm:text-2xl' : 'text-lg sm:text-xl'
            }`}
          >
            {story.title}
          </Link>
        </h2>

        {/* Editorial Summary */}
        <p className="text-news-text-secondary font-sans text-sm leading-relaxed mb-4 line-clamp-3">
          {story.summary}
        </p>

        {/* Personal Relevance Justification */}
        {story.relevance_reason && (
          <div className="mb-4 py-2 px-3 bg-blue-50/70 dark:bg-blue-950/30 border-l-2 border-blue-500 rounded-r-md text-xs text-blue-900 dark:text-blue-200 flex items-start gap-2">
            <Sparkles className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <span className="leading-snug">{story.relevance_reason}</span>
          </div>
        )}
      </div>

      {/* Card Action Footer */}
      <div className="pt-4 border-t border-news-border flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <Link
            to={`/story/${story.id}`}
            className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-blue-600 dark:bg-neutral-800 dark:hover:bg-blue-600 text-white rounded-lg font-medium transition-colors"
          >
            <span>Read Story</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
          <button
            type="button"
            onClick={() => onSaveToggle(story.id)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors ${
              isSaved
                ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-900/60 font-medium'
                : 'bg-white dark:bg-neutral-800/80 text-slate-600 dark:text-neutral-300 border-news-border hover:bg-slate-50 dark:hover:bg-neutral-700'
            }`}
          >
            {isSaved ? <BookmarkCheck className="w-3.5 h-3.5" /> : <Bookmark className="w-3.5 h-3.5 text-slate-400" />}
            <span>{isSaved ? 'Saved' : 'Save'}</span>
          </button>
        </div>

        {onHide && (
          <button
            type="button"
            onClick={() => onHide(story.id)}
            title="Not interested"
            className="text-slate-400 hover:text-slate-600 dark:hover:text-neutral-200 p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-neutral-800 transition-colors flex items-center gap-1"
          >
            <EyeOff className="w-3.5 h-3.5" />
            <span className="hidden sm:inline text-xs">Hide</span>
          </button>
        )}
      </div>
    </article>
  );
}
