import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  CheckCircle2,
  AlertTriangle,
  Database,
  Layers,
  Brain,
  TrendingUp,
  Activity,
  Users,
  Check,
  Loader2
} from 'lucide-react';
import { ApiService } from '../../services/api';

/**
 * Seven canonical pipeline stages in execution sequence.
 */
const CANONICAL_STAGES = [
  {
    key: 'ingestion',
    label: 'Ingestion',
    subtitle: 'RSS Wire Feeds & Article Normalization',
    icon: Database,
  },
  {
    key: 'clustering',
    label: 'Semantic Clustering',
    subtitle: 'Hybrid Entity + Semantic Clustering Engine',
    icon: Layers,
  },
  {
    key: 'story_analysis',
    label: 'Grounded Story Analysis',
    subtitle: 'Evidence Attribution & Claim-Level Grounding',
    icon: Brain,
  },
  {
    key: 'global_importance',
    label: 'Global Importance Engine',
    subtitle: 'Deterministic 5-Factor Significance Scoring',
    icon: TrendingUp,
  },
  {
    key: 'story_evolution',
    label: 'Story Evolution & Breaking News',
    subtitle: 'Lifecycle Transitions & Reporting Velocity',
    icon: Activity,
  },
  {
    key: 'personal_relevance',
    label: 'Personal Relevance Ranking',
    subtitle: 'User Technical Interests & Scoring Calibration',
    icon: Users,
  },
  {
    key: 'feed_readiness',
    label: 'Feed Readiness',
    subtitle: 'Canonical Deduplication, Diversity & Cache Preparation',
    icon: CheckCircle2,
  },
];

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return null;
  const num = Number(seconds);
  if (num < 1) return `${num.toFixed(2)}s`;
  if (num < 60) return `${num.toFixed(2)}s`;
  const mins = Math.floor(num / 60);
  const remSec = (num % 60).toFixed(0);
  return `${mins}m ${remSec}s`;
}

function formatDateTime(isoString) {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit'
    });
  } catch {
    return '—';
  }
}

export default function RunDetailModal({ isOpen, onClose, runId }) {
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchRunDetail = useCallback(async () => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await ApiService.getPipelineRun(runId);
      setRun(data);
    } catch (err) {
      setError(err.message || `Failed to load execution detail for ${runId}`);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (isOpen && runId) {
      fetchRunDetail();
    }
  }, [isOpen, runId, fetchRunDetail]);

  // Handle Escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const rawStatus = (run?.status || 'unknown').toLowerCase();
  const isSuccess = rawStatus === 'success';
  const isPartialFailure = rawStatus === 'partial_failure';
  const isFailed = rawStatus === 'failed';
  const isRunning = rawStatus === 'running';

  const stagesMap = run?.stages || run?.stage_metrics || {};

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 md:p-6 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="bg-news-surface border border-news-border rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-5 sm:p-6 border-b border-news-border flex items-start justify-between gap-4 shrink-0 bg-slate-50/50 dark:bg-[#121316]/50">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h2 id="modal-title" className="text-lg sm:text-xl font-bold font-sans text-news-text-primary">
                Run Execution Profile
              </h2>
              {runId && (
                <span className="font-mono text-xs font-semibold px-2.5 py-0.5 rounded-md bg-slate-200/80 dark:bg-neutral-800 text-news-text-primary border border-news-border">
                  {runId}
                </span>
              )}
              {/* Status Pill */}
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider ${
                isSuccess
                  ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                  : isPartialFailure
                  ? 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
                  : isFailed
                  ? 'bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800'
                  : isRunning
                  ? 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800'
                  : 'bg-slate-100 dark:bg-neutral-800 text-slate-600 dark:text-neutral-400 border border-news-border'
              }`}>
                {rawStatus}
              </span>
            </div>
            <p className="text-xs text-news-text-secondary mt-1">
              Comprehensive telemetry record across all seven pipeline processing stages.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close run detail dialog"
            className="p-2 rounded-xl text-slate-500 hover:text-slate-800 dark:text-neutral-400 dark:hover:text-neutral-100 hover:bg-slate-100 dark:hover:bg-neutral-800 transition-colors shrink-0 border border-transparent hover:border-news-border"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body: Scrollable */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
          {loading ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 text-news-text-secondary">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600 dark:text-blue-400" />
              <p className="text-xs">Loading execution metrics for {runId}...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 space-y-3 text-xs">
              <div className="flex items-center gap-2 font-semibold">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>Failed to retrieve run details</span>
              </div>
              <p>{error}</p>
              <button
                type="button"
                onClick={fetchRunDetail}
                className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-medium transition-colors"
              >
                Retry
              </button>
            </div>
          ) : run ? (
            <>
              {/* Global Error Banner if run failed */}
              {run.error_message && (
                <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 flex items-start gap-2.5 text-xs">
                  <AlertTriangle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <span className="font-bold">Pipeline Error:</span>
                    <p className="font-mono text-[11px] leading-relaxed">{run.error_message}</p>
                  </div>
                </div>
              )}

              {/* Execution Summary Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl border border-news-border bg-slate-50/60 dark:bg-[#121316]/60 space-y-1">
                  <span className="text-[11px] font-semibold text-news-text-secondary uppercase tracking-wider block">
                    Trigger
                  </span>
                  <span className="text-xs font-bold text-news-text-primary capitalize">
                    {run.trigger_type || 'Unknown'}
                  </span>
                </div>

                <div className="p-3 rounded-xl border border-news-border bg-slate-50/60 dark:bg-[#121316]/60 space-y-1">
                  <span className="text-[11px] font-semibold text-news-text-secondary uppercase tracking-wider block">
                    Total Duration
                  </span>
                  <span className="text-xs font-bold text-news-text-primary">
                    {formatDuration(run.duration_seconds ?? run.total_duration_seconds) || '—'}
                  </span>
                </div>

                <div className="p-3 rounded-xl border border-news-border bg-slate-50/60 dark:bg-[#121316]/60 space-y-1">
                  <span className="text-[11px] font-semibold text-news-text-secondary uppercase tracking-wider block">
                    Started
                  </span>
                  <span className="text-xs font-medium text-news-text-primary truncate block" title={formatDateTime(run.started_at)}>
                    {formatDateTime(run.started_at)}
                  </span>
                </div>

                <div className="p-3 rounded-xl border border-news-border bg-slate-50/60 dark:bg-[#121316]/60 space-y-1">
                  <span className="text-[11px] font-semibold text-news-text-secondary uppercase tracking-wider block">
                    Completed
                  </span>
                  <span className="text-xs font-medium text-news-text-primary truncate block" title={formatDateTime(run.completed_at)}>
                    {formatDateTime(run.completed_at)}
                  </span>
                </div>
              </div>

              {/* Pipeline-Level Aggregates */}
              <div className="p-3.5 rounded-xl border border-news-border bg-slate-50/40 dark:bg-[#121316]/40 space-y-2">
                <span className="text-[11px] font-bold text-news-text-secondary uppercase tracking-wider block">
                  Processing Aggregates
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div>
                    <span className="text-news-text-secondary">Articles Processed: </span>
                    <strong className="text-news-text-primary">{run.total_articles ?? '—'}</strong>
                    {run.new_articles !== undefined && run.new_articles !== null && (
                      <span className="text-emerald-600 dark:text-emerald-400 text-[11px] ml-1">
                        (+{run.new_articles} new)
                      </span>
                    )}
                  </div>
                  <div>
                    <span className="text-news-text-secondary">Stories Created: </span>
                    <strong className="text-news-text-primary">{run.total_stories ?? run.stories_created ?? '—'}</strong>
                  </div>
                  <div>
                    <span className="text-news-text-secondary">Stories Analyzed: </span>
                    <strong className="text-news-text-primary">{run.stories_analyzed ?? '—'}</strong>
                  </div>
                  <div>
                    <span className="text-news-text-secondary">Feed Items Ready: </span>
                    <strong className="text-news-text-primary">{run.feed_items ?? run.feed_items_ready ?? '—'}</strong>
                  </div>
                </div>
              </div>

              {/* Seven Canonical Stages Section */}
              <div className="space-y-3 pt-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-news-text-primary uppercase tracking-wider">
                    Stage Execution Telemetry
                  </span>
                  <span className="text-[11px] text-news-text-secondary">
                    7 Sequential Stages
                  </span>
                </div>

                <div className="space-y-2.5">
                  {CANONICAL_STAGES.map((stage, idx) => {
                    const stageData = stagesMap[stage.key] || {};
                    const stageStatus = (stageData.status || (isSuccess ? 'success' : 'pending')).toLowerCase();
                    const StageIcon = stage.icon;
                    const duration = formatDuration(stageData.duration_seconds);

                    const isStageSuccess = stageStatus === 'success';
                    const isStageFailed = stageStatus === 'failed';
                    const isStageSkipped = stageStatus === 'skipped';
                    const isStageRunning = stageStatus === 'running';

                    // Extract metrics safely from stageData
                    const metricEntries = Object.entries(stageData).filter(
                      ([k]) => !['status', 'duration_seconds', 'error', 'error_message'].includes(k)
                    );

                    return (
                      <div
                        key={stage.key}
                        className={`p-3.5 rounded-xl border transition-all ${
                          isStageRunning
                            ? 'bg-blue-50/50 dark:bg-blue-950/20 border-blue-400 dark:border-blue-700'
                            : isStageFailed
                            ? 'bg-rose-50/40 dark:bg-rose-950/20 border-rose-300 dark:border-rose-800'
                            : 'bg-slate-50/60 dark:bg-[#121316]/60 border-news-border'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold ${
                              isStageRunning
                                ? 'bg-blue-600 text-white'
                                : isStageSuccess
                                ? 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800'
                                : isStageFailed
                                ? 'bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-800'
                                : 'bg-slate-100 dark:bg-neutral-800 text-slate-500 dark:text-neutral-400'
                            }`}>
                              {isStageRunning ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : isStageSuccess ? (
                                <Check className="w-3.5 h-3.5 stroke-[3]" />
                              ) : isStageFailed ? (
                                <AlertTriangle className="w-3.5 h-3.5" />
                              ) : (
                                <StageIcon className="w-3.5 h-3.5" />
                              )}
                            </div>

                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-xs font-bold text-news-text-primary">
                                  {idx + 1}. {stage.label}
                                </span>
                                {duration && (
                                  <span className="text-[11px] font-mono font-medium text-news-text-secondary">
                                    ({duration})
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] text-news-text-secondary truncate">
                                {stage.subtitle}
                              </p>
                            </div>
                          </div>

                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider shrink-0 ${
                            isStageSuccess
                              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800'
                              : isStageFailed
                              ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-800'
                              : isStageRunning
                              ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800'
                              : isStageSkipped
                              ? 'bg-slate-100 dark:bg-neutral-800 text-slate-500 dark:text-neutral-400 border border-news-border'
                              : 'bg-slate-100 dark:bg-neutral-800 text-slate-400 dark:text-neutral-500 border border-news-border'
                          }`}>
                            {stageStatus}
                          </span>
                        </div>

                        {/* Error info if stage failed */}
                        {(stageData.error || stageData.error_message) && (
                          <div className="mt-2 p-2 rounded bg-rose-100/70 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 text-[11px] font-mono">
                            {stageData.error || stageData.error_message}
                          </div>
                        )}

                        {/* Metrics chips */}
                        {metricEntries.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-news-border/60 flex items-center gap-1.5 flex-wrap">
                            {metricEntries.map(([k, v]) => {
                              if (v === null || v === undefined) return null;
                              const displayVal = typeof v === 'object' ? JSON.stringify(v) : String(v);
                              const formattedKey = k.replace(/_/g, ' ');
                              return (
                                <span
                                  key={k}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-slate-100 dark:bg-neutral-800/80 border border-slate-200 dark:border-neutral-700 text-news-text-secondary"
                                >
                                  <span className="capitalize">{formattedKey}:</span>
                                  <strong className="font-semibold text-news-text-primary">{displayVal}</strong>
                                </span>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Modal Footer */}
        <div className="p-4 px-6 border-t border-news-border flex items-center justify-between shrink-0 bg-slate-50/50 dark:bg-[#121316]/50 text-xs text-news-text-secondary">
          <span>Pulse Engine · Pipeline Execution Archive</span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-slate-100 dark:bg-neutral-800 hover:bg-slate-200 dark:hover:bg-neutral-700 text-news-text-primary font-semibold rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
