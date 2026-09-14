import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Bookmark,
  BookmarkCheck,
  Share2,
  ExternalLink,
  Clock,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Tag,
  Building2,
  AlertCircle,
  TrendingUp,
  Scale
} from 'lucide-react';
import { ApiService } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { addPendingAction } from '../services/pendingActions';
import CategoryBadge from '../components/common/CategoryBadge';
import ImportanceBadge from '../components/common/ImportanceBadge';
import SourceBadge from '../components/common/SourceBadge';
import NewsCard from '../components/feed/NewsCard';

function formatTimeAgo(isoStr) {
  if (!isoStr) return '';
  try {
    const dt = new Date(isoStr);
    const now = new Date();
    const diffMs = Math.max(0, now - dt);
    const mins = Math.floor(diffMs / 60000);
    if (mins < 60) return `${mins} min ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} hr ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return '';
  }
}

function formatTimelineDate(dateStr) {
  if (!dateStr) return '';
  try {
    const dt = new Date(dateStr);
    if (isNaN(dt.getTime())) return dateStr;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = months[dt.getMonth()];
    const day = dt.getDate();
    const hours = String(dt.getHours()).padStart(2, '0');
    const mins = String(dt.getMinutes()).padStart(2, '0');
    return `${month} ${day} · ${hours}:${mins}`;
  } catch {
    return dateStr;
  }
}

export default function StoryDetailPage() {
  const { isAuthenticated, openLoginModal } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();

  const [story, setStory] = useState(null);
  const [relatedStories, setRelatedStories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);

    ApiService.getStoryById(id).then((foundStory) => {
      if (!mounted) return;
      setStory(foundStory);

      if (foundStory) {
        ApiService.getStories({ category: foundStory.category }).then((allCat) => {
          if (!mounted) return;
          const related = (allCat.items || [])
            .filter((s) => s.id !== foundStory.id)
            .slice(0, 2);
          setRelatedStories(related);
          setLoading(false);
        });
      } else {
        setLoading(false);
      }
    });

    return () => {
      mounted = false;
    };
  }, [id]);

  const handleSaveToggle = async () => {
    if (!story) return;
    if (!isAuthenticated) {
      const actionType = story.is_saved ? 'UNSAVE_STORY' : 'SAVE_STORY';
      addPendingAction(actionType, { storyId: story.id });
      openLoginModal({
        title: 'Sign in to personalize Pulse',
        message: 'Your action will be saved and completed after you sign in.'
      });
      return;
    }

    const willSave = !story.is_saved;
    try {
      if (willSave) {
        await ApiService.saveStory(story.id);
      } else {
        await ApiService.unsaveStory(story.id);
      }
      setStory((prev) => ({ ...prev, is_saved: willSave }));
    } catch (err) {
      console.error('Failed to toggle save story:', err);
    }
  };

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleAnalyzeStory = async () => {
    if (!story || analyzing) return;
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      const updated = await ApiService.analyzeStory(story.id);
      setStory(updated);
    } catch (err) {
      setAnalysisError('AI analysis temporarily unavailable. Continuing with canonical wire data.');
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return (
      <div className="p-20 text-center text-sm text-news-text-secondary">
        Loading story briefing...
      </div>
    );
  }

  if (!story) {
    return (
      <div className="p-16 bg-news-surface border border-news-border rounded-xl text-center space-y-4 max-w-md mx-auto shadow-card">
        <h2 className="text-xl font-bold text-news-text-primary">Story Not Found</h2>
        <p className="text-sm text-news-text-secondary">This story could not be found or may have been removed.</p>
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 text-white dark:bg-neutral-800 rounded-lg text-xs font-medium"
        >
          <ArrowLeft className="w-4 h-4" /> Go Back
        </button>
      </div>
    );
  }

  const primarySource = story.articles && story.articles.length > 0 ? story.articles[0].source_name : null;
  const isAnalyzed = Boolean(story.analyzed || story.analyzed_at || story.ai_summary);

  return (
    <article className="space-y-8 max-w-3xl mx-auto">
      {/* Top Back & Action Bar */}
      <div className="flex items-center justify-between gap-4 pb-4 border-b border-news-border">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 dark:hover:text-neutral-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Feed</span>
        </button>

        <div className="flex items-center gap-2">
          {!isAnalyzed && (
            <button
              type="button"
              onClick={handleAnalyzeStory}
              disabled={analyzing}
              title="Generate structured AI editorial understanding"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors shadow-sm disabled:opacity-60"
            >
              <Sparkles className={`w-3.5 h-3.5 ${analyzing ? 'animate-spin' : ''}`} />
              <span>{analyzing ? 'Synthesizing...' : 'Analyze with AI'}</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleShare}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-white dark:bg-[#18191E] hover:bg-slate-50 dark:hover:bg-neutral-800 border border-news-border rounded-lg text-news-text-secondary transition-colors"
          >
            {copied ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <Share2 className="w-4 h-4" />}
            <span>{copied ? 'Copied' : 'Share'}</span>
          </button>
          <button
            type="button"
            onClick={handleSaveToggle}
            className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
              story.is_saved
                ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-900/60'
                : 'bg-white dark:bg-[#18191E] text-news-text-secondary border-news-border hover:bg-slate-50 dark:hover:bg-neutral-800'
            }`}
          >
            {story.is_saved ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}
            <span>{story.is_saved ? 'Saved' : 'Save Story'}</span>
          </button>
        </div>
      </div>

      {analysisError && (
        <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 rounded-xl text-xs text-amber-800 dark:text-amber-300 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{analysisError}</span>
        </div>
      )}

      {/* Story Headline & Editorial Label */}
      <header className="space-y-4">
        <div className="flex items-center gap-2.5 flex-wrap">
          <CategoryBadge category={story.category} topic={story.primary_topic} />

          {/* Story Lifecycle Status & Breaking Level */}
          {story.story_status && (
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold tracking-wide ${
              story.breaking_level === 'BREAKING'
                ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300 border border-rose-200 dark:border-rose-900/60'
                : story.story_status === 'ESCALATING'
                ? 'bg-amber-50 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300 border border-amber-200 dark:border-amber-900/60'
                : story.story_status === 'DEVELOPING'
                ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 border border-blue-200 dark:border-blue-900/60'
                : 'bg-slate-100 text-slate-700 dark:bg-neutral-800 dark:text-neutral-300 border border-news-border'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${
                story.breaking_level === 'BREAKING' ? 'bg-rose-500 animate-pulse' :
                story.story_status === 'ESCALATING' ? 'bg-amber-500' :
                story.story_status === 'DEVELOPING' ? 'bg-blue-500' : 'bg-slate-400'
              }`} />
              <span>
                {story.story_status}
                {story.latest_updated_at ? ` · Updated ${formatTimeAgo(story.latest_updated_at)}` : ''}
              </span>
            </span>
          )}

          {isAnalyzed && (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border border-blue-200/60 dark:border-blue-900/40">
              <Sparkles className="w-3 h-3 text-blue-600 dark:text-blue-400" />
              <span>AI-generated summary</span>
            </span>
          )}
          <ImportanceBadge score={story.importance_score} tier={story.importance_tier} isBreaking={story.is_breaking} />
          <SourceBadge sourceName={primarySource} sourceCount={story.source_count} timestamp={story.created_at} />
        </div>

        <h1 className="text-2xl sm:text-3xl lg:text-4xl font-sans font-bold text-news-text-primary tracking-tight leading-snug">
          {story.ai_title || story.title}
        </h1>
      </header>

      {/* Latest Development Callout (Phase 7) */}
      {story.latest_development && story.update_count > 0 && (
        <div className="bg-amber-50/60 dark:bg-amber-950/20 border-l-4 border-amber-500 p-4 sm:p-5 rounded-r-xl space-y-1.5 shadow-card">
          <div className="flex items-center justify-between gap-2 text-amber-900 dark:text-amber-300 font-semibold text-[11px] uppercase tracking-wider">
            <div className="flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
              <span>Latest Development</span>
            </div>
            {story.latest_updated_at && (
              <span className="text-[10px] text-amber-800/80 dark:text-amber-400/80 font-normal">
                Updated {formatTimeAgo(story.latest_updated_at)}
              </span>
            )}
          </div>
          <p className="text-sm sm:text-base font-sans text-news-text-primary leading-relaxed">
            {story.latest_development}
          </p>
        </div>
      )}

      {/* What Happened Section */}
      <div className="bg-news-surface border border-news-border p-6 sm:p-7 rounded-xl shadow-card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-neutral-500">
            {isAnalyzed ? 'What Happened' : 'Executive Summary'}
          </h2>
          {isAnalyzed && (
            <span className="text-[11px] font-medium text-slate-500 dark:text-neutral-400 bg-slate-100 dark:bg-neutral-800/80 px-2 py-0.5 rounded">
              Based on {story.source_count || 1} {story.source_count === 1 ? 'source' : 'sources'}
            </span>
          )}
        </div>
        <p className="text-base sm:text-lg font-sans text-news-text-primary leading-relaxed">
          {story.ai_summary || story.summary}
        </p>
      </div>

      {/* Why It Matters Callout */}
      {story.why_it_matters && (
        <div className="bg-blue-50/70 dark:bg-blue-950/30 border-l-4 border-blue-600 p-5 rounded-r-xl space-y-2">
          <div className="flex items-center gap-2 text-blue-800 dark:text-blue-300 font-semibold text-xs uppercase tracking-wider">
            <Sparkles className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <span>Why It Matters</span>
          </div>
          <p className="text-sm font-sans text-blue-950 dark:text-blue-100 leading-relaxed">
            {story.why_it_matters}
          </p>
        </div>
      )}

      {/* Personal Relevance Context */}
      {story.relevance_reason && (
        <div className="bg-slate-50/70 dark:bg-[#18191E] border border-news-border px-4 py-3 rounded-xl flex items-start gap-3 text-xs shadow-card">
          <Sparkles className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-semibold text-news-text-primary block">Why You're Seeing This</span>
            <span className="text-news-text-secondary leading-relaxed">{story.relevance_reason}</span>
          </div>
        </div>
      )}


      {/* Global Importance Assessment */}
      {(story.importance_explanation || story.importance_breakdown) && (
        <div className="bg-slate-50/80 dark:bg-[#18191E] border border-news-border p-5 rounded-xl space-y-3 shadow-card">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <ImportanceBadge score={story.importance_score} tier={story.importance_tier} isBreaking={story.is_breaking} />
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-neutral-400">
                Global Importance Assessment
              </span>
            </div>
            {story.importance_version && (
              <span className="text-[10px] font-mono text-slate-400 dark:text-neutral-500">
                Engine {story.importance_version}
              </span>
            )}
          </div>
          {story.importance_explanation && (
            <p className="text-sm font-sans text-news-text-primary leading-relaxed">
              {story.importance_explanation}
            </p>
          )}
          {story.importance_breakdown && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-news-border/60 text-xs">
              <div className="bg-white dark:bg-[#1F2026] p-2.5 rounded-lg border border-news-border/60">
                <span className="text-slate-400 dark:text-neutral-500 block text-[10px] uppercase font-medium">Severity</span>
                <span className="font-semibold text-news-text-primary text-sm">{Math.round(story.importance_breakdown.severity * 100)}%</span>
              </div>
              <div className="bg-white dark:bg-[#1F2026] p-2.5 rounded-lg border border-news-border/60">
                <span className="text-slate-400 dark:text-neutral-500 block text-[10px] uppercase font-medium">Reach</span>
                <span className="font-semibold text-news-text-primary text-sm">{Math.round(story.importance_breakdown.reach * 100)}%</span>
              </div>
              <div className="bg-white dark:bg-[#1F2026] p-2.5 rounded-lg border border-news-border/60">
                <span className="text-slate-400 dark:text-neutral-500 block text-[10px] uppercase font-medium">Impact</span>
                <span className="font-semibold text-news-text-primary text-sm">{Math.round(story.importance_breakdown.impact * 100)}%</span>
              </div>
              <div className="bg-white dark:bg-[#1F2026] p-2.5 rounded-lg border border-news-border/60">
                <span className="text-slate-400 dark:text-neutral-500 block text-[10px] uppercase font-medium">Urgency</span>
                <span className="font-semibold text-news-text-primary text-sm">{Math.round(story.importance_breakdown.urgency * 100)}%</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Topics Section */}
      {((story.topics && story.topics.length > 0) || (story.tags && story.tags.length > 0)) && (
        <section className="space-y-2.5">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-neutral-500 flex items-center gap-1.5">
            <Tag className="w-3.5 h-3.5" />
            <span>Topics</span>
          </h2>
          <div className="flex items-center gap-2 flex-wrap">
            {(story.topics && story.topics.length > 0 ? story.topics : story.tags).map((topicItem, idx) => (
              <span
                key={idx}
                className="px-3 py-1 rounded-lg bg-slate-100 dark:bg-[#1C1D22] text-xs font-medium text-news-text-primary border border-news-border/60"
              >
                {topicItem}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* People & Organizations Section */}
      {story.entities && story.entities.length > 0 && (
        <section className="space-y-2.5">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-neutral-500 flex items-center gap-1.5">
            <Building2 className="w-3.5 h-3.5" />
            <span>People / Organizations</span>
          </h2>
          <div className="flex items-center gap-2 flex-wrap">
            {story.entities.map((ent, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-news-surface border border-news-border text-xs font-medium text-news-text-primary shadow-sm"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                <span>{ent.name}</span>
                {ent.category && (
                  <span className="text-[10px] text-news-text-secondary uppercase">
                    ({ent.category})
                  </span>
                )}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Conflicting Perspectives Section (Only when grounded conflicting claims exist) */}
      {story.perspectives && story.perspectives.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-rose-600 dark:text-rose-400 flex items-center gap-1.5">
              <Scale className="w-3.5 h-3.5" />
              <span>Conflicting Perspectives</span>
            </h2>
            <span className="text-[11px] font-medium text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/60 px-2 py-0.5 rounded border border-rose-200 dark:border-rose-900/60">
              Disputed Reporting
            </span>
          </div>
          <div className="bg-news-surface border border-rose-200 dark:border-rose-950/60 rounded-xl p-5 shadow-card space-y-4">
            {story.perspectives.map((persp, pIdx) => (
              <div key={pIdx} className="space-y-3">
                <div className="text-xs text-news-text-secondary">
                  <span className="font-semibold text-news-text-primary">{persp.topic_or_issue}</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {persp.sources.map((src, sIdx) => (
                    <div key={sIdx} className="p-3 bg-slate-50/80 dark:bg-[#1A1B22] rounded-lg border border-news-border space-y-1.5">
                      <span className="font-bold text-xs text-news-text-primary block">{src.source_name}</span>
                      <p className="text-xs text-news-text-secondary italic">"{src.stance}"</p>
                      {src.claim_text && (
                        <p className="text-[11px] text-news-text-secondary pt-1 border-t border-news-border/60 line-clamp-2">
                          {src.claim_text}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Story Timeline (Phase 7 Grounded Event Lifecycle) */}
      {story.timeline && story.timeline.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-neutral-500 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              <span>Story Timeline</span>
            </h2>
            <span className="text-[11px] text-news-text-secondary">
              {story.timeline.length} {story.timeline.length === 1 ? 'event' : 'events'} recorded
            </span>
          </div>

          <div className="bg-news-surface border border-news-border rounded-xl p-5 sm:p-6 shadow-card">
            <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200 dark:before:bg-neutral-800">
              {story.timeline.map((event, idx) => {
                const isLatest = idx === story.timeline.length - 1;
                const isFirst = idx === 0;
                const eventLabel =
                  isLatest && story.timeline.length > 1 ? 'Latest development' :
                  isFirst ? 'Initial report' :
                  event.event_type === 'ESCALATION' ? 'Escalation' :
                  event.event_type === 'RESOLUTION' ? 'Resolution' :
                  event.event_type === 'CORRECTION' ? 'Correction' :
                  'New reporting';

                return (
                  <div key={idx} className="relative group">
                    {/* Bullet marker */}
                    <span className={`absolute -left-[27px] top-1 w-3 h-3 rounded-full border-2 border-white dark:border-[#15161A] transition-colors ${
                      isLatest ? 'bg-blue-600 ring-2 ring-blue-100 dark:ring-blue-950' :
                      event.event_type === 'ESCALATION' ? 'bg-amber-500' :
                      'bg-slate-400 dark:bg-neutral-600'
                    }`} />

                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap text-xs">
                        <span className="font-mono text-[11px] text-slate-500 dark:text-neutral-400 font-medium">
                          ● {formatTimelineDate(event.time)}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold tracking-wide ${
                          isLatest ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300' :
                          event.event_type === 'ESCALATION' ? 'bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300' :
                          'bg-slate-100 text-slate-600 dark:bg-neutral-800 dark:text-neutral-400'
                        }`}>
                          {eventLabel}
                        </span>
                      </div>

                      <h4 className="text-sm font-semibold text-news-text-primary leading-snug">
                        {event.title}
                      </h4>

                      {event.description && event.description !== event.title && (
                        <p className="text-xs text-news-text-secondary leading-relaxed pt-0.5">
                          {event.description}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* Clustered Sources Section */}
      <section className="space-y-3">
        <h2 className="text-sm font-bold text-news-text-primary flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-slate-400" />
          <span>Sources ({story.articles?.length || 0})</span>
        </h2>
        <div className="space-y-3">
          {(story.articles || []).map((art) => (
            <div
              key={art.id}
              className="bg-news-surface border border-news-border hover:border-slate-300 dark:hover:border-neutral-700 p-4 sm:p-5 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-colors shadow-card"
            >
              <div className="space-y-1.5 flex-1 min-w-0">
                <div className="flex items-center gap-2 text-xs text-news-text-secondary">
                  <span className="font-semibold text-news-text-primary">{art.source_name}</span>
                  <span>·</span>
                  <span>{art.source_domain}</span>
                  {art.author && <span>· By {art.author}</span>}
                </div>
                <h4 className="font-semibold text-news-text-primary text-sm line-clamp-2">
                  {art.title}
                </h4>
              </div>
              <a
                href={art.url}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 inline-flex items-center gap-1.5 px-3.5 py-2 bg-slate-100 dark:bg-neutral-800 hover:bg-blue-600 hover:text-white dark:hover:bg-blue-600 text-xs font-semibold text-news-text-primary rounded-lg transition-colors self-start sm:self-auto"
              >
                <span>Read on Publisher</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* Related Stories */}
      {relatedStories.length > 0 && (
        <section className="space-y-4 pt-6 border-t border-news-border">
          <h2 className="text-sm font-bold text-news-text-primary">
            Related News
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {relatedStories.map((rel) => (
              <NewsCard
                key={rel.id}
                story={rel}
                onSaveToggle={handleSaveToggle}
                variant="compact"
              />
            ))}
          </div>
        </section>
      )}
    </article>
  );
}
