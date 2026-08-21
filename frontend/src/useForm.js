import { useCallback, useState } from 'react';
import { validateForm } from './validation';

/**
 * Form değerlerini, doğrulama hatalarını ve "dokunuldu" durumunu yönetir.
 *
 * Doğrulama her render'da yeniden çalışır; kullanıcı yazdıkça hata mesajı
 * anında güncellenir (taslaktaki "anlık bildirim" gereksinimi).
 */
export function useForm(initialValues, fieldRules) {
  const [values, setValues] = useState(initialValues);
  const [touched, setTouched] = useState({});

  const errors = validateForm(values, fieldRules);
  const isValid = Object.keys(errors).length === 0;

  const setValue = useCallback((name, value) => {
    setValues((current) => ({ ...current, [name]: value }));
  }, []);

  const markTouched = useCallback((name) => {
    setTouched((current) => ({ ...current, [name]: true }));
  }, []);

  /** Gönderim denemesinde tüm hataların görünür olmasını sağlar. */
  const touchAll = useCallback(() => {
    setTouched((current) => {
      const all = { ...current };
      for (const name of Object.keys(values)) all[name] = true;
      return all;
    });
  }, [values]);

  const reset = useCallback((nextValues = initialValues) => {
    setValues(nextValues);
    setTouched({});
  }, [initialValues]);

  return {
    values,
    errors,
    touched,
    isValid,
    setValue,
    setValues,
    markTouched,
    touchAll,
    reset,
  };
}
