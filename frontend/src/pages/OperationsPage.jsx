import React from 'react';
import {
  Activity,
  Radio,
  Cpu
} from 'lucide-react';
import SchedulerControlCard from '../components/operations/SchedulerControlCard';
import ActivePipelineCard from '../components/operations/ActivePipelineCard';
import FailureMetricsBanner from '../components/operations/FailureMetricsBanner';
import PipelineHistoryTable from '../components/operations/PipelineHistoryTable';

export default function OperationsPage() {
  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Page Header */}
      <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Activity className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <h1 className="text-2xl sm:text-3xl font-bold font-sans text-news-text-primary">
              System Operations
            </h1>
          </div>
          <p className="text-sm text-news-text-secondary">
            Centralized monitoring, scheduler controls, live telemetry, and execution history for the 7-stage news intelligence pipeline.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/50 rounded-full text-xs font-semibold text-emerald-700 dark:text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
            <span>Operational</span>
          </div>
        </div>
      </div>

      {/* Scheduler Control Card (Phase 8.3 Step 2) */}
      <SchedulerControlCard />

      {/* Active Pipeline Card (Phase 8.3 Step 3) */}
      <ActivePipelineCard />

      {/* Failure Telemetry Banner (Phase 8.3 Step 4) */}
      <FailureMetricsBanner />

      {/* Pipeline Execution History Table (Phase 8.3 Step 5) */}
      <PipelineHistoryTable />

      {/* Runtime Environment Footer */}
      <div className="pt-4 border-t border-news-border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs text-news-text-secondary">
        <div className="flex items-center gap-2">
          <Cpu className="w-3.5 h-3.5 text-slate-400 dark:text-neutral-500" />
          <span>Engine: FastAPI + APScheduler + SQLite</span>
        </div>
        <div className="flex items-center gap-2">
          <Radio className="w-3.5 h-3.5 text-emerald-500" />
          <span>Telemetry endpoint: /api/pipeline/status</span>
        </div>
      </div>
    </div>
  );
}
