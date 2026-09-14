/**
 * Pending Actions System for Guest-to-Authenticated User Flow.
 * 
 * Securely queues personalized actions (saving stories, following topics, preference updates)
 * initiated by unauthenticated users in namespaced localStorage ('pulse.pendingActions').
 * Replays queued actions idempotently upon successful authentication and cleans up.
 * 
 * Storage format:
 * {
 *   "version": 1,
 *   "actions": [
 *     {
 *       "id": "act_...",
 *       "type": "SAVE_STORY",
 *       "payload": { "storyId": "story_xxx" },
 *       "createdAt": "..."
 *     }
 *   ]
 * }
 */

const STORAGE_KEY = 'pulse.pendingActions';
const SCHEMA_VERSION = 1;

/**
 * Defensively parses the pending action queue from localStorage.
 * Automatically recovers from corrupt or legacy storage values.
 */
export const getPendingActionQueue = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { version: SCHEMA_VERSION, actions: [] };
    }
    const parsed = JSON.parse(raw);
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      parsed.version === SCHEMA_VERSION &&
      Array.isArray(parsed.actions)
    ) {
      return parsed;
    }
    // Storage exists but schema is invalid or outdated
    const recovered = { version: SCHEMA_VERSION, actions: [] };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(recovered));
    return recovered;
  } catch (err) {
    console.warn('[PendingActions] Corrupt localStorage recovered:', err);
    const recovered = { version: SCHEMA_VERSION, actions: [] };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(recovered));
    } catch {
      // Ignore if localStorage unavailable
    }
    return recovered;
  }
};

/**
 * Persists the action queue to localStorage.
 */
const saveQueue = (queue) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
  } catch (err) {
    console.error('[PendingActions] Failed to persist queue:', err);
  }
};

/**
 * Returns all pending actions.
 */
export const getPendingActions = () => {
  return getPendingActionQueue().actions;
};

/**
 * Enqueues a new pending action with intelligent deduplication and conflict resolution.
 * @param {string} type - 'SAVE_STORY' | 'UNSAVE_STORY' | 'FOLLOW_TOPIC' | 'UPDATE_PREFERENCES'
 * @param {object} payload - Action-specific payload
 * @returns {object} The created action object
 */
export const addPendingAction = (type, payload) => {
  const queue = getPendingActionQueue();
  const now = new Date().toISOString();
  const id = `act_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;

  // Intelligent deduplication per action type
  if (type === 'SAVE_STORY') {
    const storyId = payload?.storyId;
    if (!storyId) return null;

    // Filter out any conflicting UNSAVE_STORY or duplicate SAVE_STORY for this storyId
    queue.actions = queue.actions.filter(
      (a) => !(a.payload?.storyId === storyId && (a.type === 'SAVE_STORY' || a.type === 'UNSAVE_STORY'))
    );
  } else if (type === 'UNSAVE_STORY') {
    const storyId = payload?.storyId;
    if (!storyId) return null;

    // Filter out any conflicting SAVE_STORY or duplicate UNSAVE_STORY for this storyId
    queue.actions = queue.actions.filter(
      (a) => !(a.payload?.storyId === storyId && (a.type === 'SAVE_STORY' || a.type === 'UNSAVE_STORY'))
    );
  } else if (type === 'FOLLOW_TOPIC') {
    const topicId = payload?.topicId;
    if (!topicId) return null;

    // Keep only latest follow state for this topic
    queue.actions = queue.actions.filter(
      (a) => !(a.type === 'FOLLOW_TOPIC' && a.payload?.topicId === topicId)
    );
  } else if (type === 'UPDATE_PREFERENCES') {
    // Merge latest preference updates into previous pending update
    const existingIdx = queue.actions.findIndex((a) => a.type === 'UPDATE_PREFERENCES');
    if (existingIdx >= 0) {
      queue.actions[existingIdx].payload = {
        ...queue.actions[existingIdx].payload,
        ...payload
      };
      queue.actions[existingIdx].createdAt = now;
      saveQueue(queue);
      return queue.actions[existingIdx];
    }
  }

  const action = {
    id,
    type,
    payload,
    createdAt: now
  };

  queue.actions.push(action);
  saveQueue(queue);
  return action;
};

/**
 * Removes a specific pending action by ID upon successful execution.
 */
export const removePendingAction = (actionId) => {
  const queue = getPendingActionQueue();
  queue.actions = queue.actions.filter((a) => a.id !== actionId);
  saveQueue(queue);
};

/**
 * Clears all pending actions.
 */
export const clearPendingActions = () => {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    console.error('[PendingActions] Failed to clear queue:', err);
  }
};

/**
 * Replays all pending actions sequentially in deterministic order using authenticated client.
 * Removes each action upon success, tolerates idempotent database responses,
 * and returns summary of results.
 * 
 * @param {object} apiService - ApiService instance with active authentication credentials
 * @returns {Promise<{ total: number, succeeded: number, failed: number }>}
 */
export const replayPendingActions = async (apiService) => {
  const actions = getPendingActions();
  if (!actions || actions.length === 0) {
    return { total: 0, succeeded: 0, failed: 0 };
  }

  let succeeded = 0;
  let failed = 0;

  for (const action of actions) {
    try {
      if (action.type === 'SAVE_STORY' && action.payload?.storyId) {
        await apiService.saveStory(action.payload.storyId);
        removePendingAction(action.id);
        succeeded++;
      } else if (action.type === 'UNSAVE_STORY' && action.payload?.storyId) {
        await apiService.unsaveStory(action.payload.storyId);
        removePendingAction(action.id);
        succeeded++;
      } else if (action.type === 'FOLLOW_TOPIC' && action.payload?.topicId) {
        await apiService.toggleTopicFollow(action.payload.topicId, action.payload.isFollowed);
        removePendingAction(action.id);
        succeeded++;
      } else if (action.type === 'UPDATE_PREFERENCES' && action.payload) {
        await apiService.updatePreferences(action.payload);
        removePendingAction(action.id);
        succeeded++;
      } else {
        // Unknown or empty action type, remove to prevent queue blockage
        removePendingAction(action.id);
      }
    } catch (err) {
      console.warn(`[PendingActions] Action ${action.id} (${action.type}) replay failed:`, err);
      failed++;
      // If it's an HTTP 400/409 duplicate, it's already satisfied, so remove it
      if (err?.message && (err.message.includes('409') || err.message.includes('already'))) {
        removePendingAction(action.id);
      }
    }
  }

  // Notify components that saved stories and preferences have been synchronized
  window.dispatchEvent(new CustomEvent('pulse_saved_updated', { detail: { count: succeeded } }));
  window.dispatchEvent(new CustomEvent('pulse_topics_updated', { detail: {} }));

  return { total: actions.length, succeeded, failed };
};

export const PendingActionService = {
  getQueue: getPendingActionQueue,
  getActions: getPendingActions,
  addAction: addPendingAction,
  removeAction: removePendingAction,
  clearActions: clearPendingActions,
  replayActions: replayPendingActions
};
