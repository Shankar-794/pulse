import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Clock,
  ShieldCheck,
  ShieldAlert
} from 'lucide-react';
import { ApiService } from '../../services/api';

/**
 * Format timestamp into localized human-readable format.
 */
function formatTimestamp(isoString) {
  if (!isoString) return null;
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return null;
    return d.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit'
    });
  } catch {
    return null;
  }
}

export default function FailureMetricsBanner() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const isMountedRef = useRef(true);
  const inFlightRef = useRef(false);

  const fetchTelemetry = useCallback(async (isManual = false) => {
    if (inFlightRef.current && !isManual) return;
    inFlightRef.current = true;

    if (isManual) {
      setIsRefreshing(true);
    }

    try {
      const res = await ApiService.getPipelineStatus();
      if (!isMountedRef.current) return;

      if (res && res.status !== 'error') {
        setData(res);
        setError(null);
      } else if (res?.error) {
        setError(res.error);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err.message || 'Failure telemetry unavailable');
      }
    } finally {
      inFlightRef.current = false;
      if (isMountedRef.current) {
        setLoading(false);
        if (isManual) setIsRefreshing(false);
      }
    }
  }, []);

  // Lifecycle & 15-second polling heartbeat
  useEffect(() => {
    isMountedRef.current = true;
    fetchTelemetry();

    const intervalId = setInterval(() => {
      fetchTelemetry();
    }, 15000);

    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [fetchTelemetry]);

  // Extract failure telemetry metrics
  const failureCount = data?.consecutive_failure_count ?? 0;
  const lastFailureAt = formatTimestamp(data?.last_failure_at);
  const rawMessage = data?.last_failure_message;
  // Security/robustness: ensure message is treated strictly as plain string
  const lastFailureMessage = typeof rawMessage === 'string' ? rawMessage.trim() : null;

  // Render loading state
  if (loading && !data && !error) {
    return (
      <div className="bg-news-surface border border-news-border rounded-xl p-4 shadow-card flex items-center justify-between gap-3 text-xs text-news-text-secondary animate-pulse">
        <div className="flex items-center gap-2.5">
          <div className="w-5 h-5 rounded-full bg-slate-200 dark:bg-neutral-800" />
          <div className="h-4 w-48 bg-slate-200 dark:bg-neutral-800 rounded" />
        </div>
        <div className="h-4 w-16 bg-slate-200 dark:bg-neutral-800 rounded" />
      </div>
    );
  }

  // Render API failure / unavailable state
  if (error && !data) {
    return (
      <div className="bg-slate-50 dark:bg-[#121316] border border-news-border rounded-xl p-4 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2.5 text-news-text-secondary">
          <AlertTriangle className="w-4 h-4 text-slate-400 dark:text-neutral-500 shrink-0" />
          <span>Failure telemetry temporarily unavailable: {error}</span>
        </div>
        <button
          type="button"
          onClick={() => fetchTelemetry(true)}
          disabled={isRefreshing}
          aria-label="Retry loading failure telemetry"
          className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-200 dark:bg-neutral-800 hover:bg-slate-300 dark:hover:bg-neutral-700 text-news-text-primary rounded-lg transition-colors shrink-0 font-medium"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span>Retry</span>
        </button>
      </div>
    );
  }

  // State A: consecutive_failure_count === 0 (Healthy State)
  if (failureCount === 0) {
    return (
      <div className="bg-emerald-50/70 dark:bg-emerald-950/20 border border-emerald-200/80 dark:border-emerald-900/50 rounded-xl p-4 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-colors">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/40 border border-emerald-200 dark:border-emerald-800/60 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-900 dark:text-emerald-300">
                Pipeline Healthy
              </span>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100/80 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                0 Failures
              </span>
            </div>
            <p className="text-xs text-emerald-800/80 dark:text-emerald-300/80 mt-0.5">
              No consecutive pipeline failures recorded. Execution circuits are stable.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 self-start sm:self-auto text-xs text-emerald-800/70 dark:text-emerald-400/70 shrink-0">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            <span>Circuit Protection Active</span>
          </div>

          <button
            type="button"
            onClick={() => fetchTelemetry(true)}
            disabled={isRefreshing}
            title="Refresh failure telemetry"
            aria-label="Refresh failure telemetry"
            className="p-1.5 rounded-lg hover:bg-emerald-100/60 dark:hover:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>
    );
  }

  // State B: consecutive_failure_count > 0 (Attention / Error State)
  return (
    <div className="bg-rose-50/80 dark:bg-rose-950/30 border border-rose-300 dark:border-rose-800 rounded-xl p-4 sm:p-5 shadow-card space-y-3 transition-colors">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg bg-rose-100 dark:bg-rose-900/50 border border-rose-300 dark:border-rose-700/60 flex items-center justify-center text-rose-600 dark:text-rose-400 shrink-0 mt-0.5">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="text-xs font-bold uppercase tracking-wider text-rose-900 dark:text-rose-200">
                Pipeline Failure Detected
              </span>
              <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-rose-200/80 dark:bg-rose-900/80 text-rose-900 dark:text-rose-100 border border-rose-300 dark:border-rose-700">
                {failureCount} consecutive {failureCount === 1 ? 'failure' : 'failures'}
              </span>
            </div>

            <p className="text-xs text-rose-800 dark:text-rose-300 leading-relaxed">
              The scheduler remains operational, but persistent failures are being tracked. Subsequent runs will retry automatically per scheduler cadence.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => fetchTelemetry(true)}
          disabled={isRefreshing}
          title="Refresh failure telemetry"
          aria-label="Refresh failure telemetry"
          className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-[#18191E] border border-rose-200 dark:border-rose-800 hover:bg-rose-100/60 dark:hover:bg-rose-900/40 text-rose-800 dark:text-rose-200 rounded-lg text-xs font-semibold transition-colors shrink-0 shadow-sm"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {/* Failure Metadata Details */}
      <div className="pt-2 border-t border-rose-200/70 dark:border-rose-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2 text-rose-800 dark:text-rose-300">
          <Clock className="w-3.5 h-3.5 shrink-0" />
          <span>
            Last Failure: <strong>{lastFailureAt || 'Time unavailable'}</strong>
          </span>
        </div>

        {lastFailureMessage && (
          <div className="flex items-center gap-1.5 text-rose-700 dark:text-rose-300/90 truncate max-w-xl">
            <span className="font-semibold shrink-0">Reason:</span>
            <span className="truncate font-mono text-[11px] bg-white/60 dark:bg-black/20 px-2 py-0.5 rounded border border-rose-200/60 dark:border-rose-800/40">
              {lastFailureMessage}
            </span>
          </div>
        )}

        <div className="flex items-center gap-1.5 text-rose-700 dark:text-rose-400 shrink-0">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Failure Circuit Armed</span>
        </div>
      </div>
    </div>
  );
}
