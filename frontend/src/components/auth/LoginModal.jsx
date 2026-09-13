import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { X, Newspaper, AlertCircle } from 'lucide-react';

export const LoginModal = () => {
  const {
    isLoginModalOpen,
    closeLoginModal,
    authConfig,
    loginWithGoogle,
    devLogin,
  } = useAuth();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [devEmail, setDevEmail] = useState('');

  // Development authentication is strictly environment-gated and never rendered in production
  const isDevAuthAvailable = !import.meta.env.PROD && !!authConfig?.dev_login_enabled;

  if (!isLoginModalOpen) return null;

  const handleGoogleSignIn = async () => {
    try {
      setLoading(true);
      setError(null);
      await loginWithGoogle();
    } catch {
      setError('Unable to initialize Google authentication. Please try again.');
      setLoading(false);
    }
  };

  const handleDevSignIn = async (e) => {
    e?.preventDefault();
    if (!devEmail.trim()) {
      setError('Please enter an email address.');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await devLogin({ email: devEmail.trim(), name: devEmail.trim().split('@')[0] });
    } catch {
      setError('Sign-in failed. Please try again.');
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in"
      onClick={closeLoginModal}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
    >
      <div
        className="relative w-full max-w-md bg-white dark:bg-neutral-900 border border-slate-200 dark:border-neutral-800 rounded-2xl shadow-2xl overflow-hidden p-6 sm:p-8"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          onClick={closeLoginModal}
          className="absolute top-5 right-5 p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-neutral-200 hover:bg-slate-100 dark:hover:bg-neutral-800 transition-colors"
          aria-label="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Brand Mark & Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600 text-white shadow-md shadow-blue-600/20 mb-3.5">
            <Newspaper className="w-6 h-6" />
          </div>
          <h2 id="auth-modal-title" className="text-xl sm:text-2xl font-bold font-sans text-news-text-primary tracking-tight">
            Sign in to Pulse
          </h2>
          <p className="text-sm text-news-text-secondary mt-2 leading-relaxed">
            Your personalized news intelligence, saved stories, and recommendations — all in one place.
          </p>
        </div>

        {/* Error Presentation */}
        {error && (
          <div className="mb-5 p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 text-red-700 dark:text-red-300 text-xs flex items-start gap-2 text-left">
            <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Primary Action: Google Authentication */}
        <div className="space-y-4">
          {authConfig?.google_configured ? (
            <button
              onClick={handleGoogleSignIn}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-xl bg-white hover:bg-slate-50 dark:bg-neutral-800 dark:hover:bg-neutral-750 text-slate-800 dark:text-neutral-100 border border-slate-300 dark:border-neutral-700 font-medium text-sm transition-all shadow-sm active:scale-[0.99] disabled:opacity-50"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              <span>{loading ? 'Connecting...' : 'Continue with Google'}</span>
            </button>
          ) : (
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-neutral-800/80 border border-slate-200 dark:border-neutral-700/60 text-xs text-news-text-secondary text-center">
              <p className="font-medium text-news-text-primary">Google sign-in is temporarily unavailable.</p>
            </div>
          )}

          {/* Privacy & Account Association Guarantee */}
          <p className="text-xs text-news-text-secondary text-center leading-relaxed pt-1">
            Your preferences and saved stories are securely associated with your account.
          </p>

          {/* Development Sign-In: strictly environment-gated and never present in production */}
          {isDevAuthAvailable && (
            <div className="pt-4 mt-4 border-t border-dashed border-slate-200 dark:border-neutral-800 text-left space-y-2">
              <span className="text-[11px] font-semibold text-slate-400 dark:text-neutral-500 uppercase tracking-wider block">
                Development Sign In
              </span>
              <form onSubmit={handleDevSignIn} className="flex gap-2">
                <input
                  type="email"
                  value={devEmail}
                  onChange={(e) => setDevEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="flex-1 px-3 py-2 bg-slate-50 dark:bg-neutral-950 border border-slate-200 dark:border-neutral-700 rounded-lg text-xs text-news-text-primary outline-none focus:border-blue-500"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 dark:bg-neutral-800 dark:hover:bg-neutral-700 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                >
                  {loading ? '...' : 'Sign In'}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
