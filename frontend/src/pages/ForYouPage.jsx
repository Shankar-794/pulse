import React, { useState, useEffect } from 'react';
import { Flame, Sparkles, Cpu, Globe, Layers, RefreshCw, CheckCircle2, Newspaper } from 'lucide-react';
import { ApiService } from '../services/api';
import { StorageService } from '../services/storage';
import NewsCard from '../components/feed/NewsCard';
import FeedSection from '../components/feed/FeedSection';
import ErrorState from '../components/common/ErrorState';

export default function ForYouPage() {
  const [stories, setStories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isEmpty, setIsEmpty] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [syncMessage, setSyncMessage] = useState(null);

  const loadFeed = async () => {
    setLoading(true);
    setHasError(false);
    try {
      const data = await ApiService.getFeed();
      if (data.is_empty) {
        setIsEmpty(true);
        setStories([]);
      } else {
        setIsEmpty(false);
        setStories(data.items || []);
      }
    } catch {
      setHasError(true);
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    loadFeed();

    const handleSavedUpdated = ({ detail }) => {
      setStories((prev) =>
        prev.map((s) => (s.id === detail.storyId ? { ...s, is_saved: detail.isSaved } : s))
      );
    };

    const handleHiddenUpdated = ({ detail }) => {
      setStories((prev) => prev.filter((s) => s.id !== detail.storyId));
    };

    window.addEventListener('pulse_saved_updated', handleSavedUpdated);
    window.addEventListener('pulse_hidden_updated', handleHiddenUpdated);

    return () => {
      window.removeEventListener('pulse_saved_updated', handleSavedUpdated);
      window.removeEventListener('pulse_hidden_updated', handleHiddenUpdated);
    };
  }, []);

  const handleSaveToggle = async (storyId) => {
    if (localStorage.getItem('pulse_auth_token')) {
      const story = stories.find((s) => s.id === storyId);
      const willSave = !story?.is_saved;
      if (willSave) {
        await ApiService.saveStory(storyId);
      } else {
        await ApiService.unsaveStory(storyId);
      }
      setStories((prev) =>
        prev.map((s) => (s.id === storyId ? { ...s, is_saved: willSave } : s))
      );
    } else {
      const isSaved = StorageService.toggleSaveStory(storyId);
      ApiService.recordInteraction(storyId, isSaved ? 'save' : 'unsave');
      setStories((prev) =>
        prev.map((s) => (s.id === storyId ? { ...s, is_saved: isSaved } : s))
      );
    }
  };

  const handleHide = (storyId) => {
    StorageService.hideStory(storyId);
    ApiService.recordInteraction(storyId, 'hide');
  };

  const handleTriggerIngestion = async () => {
    setRefreshing(true);
    try {
      const summary = await ApiService.triggerIngestion();
      setSyncMessage({
        type: 'success',
        text: `Updated: ${summary.new_articles} new articles, ${summary.duplicates} duplicates from ${summary.sources_checked} sources in ${summary.duration_seconds}s.`
      });
      await loadFeed();
    } catch {
      setSyncMessage({
        type: 'error',
        text: 'Unable to update news feed. Please try again.'
      });
    } finally {
      setRefreshing(false);
      setTimeout(() => setSyncMessage(null), 5000);
    }
  };

  // Section divisions
  const breakingStories = stories.filter((s) => s.is_breaking);
  const importantStories = stories.filter(
    (s) => !s.is_breaking && (s.importance_score >= 85 || s.relevance_score >= 90)
  );
  const techCategories = new Set(['technology', 'ai', 'software engineering', 'cybersecurity', 'tech']);
  const worldCategories = new Set(['world', 'business', 'economy', 'geopolitics']);

  const techStories = stories.filter(
    (s) => !s.is_breaking && !importantStories.some((item) => item.id === s.id) && techCategories.has(s.category?.toLowerCase())
  );
  const worldStories = stories.filter(
    (s) => !s.is_breaking && !importantStories.some((item) => item.id === s.id) && worldCategories.has(s.category?.toLowerCase())
  );

  const moreStories = stories.filter(
    (s) =>
      !s.is_breaking &&
      !importantStories.some((item) => item.id === s.id) &&
      !techStories.some((item) => item.id === s.id) &&
      !worldStories.some((item) => item.id === s.id)
  );

  return (
    <div className="space-y-8">
      {/* Editorial Header Banner */}
      <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-5">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <h1 className="text-2xl sm:text-3xl font-bold font-sans text-news-text-primary tracking-tight">
              Today's Briefing
            </h1>
          </div>
          <p className="text-sm text-news-text-secondary leading-relaxed">
            Curated for <span className="font-medium text-news-text-primary">Technology & Systems Engineering</span> · Filtered across 8 verified sources
          </p>
        </div>
        <button
          type="button"
          onClick={handleTriggerIngestion}
          disabled={refreshing}
          className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-blue-600 dark:bg-neutral-800 dark:hover:bg-blue-600 text-white text-xs font-semibold rounded-lg transition-colors shadow-sm self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          <span>{refreshing ? 'Refreshing Feeds...' : 'Refresh Feed'}</span>
        </button>
      </div>

      {/* Sync Status Toast */}
      {syncMessage && (
        <div className={`p-4 rounded-xl border text-xs font-medium flex items-center gap-2.5 transition-all ${
          syncMessage.type === 'success'
            ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800/80 text-emerald-800 dark:text-emerald-300'
            : 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800/80 text-red-800 dark:text-red-300'
        }`}>
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{syncMessage.text}</span>
        </div>
      )}

      {loading ? (
        <div className="p-16 text-center text-sm text-news-text-secondary">
          Loading your news feed...
        </div>
      ) : hasError ? (
        <ErrorState onRetry={loadFeed} />
      ) : isEmpty ? (
        /* Clean Editorial Empty State */
        <div className="p-16 bg-news-surface border border-news-border rounded-xl text-center space-y-4 max-w-xl mx-auto shadow-card">
          <Newspaper className="w-12 h-12 text-blue-600 dark:text-blue-400 mx-auto opacity-80" />
          <h2 className="text-xl font-bold text-news-text-primary">No Articles Ingested Yet</h2>
          <p className="text-sm text-news-text-secondary leading-relaxed">
            Pulse is ready to collect articles from 8 trusted feeds (Hacker News, Ars Technica, MIT News, NASA, BBC, Krebs on Security, BleepingComputer, The Verge).
          </p>
          <div className="pt-2">
            <button
              type="button"
              onClick={handleTriggerIngestion}
              disabled={refreshing}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg transition-colors shadow-sm"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              <span>{refreshing ? 'Fetching Articles...' : 'Fetch Latest Articles'}</span>
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* BREAKING SECTION */}
          {breakingStories.length > 0 && (
            <FeedSection
              title="Breaking News"
              subtitle="Critical updates requiring immediate attention"
              icon={Flame}
              count={breakingStories.length}
            >
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {breakingStories.map((story) => (
                  <NewsCard
                    key={story.id}
                    story={story}
                    onSaveToggle={handleSaveToggle}
                    onHide={handleHide}
                    variant="featured"
                  />
                ))}
              </div>
            </FeedSection>
          )}

          {/* IMPORTANT FOR YOU SECTION */}
          {importantStories.length > 0 && (
            <FeedSection
              title="Important For You"
              subtitle="Matched with your technology and engineering interests"
              icon={Sparkles}
              count={importantStories.length}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {importantStories.map((story) => (
                  <NewsCard
                    key={story.id}
                    story={story}
                    onSaveToggle={handleSaveToggle}
                    onHide={handleHide}
                    variant="standard"
                  />
                ))}
              </div>
            </FeedSection>
          )}

          {/* TECHNOLOGY SECTION */}
          {techStories.length > 0 && (
            <FeedSection
              title="Technology & Systems"
              subtitle="Software, hardware, compilers, and infrastructure"
              icon={Cpu}
              count={techStories.length}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {techStories.map((story) => (
                  <NewsCard
                    key={story.id}
                    story={story}
                    onSaveToggle={handleSaveToggle}
                    onHide={handleHide}
                    variant="standard"
                  />
                ))}
              </div>
            </FeedSection>
          )}

          {/* WORLD SECTION */}
          {worldStories.length > 0 && (
            <FeedSection
              title="World & Geopolitics"
              subtitle="International policies, treaties, and global industry"
              icon={Globe}
              count={worldStories.length}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {worldStories.map((story) => (
                  <NewsCard
                    key={story.id}
                    story={story}
                    onSaveToggle={handleSaveToggle}
                    onHide={handleHide}
                    variant="standard"
                  />
                ))}
              </div>
            </FeedSection>
          )}

          {/* MORE FROM YOUR TOPICS */}
          {moreStories.length > 0 && (
            <FeedSection
              title="More Stories"
              subtitle="Science discoveries, aerospace, and research"
              icon={Layers}
              count={moreStories.length}
            >
              <div className="space-y-3">
                {moreStories.map((story) => (
                  <NewsCard
                    key={story.id}
                    story={story}
                    onSaveToggle={handleSaveToggle}
                    onHide={handleHide}
                    variant="compact"
                  />
                ))}
              </div>
            </FeedSection>
          )}
        </>
      )}
    </div>
  );
}
