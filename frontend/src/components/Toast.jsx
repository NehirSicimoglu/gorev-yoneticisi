import { useCallback, useState } from 'react';

import { ToastContext } from './toastContext';

/**
 * Anlık bildirim sistemi.
 *
 * Tarayıcının alert() kutusunun yerini alır: sayfayı bloke etmez,
 * kendiliğinden kapanır ve başarı/hata ayrımını renkle gösterir.
 */

const STYLES = {
  success: {
    box: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    dot: 'bg-emerald-500',
  },
  error: {
    box: 'bg-red-50 border-red-200 text-red-800',
    dot: 'bg-red-500',
  },
  info: {
    box: 'bg-blue-50 border-blue-200 text-blue-800',
    dot: 'bg-blue-500',
  },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback(
    (message, type = 'info') => {
      const id = Date.now() + Math.random();
      setToasts((current) => [...current, { id, message, type }]);
      setTimeout(() => dismiss(id), 4000);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={showToast}>
      {children}

      {/* Mobilde tam genişlik üstte, geniş ekranda sağ üstte */}
      <div className="fixed top-4 left-4 right-4 sm:left-auto sm:right-6 sm:w-96 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((toast) => {
          const style = STYLES[toast.type] ?? STYLES.info;
          return (
            <div
              key={toast.id}
              role="status"
              className={`pointer-events-auto flex items-start gap-3 border rounded-xl px-4 py-3 shadow-lg text-sm ${style.box}`}
            >
              <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${style.dot}`} />
              <p className="flex-1 leading-snug">{toast.message}</p>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="shrink-0 opacity-50 hover:opacity-100 transition-opacity"
                aria-label="Bildirimi kapat"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
