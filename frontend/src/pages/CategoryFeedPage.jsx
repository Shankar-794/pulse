import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { ApiService } from '../services/api';
import { StorageService } from '../services/storage';
import NewsCard from '../components/feed/NewsCard';
import ErrorState from '../components/common/ErrorState';
import { Filter, Layers } from 'lucide-react';

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

export default function CategoryFeedPage() {
  const location = useLocation();
  const categoryKey = location.pathname.replace('/', '').toLowerCase();
  const meta = CATEGORY_META[categoryKey] || {
    title: categoryKey.charAt(0).toUpperCase() + categoryKey.slice(1),
    description: 'Curated stories and reporting in this domain.'
  };

  const [stories, setStories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [minImportance, setMinImportance] = useState(0);

  const loadCategoryFeed = async () => {
    setLoading(true);
    setError(false);
    try {
      const data = await ApiService.getStories({ category: categoryKey });
      setStories(data.items || []);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCategoryFeed();
  }, [categoryKey]);

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
    setStories((prev) => prev.filter((s) => s.id !== storyId));
  };

  const filteredStories = stories.filter((s) => s.importance_score >= minImportance);

  return (
    <div className="space-y-6">
      {/* Editorial Header */}
      <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card">
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
