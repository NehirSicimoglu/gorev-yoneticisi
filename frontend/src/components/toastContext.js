import { createContext, useContext } from 'react';

/**
 * Bildirim bağlamı ve erişim hook'u.
 *
 * Bileşenlerden ayrı bir dosyada tutulur: React Fast Refresh, yalnızca
 * bileşen dışa aktaran dosyalarda düzgün çalışır.
 */
export const ToastContext = createContext(null);

/** Bildirim göstermek için: const showToast = useToast(); */
export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast, ToastProvider içinde kullanılmalıdır.');
  return context;
}
