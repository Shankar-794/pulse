import React, { useState, useEffect } from 'react';
import { Hash, Search } from 'lucide-react';
import { ApiService } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { addPendingAction } from '../services/pendingActions';
import TopicCard from '../components/topics/TopicCard';

export default function TopicsPage() {
  const { isAuthenticated, openLoginModal } = useAuth();
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterQuery, setFilterQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('all');

  const loadTopics = async () => {
    setLoading(true);
    const data = await ApiService.getTopics();
    setTopics(data);
    setLoading(false);
  };

  useEffect(() => {
    loadTopics();

    const handleTopicsUpdated = () => {
      loadTopics();
    };

    window.addEventListener('pulse_topics_updated', handleTopicsUpdated);
    return () => {
      window.removeEventListener('pulse_topics_updated', handleTopicsUpdated);
    };
  }, []);

  const handleToggleFollow = async (topicId, isFollowed) => {
    if (!isAuthenticated) {
      addPendingAction('FOLLOW_TOPIC', { topicId, isFollowed });
      openLoginModal({
        title: 'Sign in to personalize Pulse',
        message: 'Your action will be saved and completed after you sign in.'
      });
      return;
    }

    try {
      await ApiService.toggleTopicFollow(topicId, isFollowed);
      setTopics((prev) =>
        prev.map((t) => (t.id === topicId ? { ...t, is_followed: isFollowed } : t))
      );
    } catch (err) {
      console.error('Failed to toggle topic follow:', err);
    }
  };

  const filteredTopics = topics.filter((t) => {
    const matchesQuery =
      t.name.toLowerCase().includes(filterQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(filterQuery.toLowerCase()) ||
      t.slug.toLowerCase().includes(filterQuery.toLowerCase());
    const matchesCat = activeCategory === 'all' || t.category.toLowerCase() === activeCategory.toLowerCase();
    return matchesQuery && matchesCat;
  });

  const followedCount = topics.filter((t) => t.is_followed).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Hash className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <h1 className="text-2xl sm:text-3xl font-bold font-sans text-news-text-primary">
                Explore Topics
              </h1>
            </div>
            <p className="text-sm text-news-text-secondary">
              Follow technical domains to calibrate your personal feed relevance.
            </p>
          </div>
          <div className="px-3.5 py-1.5 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-900/50 rounded-full text-xs font-semibold text-blue-700 dark:text-blue-300 self-start sm:self-auto">
            Following {followedCount} of {topics.length} topics
          </div>
        </div>

        {/* Filter Controls */}
        <div className="pt-4 border-t border-news-border flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            {['all', 'ai', 'technology', 'cybersecurity', 'space', 'science', 'business', 'economy', 'world'].map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setActiveCategory(cat)}
                className={`px-3 py-1 text-xs font-medium rounded-full capitalize transition-colors ${
                  activeCategory === cat
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 dark:bg-neutral-800 text-slate-600 dark:text-neutral-300 hover:bg-slate-200 dark:hover:bg-neutral-700'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-60">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              placeholder="Filter topics..."
              className="w-full bg-slate-50 dark:bg-[#121316] border border-news-border text-xs text-news-text-primary rounded-lg pl-9 pr-3 py-1.5 outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Topics Grid */}
      {loading ? (
        <div className="p-16 text-center text-sm text-news-text-secondary">
          Loading topics directory...
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredTopics.map((topic) => (
            <TopicCard
              key={topic.id}
              topic={topic}
              onToggleFollow={handleToggleFollow}
            />
          ))}
        </div>
      )}
    </div>
  );
}
