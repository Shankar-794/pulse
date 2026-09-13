/**
 * Local Storage Persistence Layer for Pulse Foundation.
 * Manages client bookmarks, followed topics, and personalization settings.
 * Designed to cleanly map to future PostgreSQL sync endpoints.
 */

const STORAGE_KEYS = {
  SAVED_STORIES: 'pulse_saved_story_ids',
  FOLLOWED_TOPICS: 'pulse_followed_topic_ids',
  HIDDEN_STORIES: 'pulse_hidden_story_ids',
  PREFERENCES: 'pulse_user_preferences',
};

export const StorageService = {
  getSavedStoryIds: () => {
    try {
      const data = localStorage.getItem(STORAGE_KEYS.SAVED_STORIES);
      return data ? JSON.parse(data) : ['story-003', 'story-006'];
    } catch {
      return ['story-003', 'story-006'];
    }
  },

  toggleSaveStory: (storyId) => {
    try {
      const current = new Set(StorageService.getSavedStoryIds());
      const isSaved = current.has(storyId);
      if (isSaved) {
        current.delete(storyId);
      } else {
        current.add(storyId);
      }
      const updated = Array.from(current);
      localStorage.setItem(STORAGE_KEYS.SAVED_STORIES, JSON.stringify(updated));
      window.dispatchEvent(new CustomEvent('pulse_saved_updated', { detail: { storyId, isSaved: !isSaved } }));
      return !isSaved;
    } catch {
      return false;
    }
  },

  isStorySaved: (storyId) => {
    const saved = StorageService.getSavedStoryIds();
    return saved.includes(storyId);
  },

  getHiddenStoryIds: () => {
    try {
      const data = localStorage.getItem(STORAGE_KEYS.HIDDEN_STORIES);
      return data ? JSON.parse(data) : [];
    } catch {
      return [];
    }
  },

  hideStory: (storyId) => {
    try {
      const current = new Set(StorageService.getHiddenStoryIds());
      current.add(storyId);
      const updated = Array.from(current);
      localStorage.setItem(STORAGE_KEYS.HIDDEN_STORIES, JSON.stringify(updated));
      window.dispatchEvent(new CustomEvent('pulse_hidden_updated', { detail: { storyId } }));
      return updated;
    } catch {
      return [];
    }
  },

  getFollowedTopicIds: () => {
    try {
      const data = localStorage.getItem(STORAGE_KEYS.FOLLOWED_TOPICS);
      return data ? JSON.parse(data) : ['topic-ai', 'topic-ml', 'topic-swe', 'topic-cyber', 'topic-space', 'topic-semiconductors', 'topic-science'];
    } catch {
      return ['topic-ai', 'topic-ml', 'topic-swe', 'topic-cyber', 'topic-space', 'topic-semiconductors', 'topic-science'];
    }
  },

  toggleFollowTopic: (topicId) => {
    try {
      const current = new Set(StorageService.getFollowedTopicIds());
      const isFollowed = current.has(topicId);
      if (isFollowed) {
        current.delete(topicId);
      } else {
        current.add(topicId);
      }
      const updated = Array.from(current);
      localStorage.setItem(STORAGE_KEYS.FOLLOWED_TOPICS, JSON.stringify(updated));
      window.dispatchEvent(new CustomEvent('pulse_topics_updated', { detail: { topicId, isFollowed: !isFollowed } }));
      return !isFollowed;
    } catch {
      return false;
    }
  },

  getPreferences: (defaultPrefs) => {
    try {
      const data = localStorage.getItem(STORAGE_KEYS.PREFERENCES);
      return data ? JSON.parse(data) : defaultPrefs;
    } catch {
      return defaultPrefs;
    }
  },

  savePreferences: (prefs) => {
    try {
      localStorage.setItem(STORAGE_KEYS.PREFERENCES, JSON.stringify(prefs));
      window.dispatchEvent(new CustomEvent('pulse_preferences_updated', { detail: prefs }));
      return true;
    } catch {
      return false;
    }
  }
};
