import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { ApiService } from '../services/api';
import { StorageService } from '../services/storage';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('pulse_auth_token'));
  const [isLoading, setIsLoading] = useState(true);
  const [authConfig, setAuthConfig] = useState({ google_configured: false, client_id: '', redirect_uri: '', dev_login_enabled: false });
  const [savedCount, setSavedCount] = useState(0);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);

  // Fetch public auth config on mount
  useEffect(() => {
    let isMounted = true;
    ApiService.getAuthConfig().then((cfg) => {
      if (isMounted && cfg) {
        setAuthConfig(cfg);
      }
    });
    return () => { isMounted = false; };
  }, []);

  // Update saved count
  const refreshSavedCount = useCallback(async () => {
    try {
      if (localStorage.getItem('pulse_auth_token')) {
        const res = await ApiService.getSavedStories();
        setSavedCount(res.total || 0);
      } else {
        const localIds = StorageService.getSavedStoryIds();
        setSavedCount(localIds.length);
      }
    } catch {
      if (localStorage.getItem('pulse_auth_token')) {
        setSavedCount(0);
      } else {
        const localIds = StorageService.getSavedStoryIds();
        setSavedCount(localIds.length);
      }
    }
  }, []);

  // Check current session on mount or token change
  useEffect(() => {
    let isMounted = true;
    const initAuth = async () => {
      const savedToken = localStorage.getItem('pulse_auth_token');
      if (!savedToken) {
        if (isMounted) {
          setUser(null);
          setIsLoading(false);
          refreshSavedCount();
        }
        return;
      }

      try {
        const currentUser = await ApiService.getCurrentUser();
        if (isMounted) {
          if (currentUser) {
            setUser(currentUser);
            localStorage.setItem('pulse_user_profile', JSON.stringify(currentUser));
          } else {
            // Token expired or invalid
            localStorage.removeItem('pulse_auth_token');
            localStorage.removeItem('pulse_user_profile');
            setUser(null);
          }
          setIsLoading(false);
          refreshSavedCount();
        }
      } catch (err) {
        console.error('Session validation error:', err);
        if (isMounted) {
          localStorage.removeItem('pulse_auth_token');
          localStorage.removeItem('pulse_user_profile');
          setUser(null);
          setIsLoading(false);
          refreshSavedCount();
        }
      }
    };

    initAuth();

    // Listen to local bookmark update events
    const handleSavedUpdated = () => {
      refreshSavedCount();
    };
    window.addEventListener('pulse_saved_updated', handleSavedUpdated);

    return () => {
      isMounted = false;
      window.removeEventListener('pulse_saved_updated', handleSavedUpdated);
    };
  }, [token, refreshSavedCount]);

  const loginWithGoogle = async (redirectPath = window.location.pathname) => {
    try {
      sessionStorage.setItem('pulse_auth_redirect', redirectPath);
      const res = await ApiService.getGoogleAuthUrl();
      if (res && res.url) {
        window.location.href = res.url;
      }
    } catch (err) {
      console.error('Google login failed:', err);
      throw err;
    }
  };

  const devLogin = async ({ email, name, pictureUrl }) => {
    try {
      const res = await ApiService.devLogin({ email, name, pictureUrl });
      if (res && res.token) {
        localStorage.setItem('pulse_auth_token', res.token);
        setToken(res.token);
        setUser(res.user);
        localStorage.setItem('pulse_user_profile', JSON.stringify(res.user));
        setIsLoginModalOpen(false);
        await refreshSavedCount();
        return res.user;
      }
    } catch (err) {
      console.error('Dev login error:', err);
      throw err;
    }
  };

  const logout = async () => {
    try {
      await ApiService.logout();
    } finally {
      localStorage.removeItem('pulse_auth_token');
      localStorage.removeItem('pulse_user_profile');
      localStorage.removeItem('pulse_saved_story_ids');
      setToken(null);
      setUser(null);
      setSavedCount(0);
      window.dispatchEvent(new CustomEvent('pulse_saved_updated', { detail: { count: 0 } }));
    }
  };

  const openLoginModal = () => setIsLoginModalOpen(true);
  const closeLoginModal = () => setIsLoginModalOpen(false);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        authConfig,
        savedCount,
        refreshSavedCount,
        loginWithGoogle,
        devLogin,
        logout,
        isLoginModalOpen,
        openLoginModal,
        closeLoginModal,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
