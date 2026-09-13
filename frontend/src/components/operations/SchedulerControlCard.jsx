import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Clock,
  Play,
  Square,
  Pause,
  RotateCcw,
  Settings2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Loader2
} from 'lucide-react';
import { ApiService } from '../../services/api';

/**
 * Helper to compute human-friendly relative and absolute countdown.
 */
function getNextRunDisplay(nextRunTime, status) {
  if (!nextRunTime || status !== 'running') {
    return {
      primary: 'Not scheduled',
      secondary: status === 'paused' ? 'Scheduler paused' : 'Scheduler inactive'
    };
  }

  try {
    const target = new Date(nextRunTime);
    if (isNaN(target.getTime())) {
      return { primary: 'Not scheduled', secondary: 'Invalid timestamp' };
    }

    const now = new Date();
    const diffMs = target.getTime() - now.getTime();
    const diffSec = Math.round(diffMs / 1000);

    const timeStr = target.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    const dateStr = target.toLocaleDateString([], { month: 'short', day: 'numeric' });
    const formattedExact = `${dateStr}, ${timeStr}`;

    if (diffSec <= 0) {
      return { primary: 'Due now', secondary: formattedExact };
    }
    if (diffSec < 60) {
      return { primary: 'in < 1 min', secondary: formattedExact };
    }

    const diffMin = Math.round(diffSec / 60);
    if (diffMin < 60) {
      return { primary: `in ~${diffMin} min`, secondary: formattedExact };
    }

    const diffHours = Math.floor(diffMin / 60);
    const remainingMin = diffMin % 60;
    return {
      primary: `in ~${diffHours}h ${remainingMin}m`,
      secondary: formattedExact
    };
  } catch {
    return { primary: 'Not scheduled', secondary: '' };
  }
}

export default function SchedulerControlCard() {
  const [scheduler, setScheduler] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null); // 'start' | 'pause' | 'resume' | 'stop' | 'apply' | 'refresh'
  const [errorMessage, setErrorMessage] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [intervalInput, setIntervalInput] = useState('30');
  const [isInputDirty, setIsInputDirty] = useState(false);
  const [_tick, setTick] = useState(0);

  const isMountedRef = useRef(true);
  const inFlightRef = useRef(false);

  // Load scheduler status from backend
  const fetchStatus = useCallback(async (isManualRefresh = false) => {
    if (inFlightRef.current && !isManualRefresh) return;
    inFlightRef.current = true;

    if (isManualRefresh) {
      setActionLoading('refresh');
    }

    try {
      const data = await ApiService.getSchedulerStatus();
      if (!isMountedRef.current) return;

      if (data && data.status !== 'error') {
        setScheduler(data);
        // Synchronize input if user hasn't edited it
        if (!isInputDirty && data.interval_minutes !== undefined) {
          setIntervalInput(String(data.interval_minutes));
        }
        setErrorMessage(null);
      } else if (data?.error) {
        setErrorMessage(data.error);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setErrorMessage(err.message || 'Failed to fetch scheduler status');
      }
    } finally {
      inFlightRef.current = false;
      if (isMountedRef.current) {
        setLoading(false);
        if (isManualRefresh) {
          setActionLoading(null);
        }
      }
    }
  }, [isInputDirty]);

  // Initial fetch and 6-second polling heartbeat
  useEffect(() => {
    isMountedRef.current = true;
    fetchStatus();

    const intervalId = setInterval(() => {
      // Don't poll if mutation action is actively executing
      if (!actionLoading) {
        fetchStatus();
      }
    }, 6000);

    // 30-second tick for relative countdown re-renders
    const tickIntervalId = setInterval(() => {
      setTick((t) => t + 1);
    }, 30000);

    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);
      clearInterval(tickIntervalId);
    };
  }, [fetchStatus, actionLoading]);

  // Auto-clear success messages after 3 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => {
        if (isMountedRef.current) setSuccessMessage(null);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Mutation handler
  const handleAction = async (actionType, apiCall, successText) => {
    setActionLoading(actionType);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await apiCall();
      if (!isMountedRef.current) return;
      setSuccessMessage(successText);
      if (res && res.status) {
        setScheduler(res);
        if (res.interval_minutes !== undefined && !isInputDirty) {
          setIntervalInput(String(res.interval_minutes));
        }
      } else {
        await fetchStatus();
      }
    } catch (err) {
      if (isMountedRef.current) {
        setErrorMessage(err.message || `Failed to execute ${actionType}`);
      }
    } finally {
      if (isMountedRef.current) {
        setActionLoading(null);
      }
    }
  };

  const handleStart = () =>
    handleAction('start', () => ApiService.startScheduler(), 'Scheduler started successfully');

  const handlePause = () =>
    handleAction('pause', () => ApiService.pauseScheduler(), 'Scheduler paused');

  const handleResume = () =>
    handleAction('resume', () => ApiService.resumeScheduler(), 'Scheduler resumed');

  const handleStop = () =>
    handleAction('stop', () => ApiService.stopScheduler(), 'Scheduler stopped');

  const handleApplyInterval = async (e) => {
    e?.preventDefault();
    const parsed = parseInt(intervalInput, 10);
    if (isNaN(parsed) || parsed < 1) {
      setErrorMessage('Interval must be a positive number of minutes (minimum 1).');
      return;
    }

    setActionLoading('apply');
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await ApiService.configureScheduler({
        intervalMinutes: parsed,
        enabled: scheduler?.enabled ?? true
      });
      if (!isMountedRef.current) return;
      setSuccessMessage(`Interval updated to ${parsed} minutes`);
      setIsInputDirty(false);
      if (res && res.status) {
        setScheduler(res);
      } else {
        await fetchStatus();
      }
    } catch (err) {
      if (isMountedRef.current) {
        setErrorMessage(err.message || 'Failed to update scheduler interval');
      }
    } finally {
      if (isMountedRef.current) {
        setActionLoading(null);
      }
    }
  };

  const handlePresetSelect = (mins) => {
    setIntervalInput(String(mins));
    setIsInputDirty(true);
    setErrorMessage(null);
  };

  // Derive scheduler state
  const rawStatus = (scheduler?.status || (scheduler?.running ? 'running' : 'stopped')).toLowerCase();
  const isRunning = rawStatus === 'running';
  const isPaused = rawStatus === 'paused';
  const isStopped = rawStatus === 'stopped';
  const isDisabled = rawStatus === 'disabled' || scheduler?.enabled === false;

  // Derive button disabled states based on actual state and active mutation
  const isMutating = actionLoading !== null;
  const startDisabled = isMutating || isRunning || isPaused || isDisabled;
  const pauseDisabled = isMutating || !isRunning || isPaused || isStopped || isDisabled;
  const resumeDisabled = isMutating || !isPaused || isDisabled;
  const stopDisabled = isMutating || isStopped || isDisabled;

  const currentInterval = scheduler?.interval_minutes ?? 30;
  const parsedInput = parseInt(intervalInput, 10);
  const isApplyDisabled =
    isMutating ||
    isNaN(parsedInput) ||
    parsedInput < 1 ||
    (parsedInput === currentInterval && !isInputDirty);

  // Compute next execution info
  const nextRunInfo = getNextRunDisplay(scheduler?.next_run_time, rawStatus);

  // Status badge styling
  const getStatusBadge = () => {
    if (isDisabled) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-100 dark:bg-neutral-800 border border-slate-200 dark:border-neutral-700 text-slate-600 dark:text-neutral-400 rounded-full text-xs font-semibold uppercase tracking-wider">
          <span className="w-2 h-2 rounded-full bg-slate-400 shrink-0" />
          <span>Disabled</span>
        </span>
      );
    }
    if (isRunning) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400 rounded-full text-xs font-semibold uppercase tracking-wider">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
          <span>Running</span>
        </span>
      );
    }
    if (isPaused) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-400 rounded-full text-xs font-semibold uppercase tracking-wider">
          <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
          <span>Paused</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-400 rounded-full text-xs font-semibold uppercase tracking-wider">
        <span className="w-2 h-2 rounded-full bg-rose-500 shrink-0" />
        <span>Stopped</span>
      </span>
    );
  };

  const consecutiveFailures = scheduler?.consecutive_failure_count ?? 0;

  return (
    <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card space-y-6 transition-colors">
      {/* Card Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-news-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200/60 dark:border-blue-900/40 flex items-center justify-center text-blue-600 dark:text-blue-400 shrink-0">
            <Clock className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-lg font-bold font-sans text-news-text-primary">
                Scheduler
              </h2>
              {getStatusBadge()}
            </div>
            <p className="text-xs text-news-text-secondary mt-0.5">
              Automatic pipeline orchestration and background execution
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => fetchStatus(true)}
          disabled={isMutating}
          title="Refresh scheduler status"
          aria-label="Refresh scheduler status"
          className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-neutral-800 hover:bg-slate-200 dark:hover:bg-neutral-700 text-slate-700 dark:text-neutral-300 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${actionLoading === 'refresh' ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Inline Feedback Alerts */}
      {errorMessage && (
        <div className="p-3.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 flex items-start justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600 dark:text-rose-400" />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="text-rose-600 dark:text-rose-400 hover:underline font-semibold"
          >
            Dismiss
          </button>
        </div>
      )}

      {successMessage && (
        <div className="p-3.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-emerald-800 dark:text-emerald-300 flex items-center gap-2 text-xs">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Operational Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Status */}
        <div className="p-4 rounded-xl border border-news-border bg-slate-50/60 dark:bg-[#121316]/60 space-y-1">
          <span className="text-[11px] font-semibold text-news-text-secondary uppercase tracking-wider block">
            State
          </span>
          <div className="text-sm font-bold text-news-text-primary capitalize flex items-center gap-1.5">
            {rawStatus}
          </div>
          <p className="text-[11px] text-news-text-secondary">
            {isDisabled
              ? 'Scheduler turned off in config'
              : isRunning
              ? 'Active automatic cadence'
              : isPaused
              ? 'Suspended until resumed'
              : 'Stopped / not active'}
          </p>
        </div>

        {/* Metric 2: Cadence Interval */}
        <div className="p-4 rounded-xl border border-news-border bg-slate-50/60 dark:bg-[#121316]/60 space-y-1">
          <span className="text-[11px] font-semibold text-news-text-secondary uppercase tracking-wider block">
            Interval
          </span>
          <div className="text-sm font-bold text-news-text-primary">
            {loading ? '...' : `${currentInterval} minutes`}
          </div>
          <p className="text-[11px] text-news-text-secondary">
            Periodic execution cycle
          </p>
        </div>

        {/* Metric 3: Next Execution */}
        <div className="p-4 rounded-xl border border-news-border bg-slate-50/60 dark:bg-[#121316]/60 space-y-1">
          <span className="text-[11px] font-semibold text-news-text-secondary uppercase tracking-wider block">
            Next Execution
          </span>
          <div className="text-sm font-bold text-news-text-primary truncate">
            {loading ? '...' : nextRunInfo.primary}
          </div>
          <p className="text-[11px] text-news-text-secondary truncate">
            {nextRunInfo.secondary || '—'}
          </p>
        </div>

        {/* Metric 4: Last Triggered Run */}
        <div className="p-4 rounded-xl border border-news-border bg-slate-50/60 dark:bg-[#121316]/60 space-y-1">
          <span className="text-[11px] font-semibold text-news-text-secondary uppercase tracking-wider block">
            Last Triggered Run
          </span>
          <div className="text-sm font-bold text-news-text-primary truncate font-mono text-xs">
            {scheduler?.last_triggered_run_id ? (
              <span className="px-2 py-0.5 bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-900 text-blue-700 dark:text-blue-300 rounded">
                {scheduler.last_triggered_run_id}
              </span>
            ) : (
              'No scheduled run yet'
            )}
          </div>
          <p className="text-[11px] text-news-text-secondary">
            {scheduler?.last_triggered_at
              ? new Date(scheduler.last_triggered_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
              : 'Awaiting scheduled trigger'}
          </p>
        </div>
      </div>

      {/* Failure Signal Indicator */}
      <div className="pt-2 pb-1">
        {consecutiveFailures > 0 ? (
          <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-800 text-amber-800 dark:text-amber-300 flex items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <span className="font-semibold">
                {consecutiveFailures} consecutive pipeline {consecutiveFailures === 1 ? 'failure' : 'failures'}
              </span>
              {scheduler?.last_failure_message && (
                <span className="text-amber-700 dark:text-amber-400/80 truncate max-w-md hidden md:inline">
                  — {scheduler.last_failure_message}
                </span>
              )}
            </div>
            <span className="text-[11px] text-amber-700 dark:text-amber-400 shrink-0">
              Circuit protection active
            </span>
          </div>
        ) : (
          <div className="p-2.5 rounded-lg bg-emerald-50/60 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300 flex items-center gap-2 text-xs">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span className="font-medium">
              Healthy · No consecutive failures recorded
            </span>
          </div>
        )}
      </div>

      {/* Controls Section */}
      <div className="pt-4 border-t border-news-border space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-news-text-primary uppercase tracking-wider">
            Scheduler Controls
          </span>
          <span className="text-[11px] text-news-text-secondary">
            State-synchronized control triggers
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Start */}
          <button
            type="button"
            onClick={handleStart}
            disabled={startDisabled}
            aria-label="Start automatic scheduler"
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
          >
            {actionLoading === 'start' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4 fill-current" />
            )}
            <span>Start</span>
          </button>

          {/* Pause */}
          <button
            type="button"
            onClick={handlePause}
            disabled={pauseDisabled}
            aria-label="Pause automatic scheduler"
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
          >
            {actionLoading === 'pause' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Pause className="w-4 h-4" />
            )}
            <span>Pause</span>
          </button>

          {/* Resume */}
          <button
            type="button"
            onClick={handleResume}
            disabled={resumeDisabled}
            aria-label="Resume automatic scheduler"
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
          >
            {actionLoading === 'resume' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RotateCcw className="w-4 h-4" />
            )}
            <span>Resume</span>
          </button>

          {/* Stop */}
          <button
            type="button"
            onClick={handleStop}
            disabled={stopDisabled}
            aria-label="Stop automatic scheduler"
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
          >
            {actionLoading === 'stop' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Square className="w-4 h-4 fill-current" />
            )}
            <span>Stop</span>
          </button>
        </div>
      </div>

      {/* Cadence / Interval Configuration Section */}
      <div className="pt-4 border-t border-news-border space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <div className="flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <span className="text-xs font-bold text-news-text-primary uppercase tracking-wider">
              Interval Configuration
            </span>
          </div>
          <span className="text-[11px] text-news-text-secondary">
            Active cadence: <strong className="text-news-text-primary">{currentInterval}m</strong>
          </span>
        </div>

        <form onSubmit={handleApplyInterval} className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          {/* Quick Presets */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-xs text-news-text-secondary mr-1">Presets:</span>
            {[15, 30, 60].map((preset) => {
              const isSelected = parsedInput === preset;
              return (
                <button
                  key={preset}
                  type="button"
                  onClick={() => handlePresetSelect(preset)}
                  disabled={isMutating}
                  className={`px-2.5 py-1.5 text-xs font-semibold rounded-lg border transition-colors ${
                    isSelected
                      ? 'bg-blue-50 dark:bg-blue-950/60 border-blue-500 text-blue-700 dark:text-blue-300'
                      : 'bg-slate-50 dark:bg-[#121316] border-news-border text-news-text-secondary hover:text-news-text-primary hover:border-slate-400'
                  }`}
                >
                  {preset}m
                </button>
              );
            })}
          </div>

          {/* Number Input */}
          <div className="relative flex-1 min-w-[120px]">
            <input
              type="number"
              min="1"
              step="1"
              value={intervalInput}
              onChange={(e) => {
                setIntervalInput(e.target.value);
                setIsInputDirty(true);
                setErrorMessage(null);
              }}
              placeholder="Minutes (min 1)"
              aria-label="Scheduler execution interval in minutes"
              disabled={isMutating}
              className="w-full bg-slate-50 dark:bg-[#121316] border border-news-border focus:border-blue-500 text-news-text-primary text-xs rounded-lg px-3 py-2 outline-none transition-colors"
            />
          </div>

          {/* Apply Button */}
          <button
            type="submit"
            disabled={isApplyDisabled}
            aria-label="Apply new scheduler interval"
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-sm shrink-0"
          >
            {actionLoading === 'apply' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Settings2 className="w-3.5 h-3.5" />
            )}
            <span>Apply Interval</span>
          </button>
        </form>
      </div>
    </div>
  );
}
