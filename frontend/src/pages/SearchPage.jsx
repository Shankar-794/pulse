import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, X, Layers } from 'lucide-react';
import { ApiService } from '../services/api';
import { StorageService } from '../services/storage';
import { useAuth } from '../context/AuthContext';
import { addPendingAction } from '../services/pendingActions';
import NewsCard from '../components/feed/NewsCard';

const CATEGORIES = ['All', 'AI', 'Technology', 'Cybersecurity', 'Space', 'Science', 'Business', 'Economy', 'World'];
const SOURCES = ['All', 'Hacker News', 'Ars Technica', 'Krebs on Security', 'BleepingComputer', 'MIT News Research', 'NASA Breaking News', 'BBC Technology', 'The Verge', 'BBC Business', 'NPR Economy'];
const DATE_RANGES = [
  { label: 'Any Time', value: 'all' },
  { label: 'Past 24 Hours', value: '24h' },
  { label: 'Past 7 Days', value: '7d' },
  { label: 'Past 30 Days', value: '30d' },
];

export default function SearchPage() {
  const { isAuthenticated, openLoginModal } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';

  const [query, setQuery] = useState(initialQuery);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [selectedSource, setSelectedSource] = useState('All');
  const [selectedDateRange, setSelectedDateRange] = useState('all');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (initialQuery) {
      setQuery(initialQuery);
    }
  }, [initialQuery]);

  useEffect(() => {
    let mounted = true;
    setLoading(true);

    const filterCat = selectedCategory === 'All' ? undefined : selectedCategory.toLowerCase();

    ApiService.getStories({
      search: query.trim() || undefined,
      category: filterCat,
    }).then((res) => {
      if (!mounted) return;
      let items = res.items || [];

      // Filter by source
      if (selectedSource !== 'All') {
        items = items.filter((s) =>
          s.articles?.some((a) => a.source_name.toLowerCase() === selectedSource.toLowerCase())
        );
      }

      // Filter by date range
      if (selectedDateRange !== 'all') {
        const now = Date.now();
        const maxAge =
          selectedDateRange === '24h'
            ? 24 * 60 * 60 * 1000
            : selectedDateRange === '7d'
            ? 7 * 24 * 60 * 60 * 1000
            : 30 * 24 * 60 * 60 * 1000;

        items = items.filter((s) => {
          const storyTime = new Date(s.created_at).getTime();
          return now - storyTime <= maxAge;
        });
      }

      setResults(items);
      setLoading(false);
    });

    return () => {
      mounted = false;
    };
  }, [query, selectedCategory, selectedSource, selectedDateRange]);

  const handleSaveToggle = async (storyId) => {
    if (!isAuthenticated) {
      const story = results.find((s) => s.id === storyId);
      const actionType = story?.is_saved ? 'UNSAVE_STORY' : 'SAVE_STORY';
      addPendingAction(actionType, { storyId });
      openLoginModal({
        title: 'Sign in to personalize Pulse',
        message: 'Your action will be saved and completed after you sign in.'
      });
      return;
    }

    const story = results.find((s) => s.id === storyId);
    const willSave = !story?.is_saved;
    try {
      if (willSave) {
        await ApiService.saveStory(storyId);
      } else {
        await ApiService.unsaveStory(storyId);
      }
      setResults((prev) =>
        prev.map((s) => (s.id === storyId ? { ...s, is_saved: willSave } : s))
      );
    } catch (err) {
      console.error('Failed to toggle save story in search:', err);
    }
  };

  const handleResetFilters = () => {
    setQuery('');
    setSelectedCategory('All');
    setSelectedSource('All');
    setSelectedDateRange('all');
    setSearchParams({});
  };

  return (
    <div className="space-y-6">
      {/* Search Header Container */}
      <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card space-y-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold font-sans text-news-text-primary mb-1">
            Search News
          </h1>
          <p className="text-sm text-news-text-secondary">
            Find articles across all 8 verified sources, categories, and technical topics.
          </p>
        </div>

        {/* Input Bar */}
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSearchParams(e.target.value ? { q: e.target.value } : {});
            }}
            placeholder="Search keywords, headlines, or topics..."
            className="w-full bg-slate-50 dark:bg-[#121316] border border-news-border focus:border-blue-500 focus:bg-white dark:focus:bg-[#16171B] text-news-text-primary text-sm font-sans placeholder:text-slate-400 rounded-lg pl-11 pr-11 py-2.5 outline-none transition-all shadow-sm"
          />
          {query && (
            <button
              type="button"
              onClick={() => {
                setQuery('');
                setSearchParams({});
              }}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-neutral-200"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Multi-facet Filters */}
        <div className="pt-3 border-t border-news-border grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div>
            <label className="block text-news-text-secondary font-medium mb-1">Section</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full bg-slate-50 dark:bg-[#121316] border border-news-border text-news-text-primary rounded-lg px-3 py-2 outline-none focus:border-blue-500"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-news-text-secondary font-medium mb-1">Source Wire</label>
            <select
              value={selectedSource}
              onChange={(e) => setSelectedSource(e.target.value)}
              className="w-full bg-slate-50 dark:bg-[#121316] border border-news-border text-news-text-primary rounded-lg px-3 py-2 outline-none focus:border-blue-500"
            >
              {SOURCES.map((src) => (
                <option key={src} value={src}>{src}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-news-text-secondary font-medium mb-1">Time Horizon</label>
            <select
              value={selectedDateRange}
              onChange={(e) => setSelectedDateRange(e.target.value)}
              className="w-full bg-slate-50 dark:bg-[#121316] border border-news-border text-news-text-primary rounded-lg px-3 py-2 outline-none focus:border-blue-500"
            >
              {DATE_RANGES.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Results Info Bar */}
        <div className="flex items-center justify-between text-xs text-news-text-secondary pt-1">
          <span>
            Showing <strong className="text-news-text-primary font-semibold">{results.length}</strong> matching articles
          </span>
          {(query || selectedCategory !== 'All' || selectedSource !== 'All' || selectedDateRange !== 'all') && (
            <button
              type="button"
              onClick={handleResetFilters}
              className="text-blue-600 dark:text-blue-400 hover:underline"
            >
              Reset filters
            </button>
          )}
        </div>
      </div>

      {/* Results Grid */}
      {loading ? (
        <div className="p-16 text-center text-sm text-news-text-secondary">
          Searching news library...
        </div>
      ) : results.length === 0 ? (
        <div className="p-16 bg-news-surface border border-news-border rounded-xl text-center space-y-2 shadow-card">
          <Search className="w-8 h-8 text-slate-400 mx-auto" />
          <p className="text-base font-semibold text-news-text-primary">No matching stories found.</p>
          <p className="text-xs text-news-text-secondary">Try adjusting your keywords or clearing the category filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {results.map((story) => (
            <NewsCard
              key={story.id}
              story={story}
              onSaveToggle={handleSaveToggle}
              variant="standard"
            />
          ))}
        </div>
      )}
    </div>
  );
}
