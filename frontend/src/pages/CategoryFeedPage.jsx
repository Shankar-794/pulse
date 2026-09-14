import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { ApiService } from '../services/api';
import { StorageService } from '../services/storage';
import { useAuth } from '../context/AuthContext';
import { addPendingAction } from '../services/pendingActions';
import NewsCard from '../components/feed/NewsCard';
import ErrorState from '../components/common/ErrorState';
import { Filter, Layers, RefreshCw } from 'lucide-react';

const CATEGORY_META = {
  world: {
    title: 'World & Geopolitics',
    description: 'International policy, export control treaties, cross-border regulations, and critical global events.'
  },
  technology: {
    title: 'Technology & Systems',
    description: 'Operating systems, compilers, distributed systems, semiconductor lithography, and memory safety.'
  },
  ai: {
    title: 'Artificial Intelligence',
    description: 'Foundational models, reasoning agents, test-time compute, training benchmarks, and alignment engineering.'
  },
  science: {
    title: 'Applied Sciences',
    description: 'Quantum computing architectures, solid-state materials, fusion energy milestones, and biotechnology.'
  },
  business: {
    title: 'Business & Enterprise',
    description: 'Corporate strategy, earnings, enterprise technology adoption, venture capital formation, and industry developments.'
  },
  economy: {
    title: 'Economy & Markets',
    description: 'Macroeconomic indicators, monetary policy, global trade dynamics, energy commodities, and labor markets.'
  },
  cybersecurity: {
    title: 'Cybersecurity',
    description: 'Critical CVE disclosures, kernel attack vectors, post-quantum cryptography, and security research.'
  },
  space: {
    title: 'Space Exploration',
    description: 'Deep-space probes, orbital mechanics, heavy lift vehicles, and observational astrophysics.'
  }
};

export default function CategoryFeedPage({ category: propCategory }) {
  const { isAuthenticated, openLoginModal } = useAuth();
  const { category: paramCategory } = useParams();
  const location = useLocation();
  const pathSegment = location.pathname.replace(/^\/+|\/+$/g, '').split('/').pop();
  const rawKey = propCategory || paramCategory || pathSegment || 'technology';
  const categoryKey = rawKey.toLowerCase().trim();

  const meta = CATEGORY_META[categoryKey] || {
    title: categoryKey ? categoryKey.charAt(0).toUpperCase() + categoryKey.slice(1) : 'News Stream',
    description: 'Curated stories and reporting in this domain.'
  };

  const [stories, setStories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [minImportance, setMinImportance] = useState(0);

  const loadCategoryFeed = useCallback(async () => {
    if (!categoryKey) return;
    setLoading(true);
    setError(false);
    try {
      const data = await ApiService.getStories({ category: categoryKey });
      setStories(data?.items || []);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [categoryKey]);

  useEffect(() => {
    loadCategoryFeed();

    const handlePipelineCompleted = () => {
      loadCategoryFeed();
    };

    const handleSavedUpdated = ({ detail }) => {
      setStories((prev) =>
        prev.map((s) => (s.id === detail.storyId ? { ...s, is_saved: detail.isSaved } : s))
      );
    };

    const handleHiddenUpdated = ({ detail }) => {
      setStories((prev) => prev.filter((s) => s.id !== detail.storyId));
    };

    window.addEventListener('pulse_pipeline_completed', handlePipelineCompleted);
    window.addEventListener('pulse_saved_updated', handleSavedUpdated);
    window.addEventListener('pulse_hidden_updated', handleHiddenUpdated);

    return () => {
      window.removeEventListener('pulse_pipeline_completed', handlePipelineCompleted);
      window.removeEventListener('pulse_saved_updated', handleSavedUpdated);
      window.removeEventListener('pulse_hidden_updated', handleHiddenUpdated);
    };
  }, [loadCategoryFeed]);

  const handleSaveToggle = async (storyId) => {
    if (!isAuthenticated) {
      const story = stories.find((s) => s.id === storyId);
      const actionType = story?.is_saved ? 'UNSAVE_STORY' : 'SAVE_STORY';
      addPendingAction(actionType, { storyId });
      openLoginModal({
        title: 'Sign in to personalize Pulse',
        message: 'Your action will be saved and completed after you sign in.'
      });
      return;
    }

    const story = stories.find((s) => s.id === storyId);
    const willSave = !story?.is_saved;
    try {
      if (willSave) {
        await ApiService.saveStory(storyId);
      } else {
        await ApiService.unsaveStory(storyId);
      }
      setStories((prev) =>
        prev.map((s) => (s.id === storyId ? { ...s, is_saved: willSave } : s))
      );
    } catch (err) {
      console.error('Failed to toggle save story:', err);
    }
  };

  const handleHide = (storyId) => {
    StorageService.hideStory(storyId);
    ApiService.recordInteraction(storyId, 'hide');
    setStories((prev) => prev.filter((s) => s.id !== storyId));
  };

  const filteredStories = stories.filter((s) => s.importance_score >= minImportance);

  return (
    <div className="space-y-6">
      {/* Editorial Header */}
      <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">
                Section
              </span>
              <span className="text-xs text-news-text-secondary">
                · {filteredStories.length} {filteredStories.length === 1 ? 'story' : 'stories'}
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold font-sans text-news-text-primary mb-2">
              {meta.title}
            </h1>
            <p className="text-sm text-news-text-secondary max-w-3xl leading-relaxed">
              {meta.description}
            </p>
          </div>
          <button
            type="button"
            onClick={() => loadCategoryFeed()}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-100 hover:bg-slate-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-news-text-primary text-xs font-semibold rounded-lg transition-colors self-start sm:self-auto shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>

        {/* Filter Pills */}
        <div className="mt-5 pt-4 border-t border-news-border flex items-center justify-between gap-4 flex-wrap text-xs">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-news-text-secondary font-medium">Importance:</span>
            <div className="flex items-center gap-1.5">
              {[0, 80, 88].map((thresh) => (
                <button
                  key={thresh}
                  type="button"
                  onClick={() => setMinImportance(thresh)}
                  className={`px-3 py-1 rounded-full text-xs transition-colors ${
                    minImportance === thresh
                      ? 'bg-blue-600 text-white font-medium'
                      : 'bg-slate-100 dark:bg-neutral-800 text-slate-600 dark:text-neutral-300 hover:bg-slate-200 dark:hover:bg-neutral-700'
                  }`}
                >
                  {thresh === 0 ? 'All Stories' : `>= ${thresh} Score`}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Stories Grid */}
      {loading ? (
        <div className="p-16 text-center text-sm text-news-text-secondary">
          Loading {meta.title} stories...
        </div>
      ) : error ? (
        <ErrorState onRetry={loadCategoryFeed} />
      ) : filteredStories.length === 0 ? (
        <div className="p-16 bg-news-surface border border-news-border rounded-xl text-center space-y-2 shadow-card">
          <Layers className="w-8 h-8 text-slate-400 mx-auto" />
          <p className="text-base font-semibold text-news-text-primary">No stories available yet.</p>
          <p className="text-xs text-news-text-secondary">Try switching the filter to all stories or trigger an update.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filteredStories.map((story) => (
            <NewsCard
              key={story.id}
              story={story}
              onSaveToggle={handleSaveToggle}
              onHide={handleHide}
              variant="standard"
            />
          ))}
        </div>
      )}
    </div>
  );
}
