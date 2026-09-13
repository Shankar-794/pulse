import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ApiService } from '../services/api';
import { ShieldCheck, AlertCircle, ArrowLeft } from 'lucide-react';

export const AuthCallbackPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('processing'); // 'processing' | 'error' | 'success'
  const [errorMessage, setErrorMessage] = useState(null);

  useEffect(() => {
    let isCancelled = false;

    const processAuth = async () => {
      const code = searchParams.get('code');
      const error = searchParams.get('error');

      if (error) {
        if (!isCancelled) {
          setStatus('error');
          setErrorMessage('Sign-in was cancelled or interrupted. Please try again.');
        }
        return;
      }

      if (!code) {
        if (!isCancelled) {
          setStatus('error');
          setErrorMessage('Unable to complete sign-in. Please try again.');
        }
        return;
      }

      try {
        const redirectUri = window.location.origin + '/auth/callback';
        const res = await ApiService.handleGoogleCallback(code, redirectUri);
        
        if (res && res.token) {
          localStorage.setItem('pulse_auth_token', res.token);
          if (res.user) {
            localStorage.setItem('pulse_user_profile', JSON.stringify(res.user));
          }
          if (!isCancelled) {
            setStatus('success');
            const targetPath = sessionStorage.getItem('pulse_auth_redirect') || '/';
            sessionStorage.removeItem('pulse_auth_redirect');
            // Allow token to propagate, then navigate
            setTimeout(() => {
              window.location.href = targetPath;
            }, 300);
          }
        } else {
          throw new Error('No authentication token returned by server');
        }
      } catch {
        if (!isCancelled) {
          setStatus('error');
          setErrorMessage('Unable to complete sign-in. Please try again.');
        }
      }
    };

    processAuth();

    return () => {
      isCancelled = true;
    };
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen bg-neutral-950 flex flex-col items-center justify-center p-4 text-center">
      <div className="w-full max-w-md p-8 bg-neutral-900 border border-neutral-800 rounded-2xl shadow-xl">
        {status === 'processing' && (
          <div className="space-y-4">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 animate-pulse">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-neutral-100">Authenticating with Google</h2>
            <p className="text-sm text-neutral-400">Verifying credentials and creating your secure session...</p>
          </div>
        )}

        {status === 'success' && (
          <div className="space-y-4">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-neutral-100">Welcome to Pulse</h2>
            <p className="text-sm text-neutral-400">Authentication successful. Redirecting...</p>
          </div>
        )}

        {status === 'error' && (
          <div className="space-y-4">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-neutral-100">Authentication Failed</h2>
            <p className="text-sm text-red-400/90">{errorMessage}</p>
            <div className="pt-4">
              <button
                onClick={() => navigate('/')}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-sm font-medium text-neutral-200 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Return to Home
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
