/**
 * Pulse News Intelligence API Client
 * Connects to the FastAPI backend with offline/fallback resilience.
 */
import { MOCK_STORIES, MOCK_TOPICS, DEFAULT_USER_PREFERENCES } from '../data/mockNewsData';
import { StorageService } from './storage';

const rawApiUrl = (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '').trim();
const API_BASE = rawApiUrl
  ? rawApiUrl.replace(/\/+$/, '').endsWith('/api')
    ? rawApiUrl.replace(/\/+$/, '')
    : `${rawApiUrl.replace(/\/+$/, '')}/api`
  : '/api';

export const getAuthHeaders = () => {
  const token = localStorage.getItem('pulse_auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const ApiService = {
  /**
   * Check backend health and readiness
   */
  checkHealth: async () => {
    try {
      const res = await fetch(`${API_BASE}/health`, { method: 'GET' });
      if (!res.ok) throw new Error('Health check failed');
      return await res.json();
    } catch {
      return {
        status: 'standby',
        service: 'Pulse Mock Client (Backend Offline/Standby)',
        version: '0.1.0-foundation',
        mode: 'client-mock-store'
      };
    }
  },

  /**
   * Trigger real news ingestion cycle across permitted sources
   */
  triggerIngestion: async () => {
    try {
      const res = await fetch(`${API_BASE}/ingestion/run`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Ingestion failed:', err);
      throw err;
    }
  },

  /**
   * Trigger Story Intelligence semantic clustering pipeline
   */
  triggerClustering: async (timeWindowHours) => {
    try {
      const url = timeWindowHours 
        ? `${API_BASE}/clustering/run?time_window_hours=${timeWindowHours}`
        : `${API_BASE}/clustering/run`;
      const res = await fetch(url, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Clustering failed:', err);
      throw err;
    }
  },

  /**
   * Get clustering metrics from latest run
   */
  getClusteringMetrics: async () => {
    try {
      const res = await fetch(`${API_BASE}/clustering/metrics`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return null;
    }
  },


  /**
   * Get registered news sources
   */
  getIngestionSources: async () => {
    try {
      const res = await fetch(`${API_BASE}/ingestion/sources`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return [];
    }
  },

  /**
   * Query real stored news articles
   */
  getNewsArticles: async ({ category, source, search, limit = 50, offset = 0 } = {}) => {
    try {
      const params = new URLSearchParams();
      if (category) params.append('category', category);
      if (source) params.append('source', source);
      if (search) params.append('search', search);
      params.append('limit', limit);
      params.append('offset', offset);

      const res = await fetch(`${API_BASE}/news?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return { total: 0, count: 0, items: [] };
    }
  },

  /**
   * Fetch clustered stories with optional filters
   */
  getStories: async ({ category, topic, section, search, minImportance } = {}) => {
    try {
      const params = new URLSearchParams();
      if (category) params.append('category', category);
      if (topic) params.append('topic', topic);
      if (section) params.append('section', section);
      if (search) params.append('search', search);
      if (minImportance !== undefined && minImportance !== null) params.append('min_importance', minImportance);

      const res = await fetch(`${API_BASE}/stories?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      
      // If backend explicitly returns empty state (no ingested articles yet)
      if (data.is_empty) {
        return {
          total: 0,
          items: [],
          is_empty: true,
          message: data.message
        };
      }

      // Handle both raw array and object with items
      const rawItems = Array.isArray(data) ? data : (data.items || []);
      const savedIds = new Set(StorageService.getSavedStoryIds());
      const hiddenIds = new Set(StorageService.getHiddenStoryIds());
      
      const filtered = rawItems.filter(s => !hiddenIds.has(s.id)).map(s => ({
        ...s,
        is_saved: savedIds.has(s.id)
      }));

      return {
        total: filtered.length,
        items: filtered,
        is_real_data: data.is_real_data,
        is_empty: filtered.length === 0
      };
    } catch (err) {
      // Fallback to local dataset only if backend unreachable
      const savedIds = new Set(StorageService.getSavedStoryIds());
      const hiddenIds = new Set(StorageService.getHiddenStoryIds());
      
      let items = MOCK_STORIES.filter(s => !hiddenIds.has(s.id)).map(s => ({
        ...s,
        is_saved: savedIds.has(s.id)
      }));

      if (category) {
        items = items.filter(s => s.category.toLowerCase() === category.toLowerCase());
      }
      if (topic) {
        items = items.filter(s => 
          s.primary_topic.toLowerCase() === topic.toLowerCase() ||
          s.tags.some(t => t.toLowerCase() === topic.toLowerCase())
        );
      }
      if (section === 'breaking') {
        items = items.filter(s => s.is_breaking);
      } else if (section === 'important') {
        items = items.filter(s => s.importance_score >= 85);
      }
      if (minImportance) {
        items = items.filter(s => s.importance_score >= minImportance);
      }
      if (search) {
        const q = search.toLowerCase();
        items = items.filter(s => 
          s.title.toLowerCase().includes(q) ||
          s.summary.toLowerCase().includes(q) ||
          s.tags.some(t => t.toLowerCase().includes(q)) ||
          s.entities.some(e => e.name.toLowerCase().includes(q))
        );
      }

      return { total: items.length, items };
    }
  },

  /**
   * Fetch single story by ID
   */
  getStoryById: async (storyId) => {
    try {
      const res = await fetch(`${API_BASE}/stories/${storyId}`);
      if (!res.ok) throw new Error('Not found');
      const data = await res.json();
      const savedIds = new Set(StorageService.getSavedStoryIds());
      return {
        ...data,
        is_saved: savedIds.has(data.id)
      };
    } catch {
      const savedIds = new Set(StorageService.getSavedStoryIds());
      const found = MOCK_STORIES.find(s => s.id === storyId);
      if (found) {
        return {
          ...found,
          is_saved: savedIds.has(found.id)
        };
      }
      return null;
    }
  },

  /**
   * Trigger AI understanding analysis on a specific story
   */
  analyzeStory: async (storyId) => {
    try {
      const res = await fetch(`${API_BASE}/stories/${storyId}/analyze`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error(`Analysis failed for story ${storyId}:`, err);
      throw err;
    }
  },

  /**
   * Trigger batch AI understanding on unanalyzed stories
   */
  analyzeBatchStories: async (limit = 10) => {
    try {
      const res = await fetch(`${API_BASE}/stories/analyze?limit=${limit}`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Batch analysis failed:', err);
      throw err;
    }
  },


  /**
   * Fetch all topics
   */
  getTopics: async () => {
    try {
      const res = await fetch(`${API_BASE}/topics`);
      if (!res.ok) throw new Error('Topics failed');
      const backendTopics = await res.json();
      const followed = new Set(StorageService.getFollowedTopicIds());
      return backendTopics.map(t => ({
        ...t,
        is_followed: followed.has(t.id)
      }));
    } catch {
      const followed = new Set(StorageService.getFollowedTopicIds());
      return MOCK_TOPICS.map(t => ({
        ...t,
        is_followed: followed.has(t.id)
      }));
    }
  },

  /**
   * Toggle topic follow
   */
  toggleTopicFollow: async (topicId, isFollowed) => {
    StorageService.toggleFollowTopic(topicId);
    try {
      await fetch(`${API_BASE}/topics/${topicId}/follow`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_followed: isFollowed })
      });
    } catch {
      // Handled locally
    }
    return isFollowed;
  },

  /**
   * Record user interaction telemetry
   */
  recordInteraction: async (storyId, interactionType) => {
    try {
      await fetch(`${API_BASE}/interactions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          story_id: storyId,
          interaction_type: interactionType
        })
      });
    } catch {
      // Telemetry queued or ignored if offline
    }
  },

  /**
   * Get user preferences
   */
  getPreferences: async () => {
    try {
      const res = await fetch(`${API_BASE}/preferences`);
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Fallback
    }
    return StorageService.getPreferences(DEFAULT_USER_PREFERENCES);
  },

  /**
   * Update user preferences
   */
  updatePreferences: async (prefs) => {
    StorageService.savePreferences(prefs);
    try {
      await fetch(`${API_BASE}/preferences`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prefs)
      });
    } catch {
      // Saved locally
    }
    return prefs;
  },

  /**
   * Fetch personalized feed ranked by Personal Relevance & Global Importance
   */
  getFeed: async ({ limit = 50, offset = 0 } = {}) => {
    try {
      const params = new URLSearchParams();
      params.append('limit', limit);
      params.append('offset', offset);

      const res = await fetch(`${API_BASE}/feed?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.is_empty) {
        return {
          total: 0,
          items: [],
          is_empty: true,
          message: data.message
        };
      }

      const savedIds = new Set(StorageService.getSavedStoryIds());
      const hiddenIds = new Set(StorageService.getHiddenStoryIds());

      const rawItems = Array.isArray(data) ? data : (data.items || []);
      const filtered = rawItems.filter(s => !hiddenIds.has(s.id)).map(s => ({
        ...s,
        is_saved: savedIds.has(s.id) || s.is_saved
      }));

      return {
        total: filtered.length,
        items: filtered,
        is_real_data: true,
        is_empty: filtered.length === 0
      };
    } catch {
      // Fall back to standard stories
      return await ApiService.getStories({ limit });
    }
  },

  /**
   * Get complete personalization profile with affinities and interest weights
   */
  getPersonalizationProfile: async () => {
    try {
      const res = await fetch(`${API_BASE}/personalization/profile`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return null;
    }
  },

  /**
   * Get story personal relevance breakdown and explainability
   */
  getStoryRelevance: async (storyId) => {
    try {
      const res = await fetch(`${API_BASE}/stories/${storyId}/relevance`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return null;
    }
  },

  /**
   * Trigger batch recalculation of personal relevance for all stories
   */
  recalculatePersonalization: async () => {
    try {
      const res = await fetch(`${API_BASE}/personalization/recalculate`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Recalculation failed:', err);
      throw err;
    }
  },

  /**
   * Trigger deterministic story evolution lifecycle assessment (Phase 7)
   */
  evolveStory: async (storyId) => {
    try {
      const res = await fetch(`${API_BASE}/stories/${storyId}/evolve`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Evolve story failed:', err);
      throw err;
    }
  },

  /**
   * Batch evaluate story evolution and breaking scores (Phase 7)
   */
  evolveBatchStories: async (limit = 50) => {
    try {
      const res = await fetch(`${API_BASE}/stories/evolve?limit=${limit}`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Batch evolve stories failed:', err);
      throw err;
    }
  },

  /**
   * Get grounded story timeline events (Phase 7)
   */
  getStoryTimeline: async (storyId) => {
    try {
      const res = await fetch(`${API_BASE}/stories/${storyId}/timeline`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Get story timeline failed:', err);
      return { story_id: storyId, total_events: 0, events: [] };
    }
  },

  /**
   * Run end-to-end Pulse pipeline (Phase 8.1)
   */
  runPipeline: async ({ skipIngestion = false, timeWindowHours } = {}) => {
    try {
      const params = new URLSearchParams();
      if (skipIngestion) params.append('skip_ingestion', 'true');
      if (timeWindowHours) params.append('time_window_hours', timeWindowHours);

      const res = await fetch(`${API_BASE}/pipeline/run?${params.toString()}`, { method: 'POST' });
      if (!res.ok) {
        let message = `HTTP ${res.status}`;
        try {
          const data = await res.json();
          if (data?.detail?.message) message = data.detail.message;
          else if (typeof data?.detail === 'string') message = data.detail;
        } catch (_) {}
        const err = new Error(message);
        err.status = res.status;
        throw err;
      }
      return await res.json();
    } catch (err) {
      console.error('Pipeline run failed:', err);
      throw err;
    }
  },

  /**
   * Get latest pipeline run status (Phase 8.1)
   */
  getPipelineStatus: async () => {
    try {
      const res = await fetch(`${API_BASE}/pipeline/status`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Get pipeline status failed:', err);
      return { status: 'error', error: err.message };
    }
  },

  /**
   * Get comprehensive system health and operational metrics (Phase 8.1)
   */
  getSystemHealth: async () => {
    try {
      const res = await fetch(`${API_BASE}/system/health`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Get system health failed:', err);
      return { status: 'error', error: err.message };
    }
  },

  /**
   * Get recent pipeline runs history with optional filtering (Phase 8.2 Steps 1 & 4)
   */
  getPipelineRuns: async (paramsOrLimit = 20) => {
    try {
      const params = new URLSearchParams();
      if (typeof paramsOrLimit === 'number') {
        params.append('limit', paramsOrLimit);
      } else if (paramsOrLimit && typeof paramsOrLimit === 'object') {
        const { limit = 20, status, triggerType } = paramsOrLimit;
        if (limit) params.append('limit', limit);
        if (status) params.append('status', status);
        if (triggerType) params.append('trigger_type', triggerType);
      }

      const res = await fetch(`${API_BASE}/pipeline/runs?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Get pipeline runs failed:', err);
      return [];
    }
  },

  /**
   * Get complete execution details for a specific pipeline run (Phase 8.2 Step 4)
   */
  getPipelineRun: async (runId) => {
    try {
      const res = await fetch(`${API_BASE}/pipeline/runs/${encodeURIComponent(runId)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error(`Get pipeline run ${runId} failed:`, err);
      throw err;
    }
  },

  /**
   * Get automatic pipeline scheduler operational status (Phase 8.2 Steps 3 & 4)
   */
  getSchedulerStatus: async () => {
    try {
      const res = await fetch(`${API_BASE}/pipeline/scheduler`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Get scheduler status failed:', err);
      return { status: 'error', error: err.message };
    }
  },

  /**
   * Start automatic pipeline scheduler (Phase 8.2 Step 4)
   */
  startScheduler: async () => {
    try {
      const res = await fetch(`${API_BASE}/pipeline/scheduler/start`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Start scheduler failed:', err);
      throw err;
    }
  },

  /**
   * Stop automatic pipeline scheduler (Phase 8.2 Step 4)
   */
  stopScheduler: async () => {
    try {
      const res = await fetch(`${API_BASE}/pipeline/scheduler/stop`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Stop scheduler failed:', err);
      throw err;
    }
  },

  /**
   * Pause automatic pipeline scheduler (Phase 8.2 Step 4)
   */
  pauseScheduler: async () => {
    try {
      const res = await fetch(`${API_BASE}/pipeline/scheduler/pause`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Pause scheduler failed:', err);
      throw err;
    }
  },

  /**
   * Resume automatic pipeline scheduler (Phase 8.2 Step 4)
   */
  resumeScheduler: async () => {
    try {
      const res = await fetch(`${API_BASE}/pipeline/scheduler/resume`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Resume scheduler failed:', err);
      throw err;
    }
  },

  /**
   * Update runtime scheduler configuration (Phase 8.2 Step 4)
   */
  configureScheduler: async ({ intervalMinutes, enabled } = {}) => {
    try {
      const payload = {};
      if (intervalMinutes !== undefined) payload.interval_minutes = intervalMinutes;
      if (enabled !== undefined) payload.enabled = enabled;

      const res = await fetch(`${API_BASE}/pipeline/scheduler/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      console.error('Configure scheduler failed:', err);
      throw err;
    }
  },

  // =========================================================================
  // Authentication & User Session Management
  // =========================================================================

  /**
   * Get public auth configuration
   */
  getAuthConfig: async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/config`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch {
      return { google_configured: false, client_id: '', redirect_uri: '' };
    }
  },

  /**
   * Get Google OAuth login URL
   */
  getGoogleAuthUrl: async (redirectUri) => {
    try {
      const params = redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : '';
      const res = await fetch(`${API_BASE}/auth/google/url${params}`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (err) {
      console.error('Failed to get Google Auth URL:', err);
      throw err;
    }
  },

  /**
   * Complete Google OAuth callback
   */
  handleGoogleCallback: async (code, redirectUri) => {
    try {
      const res = await fetch(`${API_BASE}/auth/google/callback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, redirect_uri: redirectUri })
      });
      if (!res.ok) {
        throw new Error('Unable to complete Google sign-in. Please try again.');
      }
      localStorage.removeItem('pulse_saved_story_ids');
      return await res.json();
    } catch (err) {
      throw err;
    }
  },

  /**
   * Developer / offline login (development only)
   */
  devLogin: async ({ email, name, pictureUrl } = {}) => {
    try {
      const res = await fetch(`${API_BASE}/auth/dev-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, name, picture_url: pictureUrl })
      });
      if (!res.ok) {
        throw new Error('Unable to authenticate. Please try again.');
      }
      localStorage.removeItem('pulse_saved_story_ids');
      return await res.json();
    } catch (err) {
      throw err;
    }
  },

  /**
   * Fetch current authenticated user profile
   */
  getCurrentUser: async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: getAuthHeaders()
      });
      if (!res.ok) return null;
      const data = await res.json();
      return data.user || null;
    } catch {
      return null;
    }
  },

  /**
   * Logout current session
   */
  logout: async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
    } catch {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem('pulse_auth_token');
      localStorage.removeItem('pulse_user_profile');
      localStorage.removeItem('pulse_saved_story_ids');
      window.dispatchEvent(new CustomEvent('pulse_saved_updated', { detail: { count: 0 } }));
    }
  },

  // =========================================================================
  // Per-User Saved Stories Persistence
  // =========================================================================

  /**
   * Retrieve stories saved by current user
   */
  getSavedStories: async () => {
    const isAuthed = !!localStorage.getItem('pulse_auth_token');
    if (isAuthed) {
      try {
        const res = await fetch(`${API_BASE}/stories/saved`, {
          headers: getAuthHeaders()
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
      } catch {
        return { total: 0, items: [] };
      }
    }
    // Unauthenticated: only return locally saved stories if any exist
    try {
      const savedIds = new Set(StorageService.getSavedStoryIds());
      if (savedIds.size === 0) {
        return { total: 0, items: [] };
      }
      const allStories = await ApiService.getStories();
      const filtered = (allStories.items || []).filter(s => savedIds.has(s.id)).map(s => ({
        ...s,
        is_saved: true
      }));
      return { total: filtered.length, items: filtered };
    } catch {
      return { total: 0, items: [] };
    }
  },

  /**
   * Save a story for current user
   */
  saveStory: async (storyId) => {
    const isAuthed = !!localStorage.getItem('pulse_auth_token');
    if (!isAuthed) {
      StorageService.toggleSaveStory(storyId);
      window.dispatchEvent(new CustomEvent('pulse_saved_updated', { detail: { storyId, isSaved: true } }));
      return { status: 'success', story_id: storyId, is_saved: true };
    }
    try {
      const res = await fetch(`${API_BASE}/stories/${storyId}/save`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      window.dispatchEvent(new CustomEvent('pulse_saved_updated', { detail: { storyId, isSaved: true } }));
      return data;
    } catch {
      throw new Error('Unable to save story. Please try again.');
    }
  },

  /**
   * Remove a story from current user's saved list
   */
  unsaveStory: async (storyId) => {
    const isAuthed = !!localStorage.getItem('pulse_auth_token');
    if (!isAuthed) {
      StorageService.toggleSaveStory(storyId);
      window.dispatchEvent(new CustomEvent('pulse_saved_updated', { detail: { storyId, isSaved: false } }));
      return { status: 'success', story_id: storyId, is_saved: false };
    }
    try {
      const res = await fetch(`${API_BASE}/stories/${storyId}/save`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      window.dispatchEvent(new CustomEvent('pulse_saved_updated', { detail: { storyId, isSaved: false } }));
      return data;
    } catch {
      throw new Error('Unable to remove story. Please try again.');
    }
  }
};


