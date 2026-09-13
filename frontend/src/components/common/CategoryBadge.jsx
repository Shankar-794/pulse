import React from 'react';

export default function CategoryBadge({ category, topic, className = '' }) {
  const cat = category || 'General';

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold tracking-wider uppercase text-blue-600 dark:text-blue-400 ${className}`}>
      <span>{cat}</span>
      {topic && topic.toLowerCase() !== cat.toLowerCase() && (
        <>
          <span className="text-slate-300 dark:text-neutral-600">/</span>
          <span className="text-slate-500 dark:text-neutral-400 font-normal lowercase tracking-normal">{topic}</span>
        </>
      )}
    </span>
  );
}
