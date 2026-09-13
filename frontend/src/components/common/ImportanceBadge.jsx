import React from 'react';

export default function ImportanceBadge({ score = 50, tier, isBreaking = false, className = '' }) {
  const currentTier = tier || (
    score >= 85 ? 'CRITICAL' :
    score >= 70 ? 'HIGH' :
    score >= 45 ? 'MEDIUM' : 'LOW'
  );

  if (isBreaking || currentTier === 'CRITICAL') {
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[11px] font-semibold tracking-wide bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-900/50 rounded-full ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-red-600 dark:bg-red-400 animate-pulse" />
        <span>{score} · Critical</span>
      </span>
    );
  }

  if (currentTier === 'HIGH') {
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[11px] font-medium tracking-wide bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900/50 rounded-full ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
        <span>{score} · High</span>
      </span>
    );
  }

  if (currentTier === 'MEDIUM') {
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 text-[11px] font-medium tracking-wide bg-slate-100/80 dark:bg-[#1E2028] text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800 rounded-full ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500/70" />
        <span>{score} · Medium</span>
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-medium tracking-wide bg-slate-50 dark:bg-[#16171B] text-slate-400 dark:text-slate-500 border border-slate-200/60 dark:border-slate-800/80 rounded-full ${className}`}>
      <span>{score} · Low</span>
    </span>
  );
}
