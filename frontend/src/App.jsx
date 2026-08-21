import { useCallback, useEffect, useState } from 'react';

import { api, setAccessToken, setSessionLostHandler } from './api';
import AdminPanel from './components/AdminPanel';
import AuthScreen from './components/AuthScreen';
import Dashboard from './components/Dashboard';
import { ToastProvider } from './components/Toast';

/**
 * Uygulamanın giriş noktası.
 *
 * Oturum bilgisi tarayıcı depolamasında tutulmaz. Sayfa açıldığında
 * httpOnly çerezdeki refresh token ile oturum geri getirilmeye çalışılır;
 * çerez yoksa veya geçersizse giriş ekranı gösterilir.
 */
export default function App() {
  const [session, setSession] = useState(null);
  const [view, setView] = useState('tasks');
  // Çerez denenene kadar hiçbir ekran gösterilmez; aksi hâlde giriş
  // ekranı bir an görünüp kaybolurdu.
  const [restoring, setRestoring] = useState(true);

  const handleSessionLost = useCallback(() => setSession(null), []);

  const handleLogin = useCallback((accessToken, username, isAdmin) => {
    setAccessToken(accessToken);
    setSession({ username, isAdmin });
    setView('tasks');
  }, []);

  const handleLogout = useCallback(async () => {
    try {
      // Sunucudaki yenileme zinciri iptal edilir ve çerez silinir.
      await api.logout();
    } catch {
      // Sunucuya ulaşılamasa bile yerel oturum kapatılır.
    }
    setAccessToken(null);
    setSession(null);
    setView('tasks');
  }, []);

  useEffect(() => {
    setSessionLostHandler(handleSessionLost);
  }, [handleSessionLost]);

  // Sayfa açılışında çerezle oturumu geri getirmeyi dene.
  useEffect(() => {
    let active = true;

    api
      .restore()
      .then((restored) => {
        if (!active) return;
        if (restored) setSession({ username: restored.username, isAdmin: restored.is_admin });
        setRestoring(false);
      })
      .catch(() => {
        if (active) setRestoring(false);
      });

    return () => {
      active = false;
    };
  }, []);

  if (restoring) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="flex items-center gap-3 text-slate-400 text-sm">
          <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Oturum kontrol ediliyor...
        </div>
      </div>
    );
  }

  return (
    <ToastProvider>
      {!session ? (
        <AuthScreen onLogin={handleLogin} />
      ) : view === 'admin' && session.isAdmin ? (
        <AdminPanel
          username={session.username}
          view={view}
          onViewChange={setView}
          onLogout={handleLogout}
        />
      ) : (
        <Dashboard
          username={session.username}
          isAdmin={session.isAdmin}
          view={view}
          onViewChange={setView}
          onLogout={handleLogout}
        />
      )}
    </ToastProvider>
  );
}
