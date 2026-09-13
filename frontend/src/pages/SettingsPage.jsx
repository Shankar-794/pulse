import React, { useState, useEffect } from 'react';
import { Sliders, Save, CheckCircle2, RotateCcw, Shield, Bell, Eye, Palette, Sun, Moon } from 'lucide-react';
import { ApiService } from '../services/api';
import { DEFAULT_USER_PREFERENCES } from '../data/mockNewsData';
import { useTheme } from '../hooks/useTheme';

const ALL_INTERESTS = [
  'AI',
  'Software Engineering',
  'Cybersecurity',
  'Semiconductors',
  'Space',
  'Science',
  'Cloud Infrastructure',
  'Robotics',
  'Business',
  'World News',
  'Macroeconomics'
];

const AVAILABLE_SOURCES = [
  'Hacker News',
  'Ars Technica',
  'Krebs on Security',
  'BleepingComputer',
  'MIT News Research',
  'NASA Breaking News',
  'BBC Technology',
  'The Verge',
  'Nature Energy',
  'Quanta Magazine',
  'ACM Queue'
];

export default function SettingsPage() {
  const { theme, toggleTheme, isDark } = useTheme();
  const [preferences, setPreferences] = useState(DEFAULT_USER_PREFERENCES);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    ApiService.getPreferences().then((prefs) => {
      if (prefs) setPreferences(prefs);
    });
  }, []);

  const handleInterestToggle = (interest) => {
    setPreferences((prev) => {
      const set = new Set(prev.interests);
      if (set.has(interest)) {
        set.delete(interest);
      } else {
        set.add(interest);
      }
      return { ...prev, interests: Array.from(set) };
    });
  };

  const handleSourceToggle = (source) => {
    setPreferences((prev) => {
      const set = new Set(prev.preferred_sources);
      if (set.has(source)) {
        set.delete(source);
      } else {
        set.add(source);
      }
      return { ...prev, preferred_sources: Array.from(set) };
    });
  };

  const handleSave = async (e) => {
    e.preventDefault();
    await ApiService.updatePreferences(preferences);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 2500);
  };

  const handleReset = () => {
    if (window.confirm('Reset all preferences to defaults?')) {
      setPreferences(DEFAULT_USER_PREFERENCES);
      ApiService.updatePreferences(DEFAULT_USER_PREFERENCES);
    }
  };

  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="bg-news-surface border border-news-border rounded-xl p-6 sm:p-7 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <Sliders className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <h1 className="text-2xl sm:text-3xl font-bold font-sans text-news-text-primary">
              Feed Preferences
            </h1>
          </div>
          <p className="text-sm text-news-text-secondary">
            Personalize topic relevance, notification sensitivity, and appearance.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={handleReset}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-neutral-800 hover:bg-slate-200 dark:hover:bg-neutral-700 text-xs font-medium text-slate-600 dark:text-neutral-300 rounded-lg transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset</span>
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition-colors shadow-sm"
          >
            {savedSuccess ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            <span>{savedSuccess ? 'Saved' : 'Save Preferences'}</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Section 1: Appearance Theme */}
        <div className="bg-news-surface border border-news-border rounded-xl p-6 shadow-card space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-news-border">
            <Palette className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <h2 className="text-sm font-bold text-news-text-primary">
              Appearance & Theme
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <button
              type="button"
              onClick={() => {
                if (isDark) toggleTheme();
              }}
              className={`p-4 rounded-xl border text-left flex items-center gap-3.5 transition-all ${
                !isDark
                  ? 'bg-blue-50/70 border-blue-500 shadow-sm'
                  : 'bg-slate-50 dark:bg-[#121316] border-news-border hover:border-slate-400'
              }`}
            >
              <div className="w-9 h-9 rounded-lg bg-amber-100 flex items-center justify-center text-amber-600 shrink-0">
                <Sun className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-news-text-primary">Light Mode</div>
                <div className="text-xs text-news-text-secondary">Clean editorial light canvas</div>
              </div>
            </button>

            <button
              type="button"
              onClick={() => {
                if (!isDark) toggleTheme();
              }}
              className={`p-4 rounded-xl border text-left flex items-center gap-3.5 transition-all ${
                isDark
                  ? 'bg-blue-950/40 border-blue-500 shadow-sm'
                  : 'bg-slate-50 dark:bg-[#121316] border-news-border hover:border-slate-400'
              }`}
            >
              <div className="w-9 h-9 rounded-lg bg-neutral-800 flex items-center justify-center text-blue-400 shrink-0">
                <Moon className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-news-text-primary">Dark Mode</div>
                <div className="text-xs text-news-text-secondary">Soft charcoal dark theme</div>
              </div>
            </button>
          </div>
        </div>

        {/* Section 2: Technical Interests */}
        <div className="bg-news-surface border border-news-border rounded-xl p-6 shadow-card space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-news-border">
            <Shield className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <h2 className="text-sm font-bold text-news-text-primary">
              Personal Interests
            </h2>
          </div>
          <p className="text-xs text-news-text-secondary">
            Select the domains you follow. Stories in these areas will be prioritized in your "Important For You" feed.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 pt-1">
            {ALL_INTERESTS.map((interest) => {
              const isSelected = preferences.interests?.includes(interest);
              return (
                <button
                  type="button"
                  key={interest}
                  onClick={() => handleInterestToggle(interest)}
                  className={`p-3 rounded-lg text-xs font-medium text-left border transition-all ${
                    isSelected
                      ? 'bg-blue-50 dark:bg-blue-950/40 border-blue-300 dark:border-blue-800 text-blue-700 dark:text-blue-300'
                      : 'bg-slate-50 dark:bg-[#121316] border-news-border text-news-text-secondary hover:text-news-text-primary hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span>{interest}</span>
                    {isSelected && <span className="text-blue-600 dark:text-blue-400 font-bold">✓</span>}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Section 3: Feed Sensitivity */}
        <div className="bg-news-surface border border-news-border rounded-xl p-6 shadow-card space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-news-border">
            <Bell className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <h2 className="text-sm font-bold text-news-text-primary">
              Sensitivity & Filters
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-1">
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-news-text-primary">
                Breaking News Threshold
              </label>
              <select
                value={preferences.breaking_sensitivity}
                onChange={(e) => setPreferences({ ...preferences, breaking_sensitivity: e.target.value })}
                className="w-full bg-slate-50 dark:bg-[#121316] border border-news-border text-news-text-primary text-xs rounded-lg px-3 py-2 outline-none focus:border-blue-500"
              >
                <option value="all">High (All developing breaking stories)</option>
                <option value="standard">Standard (Major verified stories only)</option>
                <option value="critical_only">Critical Only (Highest severity events)</option>
              </select>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <label className="font-semibold text-news-text-primary">
                  Minimum Importance Score
                </label>
                <span className="font-bold text-blue-600 dark:text-blue-400">
                  {preferences.importance_threshold || 50}/100
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="90"
                step="5"
                value={preferences.importance_threshold || 50}
                onChange={(e) => setPreferences({ ...preferences, importance_threshold: parseInt(e.target.value, 10) })}
                className="w-full accent-blue-600 cursor-pointer"
              />
              <div className="flex justify-between text-[11px] text-news-text-secondary">
                <span>0 (All stories)</span>
                <span>50 (Standard)</span>
                <span>90 (Top only)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Section 4: Preferred News Wires */}
        <div className="bg-news-surface border border-news-border rounded-xl p-6 shadow-card space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-news-border">
            <Eye className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            <h2 className="text-sm font-bold text-news-text-primary">
              Preferred News Outlets
            </h2>
          </div>
          <p className="text-xs text-news-text-secondary">
            Favorite outlets you trust. These sources receive higher priority in your feed.
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1">
            {AVAILABLE_SOURCES.map((source) => {
              const isSelected = preferences.preferred_sources?.includes(source);
              return (
                <button
                  type="button"
                  key={source}
                  onClick={() => handleSourceToggle(source)}
                  className={`p-2.5 rounded-lg text-xs font-medium text-left border transition-all flex items-center justify-between ${
                    isSelected
                      ? 'bg-blue-50 dark:bg-blue-950/40 border-blue-300 dark:border-blue-800 text-blue-700 dark:text-blue-300'
                      : 'bg-slate-50 dark:bg-[#121316] border-news-border text-news-text-secondary hover:text-news-text-primary hover:border-slate-300'
                  }`}
                >
                  <span className="truncate">{source}</span>
                  <span className="text-xs ml-1">{isSelected ? '★' : '☆'}</span>
                </button>
              );
            })}
          </div>
        </div>
      </form>
    </div>
  );
}
