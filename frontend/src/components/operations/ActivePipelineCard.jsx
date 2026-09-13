import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Activity,
  Play,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  RefreshCw,
  Database,
  Layers,
  Brain,
  TrendingUp,
  Users,
  Check,
  Sliders
} from 'lucide-react';
import { ApiService } from '../../services/api';

/**
 * Seven canonical pipeline stages mapped directly to backend keys.
 */
const PIPELINE_STAGES = [
  {
    key: 'ingestion',
    label: 'Ingestion',
    subtitle: 'Fetch and normalize RSS wire articles',
    icon: Database,
  },
  {
    key: 'clustering',
    label: 'Semantic Clustering',
    subtitle: 'Entity-enhanced semantic cluster creation',
    icon: Layers,
  },
  {
    key: 'story_analysis',
    label: 'Grounded Story Analysis',
    subtitle: 'Evidence attribution and claim grounding',
    icon: Brain,
  },
  {
    key: 'global_importance',
    label: 'Global Importance Engine',
    subtitle: '5-factor objective significance scoring',
    icon: TrendingUp,
  },
  {
    key: 'story_evolution',
    label: 'Story Evolution & Breaking News',
    subtitle: 'Lifecycle updates and breaking velocity detection',
    icon: Activity,
  },
  {
    key: 'personal_relevance',
    label: 'Personal Relevance Ranking',
    subtitle: 'Interest profiling and topic relevance calibration',
    icon: Users,
  },
  {
    key: 'feed_readiness',
    label: 'Feed Readiness',
    subtitle: 'Diversity control, deduplication, and cache preparation',
    icon: CheckCircle2,
  },
];

/**
 * Format duration seconds cleanly (e.g. "0.96s", "4.18s", "1m 12s").
 */
function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return null;
  const num = Number(seconds);
  if (num < 1) {
    return `${num.toFixed(2)}s`;
  }
  if (num < 60) {
    return `${num.toFixed(2)}s`;
  }
  const mins = Math.floor(num / 60);
  const remSec = (num % 60).toFixed(0);
  return `${mins}m ${remSec}s`;
}

/**
 * Extract safe, readable metrics for each stage without inventing field names.
 */
function getStageMetrics(stageKey, data) {
  if (!data || typeof data !== 'object') return [];
  const metrics = [];

  switch (stageKey) {
    case 'ingestion':
      if (data.articles_seen !== undefined) metrics.push({ label: 'Fetched', value: data.articles_seen });
      if (data.new_articles !== undefined) metrics.push({ label: 'New', value: data.new_articles });
      if (data.duplicates !== undefined) metrics.push({ label: 'Duplicates', value: data.duplicates });
      if (data.sources_checked !== undefined) metrics.push({ label: 'Sources', value: data.sources_checked });
      if (data.failed_sources !== undefined && data.failed_sources > 0) {
        metrics.push({ label: 'Failed Sources', value: data.failed_sources, alert: true });
      }
      break;

    case 'clustering':
      if (data.articles_processed !== undefined) metrics.push({ label: 'Processed', value: data.articles_processed });
      if (data.stories_created !== undefined) metrics.push({ label: 'Stories', value: data.stories_created });
      if (data.largest_cluster_size !== undefined) metrics.push({ label: 'Max Cluster', value: data.largest_cluster_size });
      break;

    case 'story_analysis':
      if (data.stories_evaluated !== undefined) metrics.push({ label: 'Evaluated', value: data.stories_evaluated });
      if (data.analyzed_count !== undefined) metrics.push({ label: 'Analyzed', value: data.analyzed_count });
      if (data.failed_count !== undefined && data.failed_count > 0) {
        metrics.push({ label: 'Failed', value: data.failed_count, alert: true });
      }
      break;

    case 'global_importance':
      if (data.scored_count !== undefined) metrics.push({ label: 'Scored', value: data.scored_count });
      if (data.version) metrics.push({ label: 'Model', value: data.version });
      break;

    case 'story_evolution':
      if (data.stories_evolved !== undefined) metrics.push({ label: 'Evolved', value: data.stories_evolved });
      if (data.breaking_stories !== undefined) metrics.push({ label: 'Breaking', value: data.breaking_stories });
      break;

    case 'personal_relevance':
      if (data.stories_evaluated !== undefined) metrics.push({ label: 'Stories', value: data.stories_evaluated });
      if (data.average_relevance !== undefined) metrics.push({ label: 'Avg Score', value: `${data.average_relevance}%` });
      break;

    case 'feed_readiness':
      if (data.feed_items_count !== undefined) metrics.push({ label: 'Feed Ready', value: data.feed_items_count });
      if (Array.isArray(data.categories_represented)) {
        metrics.push({ label: 'Categories', value: data.categories_represented.length });
      }
      break;

    default:
      break;
  }

  return metrics;
}

export default function ActivePipelineCard() {
  const [pipelineData, setPipelineData] = useState(null);
  const [_loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isDispatching, setIsDispatching] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Manual Trigger Parameters
  const [showConfig, setShowConfig] = useState(false);
  const [skipIngestion, setSkipIngestion] = useState(false);
  const [timeWindowHours, setTimeWindowHours] = useState('24');

  const isMountedRef = useRef(true);
  const inFlightRef = useRef(false);

  // Fetch status from API
  const fetchStatus = useCallback(async (isManual = false) => {
    if (inFlightRef.current && !isManual) return;
    inFlightRef.current = true;

    if (isManual) {
      setIsRefreshing(true);
    }

    try {
      const res = await ApiService.getPipelineStatus();
      if (!isMountedRef.current) return;

      if (res && res.status !== 'error') {
        setPipelineData(res);
        setErrorMessage(null);
      } else if (res?.error) {
        setErrorMessage(res.error);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setErrorMessage(err.message || 'Failed to fetch pipeline status');
      }
    } finally {
      inFlightRef.current = false;
      if (isMountedRef.current) {
        setLoading(false);
        if (isManual) setIsRefreshing(false);
      }
    }
  }, []);

  // Determine current pipeline run status
  const currentRun = pipelineData?.pipeline || pipelineData;
  const rawStatus = (pipelineData?.status || currentRun?.status || 'idle').toLowerCase();
  const isNeverRun = rawStatus === 'never_run' || !currentRun || !currentRun.run_id;
  const isQueued = rawStatus === 'queued';
  const isRunning = rawStatus === 'running';
  const isSuccess = rawStatus === 'success';
  const isPartialFailure = rawStatus === 'partial_failure';
  const isFailed = rawStatus === 'failed';
  const isActive = isQueued || isRunning;

  // Polling setup: 2.5s high-frequency when active, 15s heartbeat when idle
  useEffect(() => {
    isMountedRef.current = true;
    fetchStatus();

    const intervalMs = isActive ? 2500 : 15000;
    const intervalId = setInterval(() => {
      fetchStatus();
    }, intervalMs);

    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [fetchStatus, isActive]);

  // Auto-clear success message after 4s
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => {
        if (isMountedRef.current) setSuccessMessage(null);
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Manual execution dispatch handler
  const handleTriggerRun = async () => {
    if (isActive || isDispatching) return;

    setIsDispatching(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const parsedWindow = parseInt(timeWindowHours, 10);
    const windowHours = isNaN(parsedWindow) || parsedWindow < 1 ? 24 : parsedWindow;

    try {
      const res = await ApiService.runPipeline({
        skipIngestion,
        timeWindowHours: windowHours
      });

      if (!isMountedRef.current) return;

      if (res?.status === 'accepted') {
        setSuccessMessage(`Pipeline execution accepted (${res.run_id}). Live monitoring active.`);
        // Immediately refresh status to enter high-frequency tracking
        await fetchStatus(true);
      } else {
        await fetchStatus(true);
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      if (err.status === 409 || err.message?.includes('409') || err.message?.includes('already in progress')) {
        setErrorMessage('Another pipeline run is already active in the background.');
        // Refresh to get the active run data
        fetchStatus(true);
      } else {
        setErrorMessage(err.message || 'Failed to dispatch pipeline execution');
      }
    } finally {
      if (isMountedRef.current) {
        setIsDispatching(false);
      }
    }
  };

  // Status badge styling helper
  const getStatusBadge = () => {
    if (isNeverRun) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-100 dark:bg-neutral-800 border border-slate-200 dark:border-neutral-700 text-slate-600 dark:text-neutral-400 rounded-full text-xs font-semibold uppercase tracking-wider">
          <span className="w-2 h-2 rounded-full bg-slate-400 shrink-0" />
          <span>Idle / No Active Run</span>
        </span>
      );
    }
    if (isQueued) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-amber-700 dark:text-amber-400 rounded-full text-xs font-semibold uppercase tracking-wider">
          <Clock className="w-3.5 h-3.5 shrink-0" />
          <span>Queued</span>
        </span>
      );
    }
    if (isRunning) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-blue-50 dark:bg-blue-950/40 border border-blue-300 dark:border-blue-800 text-blue-700 dark:text-blue-400 rounded-full text-xs font-semibold uppercase tracking-wider">
          <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
          <span>Running</span>
        </span>
      );
    }
    if (isSuccess) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400 rounded-full text-xs font-semibold uppercase tracking-wider">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
          <span>Success</span>
        </span>
      );
    }
    if (isPartialFailure) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-amber-700 dark:text-amber-400 rounded-full text-xs font-semibold uppercase tracking-wider">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>Partial Failure</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-400 rounded-full text-xs font-semibold uppercase tracking-wider">
        <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
        <span>Failed</span>
      </span>
    );
  };

  // Headline message for the overview banner
  const getBannerHeadline = () => {
    if (isNeverRun) return 'No pipeline execution recorded yet';
    if (isQueued) return 'Pipeline execution queued in background';
    if (isRunning) return 'Pipeline execution in progress';
    if (isSuccess) return 'Pipeline completed successfully';
    if (isPartialFailure) return 'Pipeline completed with partial failures';
    if (isFailed) return 'Pipeline execution failed';
    return 'Pipeline status available';
  };

  // Stage states map
  const stagesMap = currentRun?.stages || currentRun?.stage_metrics || {};

  // Timing metrics
  const runDuration = currentRun?.duration_seconds ?? currentRun?.total_duration_seconds;
  const startedAt = currentRun?.started_at ? new Date(currentRun.started_at) : null;
  const completedAt = currentRun?.completed_at ? new Date(currentRun.completed_at) : null;

  return (
    <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card space-y-6 transition-colors">
      {/* Card Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-news-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200/60 dark:border-blue-900/40 flex items-center justify-center text-blue-600 dark:text-blue-400 shrink-0">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h2 className="text-lg font-bold font-sans text-news-text-primary">
                Active Pipeline
              </h2>
              {getStatusBadge()}
            </div>
            <p className="text-xs text-news-text-secondary mt-0.5">
              Live seven-stage execution telemetry
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            type="button"
            onClick={() => fetchStatus(true)}
            disabled={isRefreshing}
            title="Refresh pipeline status"
            aria-label="Refresh pipeline status"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-neutral-800 hover:bg-slate-200 dark:hover:bg-neutral-700 text-slate-700 dark:text-neutral-300 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
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
            className="text-rose-600 dark:text-rose-400 hover:underline font-semibold shrink-0"
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

      {/* Overall Status Banner */}
      <div className={`p-4 rounded-xl border transition-colors ${
        isActive
          ? 'bg-blue-50/70 dark:bg-blue-950/20 border-blue-200 dark:border-blue-900/50'
          : isSuccess
          ? 'bg-emerald-50/60 dark:bg-emerald-950/20 border-emerald-200/70 dark:border-emerald-900/40'
          : isFailed || isPartialFailure
          ? 'bg-amber-50/70 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/40'
          : 'bg-slate-50/60 dark:bg-[#121316]/60 border-news-border'
      }`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              {isActive ? (
                <Loader2 className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin shrink-0" />
              ) : isSuccess ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
              ) : isFailed || isPartialFailure ? (
                <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
              ) : (
                <Clock className="w-4 h-4 text-slate-400 shrink-0" />
              )}
              <span className="text-sm font-bold text-news-text-primary">
                {getBannerHeadline()}
              </span>
            </div>

            <div className="flex items-center gap-3 text-xs text-news-text-secondary flex-wrap">
              {currentRun?.run_id && (
                <span className="font-mono bg-white/80 dark:bg-black/30 px-2 py-0.5 rounded border border-news-border text-[11px] font-semibold text-news-text-primary">
                  {currentRun.run_id}
                </span>
              )}
              {currentRun?.trigger_type && (
                <span className="capitalize">
                  Trigger: <strong className="text-news-text-primary">{currentRun.trigger_type}</strong>
                </span>
              )}
              {startedAt && (
                <span>
                  Started: <strong className="text-news-text-primary">{startedAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' })}</strong>
                </span>
              )}
              {completedAt && (
                <span>
                  Completed: <strong className="text-news-text-primary">{completedAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' })}</strong>
                </span>
              )}
              {runDuration !== undefined && runDuration !== null && (
                <span>
                  Total Duration: <strong className="text-news-text-primary">{formatDuration(runDuration)}</strong>
                </span>
              )}
            </div>
          </div>

          {/* Prominent Run Pipeline Trigger Button */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={handleTriggerRun}
              disabled={isActive || isDispatching}
              aria-label="Trigger manual pipeline execution"
              className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition-colors shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isDispatching ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Starting Pipeline...</span>
                </>
              ) : isActive ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Pipeline In Progress</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>Run Pipeline Now</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => setShowConfig(!showConfig)}
              title="Execution parameters"
              aria-label="Toggle execution parameters"
              className="p-2 text-slate-600 dark:text-neutral-400 hover:text-slate-900 dark:hover:text-neutral-100 hover:bg-slate-100 dark:hover:bg-neutral-800 rounded-lg transition-colors border border-news-border"
            >
              <Sliders className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Optional Pipeline Parameters Drawer */}
        {showConfig && (
          <div className="mt-3 pt-3 border-t border-news-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs">
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={skipIngestion}
                  onChange={(e) => setSkipIngestion(e.target.checked)}
                  disabled={isActive || isDispatching}
                  className="rounded border-news-border text-blue-600 focus:ring-blue-500"
                />
                <span className="font-medium text-news-text-primary">Skip Ingestion</span>
                <span className="text-[11px] text-news-text-secondary">(reuse existing DB articles)</span>
              </label>
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="timeWindowInput" className="font-medium text-news-text-primary">
                Time Window:
              </label>
              <input
                id="timeWindowInput"
                type="number"
                min="1"
                max="168"
                value={timeWindowHours}
                onChange={(e) => setTimeWindowHours(e.target.value)}
                disabled={isActive || isDispatching}
                className="w-16 px-2 py-1 bg-slate-50 dark:bg-[#121316] border border-news-border text-news-text-primary rounded text-xs outline-none focus:border-blue-500"
              />
              <span className="text-news-text-secondary">hours</span>
            </div>
          </div>
        )}
      </div>

      {/* Seven-Stage Stepper / Timeline List */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between pb-1">
          <span className="text-xs font-bold text-news-text-primary uppercase tracking-wider">
            Pipeline Execution Stages
          </span>
          <span className="text-[11px] text-news-text-secondary">
            7 Sequential Intelligence Stages
          </span>
        </div>

        <div className="space-y-2.5">
          {PIPELINE_STAGES.map((stage) => {
            const stageData = stagesMap[stage.key] || {};
            const stageStatus = (stageData.status || (isNeverRun ? 'pending' : (isActive ? 'pending' : 'pending'))).toLowerCase();
            const StageIcon = stage.icon;
            const metrics = getStageMetrics(stage.key, stageData);
            const duration = formatDuration(stageData.duration_seconds);

            // Derive node visual treatment
            const isStageRunning = stageStatus === 'running';
            const isStageSuccess = stageStatus === 'success';
            const isStageFailed = stageStatus === 'failed';
            const isStageSkipped = stageStatus === 'skipped';

            return (
              <div
                key={stage.key}
                className={`p-3.5 sm:p-4 rounded-xl border transition-all ${
                  isStageRunning
                    ? 'bg-blue-50/50 dark:bg-blue-950/20 border-blue-400 dark:border-blue-700 shadow-sm'
                    : isStageFailed
                    ? 'bg-rose-50/40 dark:bg-rose-950/20 border-rose-300 dark:border-rose-800'
                    : 'bg-slate-50/60 dark:bg-[#121316]/60 border-news-border'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                  {/* Left: Icon, Number, Title & Subtitle */}
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold transition-colors ${
                      isStageRunning
                        ? 'bg-blue-600 text-white'
                        : isStageSuccess
                        ? 'bg-emerald-100 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800'
                        : isStageFailed
                        ? 'bg-rose-100 dark:bg-rose-950/50 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-800'
                        : isStageSkipped
                        ? 'bg-slate-200 dark:bg-neutral-800 text-slate-500 dark:text-neutral-400'
                        : 'bg-slate-100 dark:bg-neutral-800 text-slate-500 dark:text-neutral-400'
                    }`}>
                      {isStageRunning ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : isStageSuccess ? (
                        <Check className="w-4 h-4 stroke-[3]" />
                      ) : isStageFailed ? (
                        <AlertTriangle className="w-4 h-4" />
                      ) : (
                        <StageIcon className="w-4 h-4" />
                      )}
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-news-text-primary">
                          {stage.label}
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

                  {/* Right: State Label Badge & Metrics */}
                  <div className="flex items-center gap-2 flex-wrap sm:justify-end shrink-0 pl-11 sm:pl-0">
                    {/* Status Label */}
                    <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wider ${
                      isStageRunning
                        ? 'bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-800'
                        : isStageSuccess
                        ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800'
                        : isStageFailed
                        ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-800'
                        : isStageSkipped
                        ? 'bg-slate-100 dark:bg-neutral-800 text-slate-500 dark:text-neutral-400 border border-slate-200 dark:border-neutral-700'
                        : 'bg-slate-100 dark:bg-neutral-800/80 text-slate-400 dark:text-neutral-500 border border-slate-200/60 dark:border-neutral-700/60'
                    }`}>
                      {isStageRunning ? 'Running' : isStageSuccess ? 'Completed' : isStageFailed ? 'Failed' : isStageSkipped ? 'Skipped' : 'Pending'}
                    </span>
                  </div>
                </div>

                {/* Stage Metrics Chips */}
                {metrics.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-news-border/60 flex items-center gap-1.5 flex-wrap pl-11 sm:pl-11">
                    {metrics.map((m, mIdx) => (
                      <span
                        key={mIdx}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] border font-medium ${
                          m.alert
                            ? 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-400'
                            : 'bg-slate-100 dark:bg-neutral-800/80 border-slate-200 dark:border-neutral-700 text-news-text-secondary'
                        }`}
                      >
                        <span>{m.label}:</span>
                        <strong className="font-semibold text-news-text-primary">{m.value}</strong>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
