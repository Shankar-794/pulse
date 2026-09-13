import React from 'react';
import { Search, X } from 'lucide-react';

export default function SearchBar({
  value = '',
  onChange,
  onClear,
  placeholder = 'Search articles, topics, and sources...',
  className = ''
}) {
  return (
    <div className={`relative flex items-center ${className}`}>
      <Search className="absolute left-3.5 w-4 h-4 text-slate-400 dark:text-neutral-500 pointer-events-none" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-white dark:bg-[#18191E] border border-news-border focus:border-blue-500 text-news-text-primary text-sm font-sans placeholder:text-slate-400 dark:placeholder:text-neutral-500 rounded-lg pl-10 pr-10 py-2 outline-none transition-colors shadow-sm"
      />
      {value && (
        <button
          type="button"
          onClick={onClear}
          className="absolute right-3.5 text-slate-400 hover:text-slate-600 dark:hover:text-neutral-200 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
