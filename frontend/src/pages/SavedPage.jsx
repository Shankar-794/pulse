import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Bookmark, Trash2, Compass } from 'lucide-react';
import { ApiService } from '../services/api';
import { StorageService } from '../services/storage';
import { useAuth } from '../context/AuthContext';
import NewsCard from '../components/feed/NewsCard';

export default function SavedPage() {
  const [savedStories, setSavedStories] = useState([]);
  const [loading, setLoading] = useState(true);
  const { user, isAuthenticated, refreshSavedCount } = useAuth();

  const loadSavedStories = async () => {
    setLoading(true);
    try {
      if (localStorage.getItem('pulse_auth_token')) {
        const res = await ApiService.getSavedStories();
        setSavedStories(res.items || []);
      } else {
        const savedIds = new Set(StorageService.getSavedStoryIds());
        const allStories = await ApiService.getStories();
        const filtered = (allStories.items || []).filter((s) => savedIds.has(s.id));
        setSavedStories(filtered);
      }
    } catch {
      setSavedStories([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSavedStories();

    const handleSavedUpdated = () => {
      loadSavedStories();
    };

    window.addEventListener('pulse_saved_updated', handleSavedUpdated);
    return () => {
      window.removeEventListener('pulse_saved_updated', handleSavedUpdated);
    };
  }, [isAuthenticated]);

  const handleSaveToggle = async (storyId) => {
    if (localStorage.getItem('pulse_auth_token')) {
      await ApiService.unsaveStory(storyId);
    } else {
      StorageService.toggleSaveStory(storyId);
      ApiService.recordInteraction(storyId, 'unsave');
    }
    setSavedStories((prev) => prev.filter((s) => s.id !== storyId));
    await refreshSavedCount();
  };

  const handleClearAll = async () => {
    if (window.confirm('Remove all saved stories from your library?')) {
      for (const s of savedStories) {
        if (localStorage.getItem('pulse_auth_token')) {
          await ApiService.unsaveStory(s.id);
        } else {
          StorageService.toggleSaveStory(s.id);
        }
      }
      setSavedStories([]);
      await refreshSavedCount();
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Bookmark className="w-5 h-5 text-blue-600 dark:text-blue-400 fill-blue-600 dark:fill-blue-400" />
            <h1 className="text-2xl sm:text-3xl font-bold font-sans text-news-text-primary">
              Saved Stories
            </h1>
          </div>
          <p className="text-sm text-news-text-secondary">
            {isAuthenticated && user
              ? `Personal reading list for ${user.full_name || user.email}. Synced to your profile.`
              : 'Your personal reading list. Saved stories are stored securely.'}
          </p>
        </div>

        {savedStories.length > 0 && (
          <button
            type="button"
            onClick={handleClearAll}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-neutral-800 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/40 dark:hover:text-red-400 text-xs font-medium text-slate-600 dark:text-neutral-300 rounded-lg transition-colors self-start sm:self-auto"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Library</span>
          </button>
        )}
      </div>

      {/* Content */}
      {loading ? (
        <div className="p-16 text-center text-sm text-news-text-secondary">
          Loading your reading list...
        </div>
      ) : savedStories.length === 0 ? (
        <div className="p-16 bg-news-surface border border-news-border rounded-xl text-center space-y-4 max-w-md mx-auto shadow-card">
          <Bookmark className="w-10 h-10 text-slate-300 dark:text-neutral-600 mx-auto" />
          <div>
            <h3 className="text-lg font-bold text-news-text-primary">
              You haven't saved any stories yet.
            </h3>
            <p className="text-sm text-news-text-secondary leading-relaxed mt-1">
              Click the bookmark icon on any story in your feed to save it for later reading.
            </p>
          </div>
          <div className="pt-2">
            <Link
              to="/for-you"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-sm transition-colors"
            >
              <Compass className="w-4 h-4" />
              <span>Explore Your Feed</span>
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {savedStories.map((story) => (
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

