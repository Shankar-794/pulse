import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  History,
  Filter,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ChevronRight
} from 'lucide-react';
import { ApiService } from '../../services/api';
import RunDetailModal from './RunDetailModal';

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return '—';
  const num = Number(seconds);
  if (num < 1) return `${num.toFixed(2)}s`;
  if (num < 60) return `${num.toFixed(2)}s`;
  const mins = Math.floor(num / 60);
  const remSec = (num % 60).toFixed(0);
  return `${mins}m ${remSec}s`;
}

function formatTimestamp(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  } catch {
    return '—';
  }
}

export default function PipelineHistoryTable() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [triggerFilter, setTriggerFilter] = useState('all');

  // Modal State
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const isMountedRef = useRef(true);
  const inFlightRef = useRef(false);

  const fetchRuns = useCallback(async (isManual = false) => {
    if (inFlightRef.current && !isManual) return;
    inFlightRef.current = true;

    if (isManual) setIsRefreshing(true);

    try {
      const params = { limit: 25 };
      if (statusFilter !== 'all') params.status = statusFilter;
      if (triggerFilter !== 'all') params.triggerType = triggerFilter;

      const data = await ApiService.getPipelineRuns(params);
      if (!isMountedRef.current) return;

      setRuns(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      if (isMountedRef.current) {
        setError(err.message || 'Failed to load pipeline execution history');
      }
    } finally {
      inFlightRef.current = false;
      if (isMountedRef.current) {
        setLoading(false);
        if (isManual) setIsRefreshing(false);
      }
    }
  }, [statusFilter, triggerFilter]);

  // Fetch when filters change or initially
  useEffect(() => {
    isMountedRef.current = true;
    fetchRuns();

    // 15-second polling to update history while on page
    const intervalId = setInterval(() => {
      fetchRuns();
    }, 15000);

    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [fetchRuns]);

  const handleRowClick = (runId) => {
    if (!runId) return;
    setSelectedRunId(runId);
    setIsModalOpen(true);
  };

  const handleResetFilters = () => {
    setStatusFilter('all');
    setTriggerFilter('all');
  };

  const getStatusBadge = (status) => {
    const s = (status || 'unknown').toLowerCase();
    if (s === 'success') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 uppercase tracking-wider">
          <CheckCircle2 className="w-3 h-3 shrink-0" />
          <span>Success</span>
        </span>
      );
    }
    if (s === 'partial_failure') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800 uppercase tracking-wider">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          <span>Partial</span>
        </span>
      );
    }
    if (s === 'failed') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 uppercase tracking-wider">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          <span>Failed</span>
        </span>
      );
    }
    if (s === 'running') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 uppercase tracking-wider">
          <Loader2 className="w-3 h-3 animate-spin shrink-0" />
          <span>Running</span>
        </span>
      );
    }
    if (s === 'queued') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800 uppercase tracking-wider">
          <Clock className="w-3 h-3 shrink-0" />
          <span>Queued</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-slate-100 dark:bg-neutral-800 text-slate-600 dark:text-neutral-400 border border-news-border capitalize">
        {s}
      </span>
    );
  };

  const getTriggerBadge = (triggerType) => {
    const t = (triggerType || 'api').toLowerCase();
    let colorClass = 'bg-slate-100 dark:bg-neutral-800 text-slate-700 dark:text-neutral-300';
    if (t === 'scheduler') {
      colorClass = 'bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800';
    } else if (t === 'manual') {
      colorClass = 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800';
    } else if (t === 'api') {
      colorClass = 'bg-slate-100 dark:bg-neutral-800 text-slate-600 dark:text-neutral-400 border border-news-border';
    }
    return (
      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider ${colorClass}`}>
        {t}
      </span>
    );
  };

  return (
    <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card space-y-6 transition-colors">
      {/* Card Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-news-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200/60 dark:border-blue-900/40 flex items-center justify-center text-blue-600 dark:text-blue-400 shrink-0">
            <History className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold font-sans text-news-text-primary">
                Execution History
              </h2>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-neutral-800 text-slate-600 dark:text-neutral-300">
                {runs.length} runs
              </span>
            </div>
            <p className="text-xs text-news-text-secondary mt-0.5">
              Historical archive of automated and manual pipeline runs. Click any run to inspect complete stage metrics.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => fetchRuns(true)}
          disabled={isRefreshing}
          title="Refresh run history"
          aria-label="Refresh run history"
          className="self-start sm:self-auto inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-neutral-800 hover:bg-slate-200 dark:hover:bg-neutral-700 text-slate-700 dark:text-neutral-300 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-3.5 rounded-xl bg-slate-50/60 dark:bg-[#121316]/60 border border-news-border">
        {/* Status Filters */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-bold text-news-text-secondary mr-1 flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> Status:
          </span>
          {[
            { id: 'all', label: 'All' },
            { id: 'success', label: 'Success' },
            { id: 'partial_failure', label: 'Partial' },
            { id: 'failed', label: 'Failed' }
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setStatusFilter(tab.id)}
              className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors ${
                statusFilter === tab.id
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-white dark:bg-neutral-800 text-news-text-secondary hover:text-news-text-primary border border-news-border'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Trigger Filters */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs font-bold text-news-text-secondary mr-1">
            Trigger:
          </span>
          {[
            { id: 'all', label: 'All' },
            { id: 'scheduler', label: 'Scheduler' },
            { id: 'manual', label: 'Manual' },
            { id: 'api', label: 'API' }
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setTriggerFilter(tab.id)}
              className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-colors ${
                triggerFilter === tab.id
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-white dark:bg-neutral-800 text-news-text-secondary hover:text-news-text-primary border border-news-border'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => fetchRuns(true)}
            className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded font-semibold transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading ? (
        <div className="py-16 flex flex-col items-center justify-center gap-3 text-news-text-secondary">
          <Loader2 className="w-6 h-6 animate-spin text-blue-600 dark:text-blue-400" />
          <p className="text-xs">Loading execution archive...</p>
        </div>
      ) : runs.length === 0 ? (
        /* Empty State */
        <div className="py-12 px-4 rounded-xl border border-dashed border-news-border text-center space-y-3">
          <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-neutral-800 flex items-center justify-center mx-auto text-slate-400 dark:text-neutral-500">
            <History className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-news-text-primary">
              No pipeline runs found
            </h3>
            <p className="text-xs text-news-text-secondary mt-1 max-w-sm mx-auto">
              No execution history matches the selected filters. Clear your filters or trigger a new pipeline run.
            </p>
          </div>
          {(statusFilter !== 'all' || triggerFilter !== 'all') && (
            <button
              type="button"
              onClick={handleResetFilters}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition-colors inline-flex items-center gap-1.5"
            >
              Reset Filters
            </button>
          )}
        </div>
      ) : (
        /* Table of Execution Runs */
        <div className="overflow-x-auto rounded-xl border border-news-border">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-news-border bg-slate-50/80 dark:bg-[#121316]/80 text-[11px] font-bold uppercase tracking-wider text-news-text-secondary">
                <th scope="col" className="py-3 px-4">Run ID</th>
                <th scope="col" className="py-3 px-4">Trigger</th>
                <th scope="col" className="py-3 px-4">Status</th>
                <th scope="col" className="py-3 px-4">Duration</th>
                <th scope="col" className="py-3 px-4">Articles</th>
                <th scope="col" className="py-3 px-4">Stories</th>
                <th scope="col" className="py-3 px-4">Timestamp</th>
                <th scope="col" className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-news-border/60">
              {runs.map((run) => {
                const duration = formatDuration(run.duration_seconds ?? run.total_duration_seconds);
                const timestamp = formatTimestamp(run.completed_at || run.started_at);
                const totalArticles = run.total_articles ?? run.articles_processed;
                const newArticles = run.new_articles;
                const totalStories = run.total_stories ?? run.stories_created;
                const scoredStories = run.stories_scored ?? run.stories_importance_scored;

                return (
                  <tr
                    key={run.run_id}
                    onClick={() => handleRowClick(run.run_id)}
                    tabIndex={0}
                    role="button"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleRowClick(run.run_id);
                      }
                    }}
                    className="hover:bg-blue-50/40 dark:hover:bg-blue-950/20 cursor-pointer transition-colors focus:outline-none focus:bg-blue-50/60 dark:focus:bg-blue-950/30"
                  >
                    {/* Run ID */}
                    <td className="py-3.5 px-4 font-mono font-bold text-news-text-primary">
                      <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-neutral-800 border border-news-border text-[11px]">
                        {run.run_id}
                      </span>
                    </td>

                    {/* Trigger */}
                    <td className="py-3.5 px-4">
                      {getTriggerBadge(run.trigger_type)}
                    </td>

                    {/* Status */}
                    <td className="py-3.5 px-4">
                      {getStatusBadge(run.status)}
                    </td>

                    {/* Duration */}
                    <td className="py-3.5 px-4 font-mono text-news-text-primary font-medium">
                      {duration}
                    </td>

                    {/* Articles */}
                    <td className="py-3.5 px-4 text-news-text-secondary">
                      {totalArticles !== undefined && totalArticles !== null ? (
                        <span>
                          <strong className="text-news-text-primary">{totalArticles}</strong>
                          {newArticles !== undefined && newArticles !== null && (
                            <span className="text-emerald-600 dark:text-emerald-400 ml-1">
                              (+{newArticles})
                            </span>
                          )}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>

                    {/* Stories */}
                    <td className="py-3.5 px-4 text-news-text-secondary">
                      {totalStories !== undefined && totalStories !== null ? (
                        <span>
                          <strong className="text-news-text-primary">{totalStories}</strong>
                          {scoredStories !== undefined && scoredStories !== null && (
                            <span className="text-news-text-secondary ml-1">
                              ({scoredStories} scored)
                            </span>
                          )}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>

                    {/* Timestamp */}
                    <td className="py-3.5 px-4 text-news-text-secondary whitespace-nowrap">
                      {timestamp}
                    </td>

                    {/* Action */}
                    <td className="py-3.5 px-4 text-right">
                      <span className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 font-semibold hover:underline">
                        <span>Details</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal for Detailed Run Inspection */}
      <RunDetailModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        runId={selectedRunId}
      />
    </div>
  );
}
