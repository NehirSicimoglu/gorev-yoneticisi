import { useState } from 'react';

import { api } from '../api';
import { useForm } from '../useForm';
import { validators } from '../validation';
import Field from './Field';
import { useToast } from './toastContext';
import { CheckIcon, LockIcon, MailIcon, SpinnerIcon, UserIcon } from './icons';

const LOGIN_RULES = {
  username: validators.username,
  password: validators.loginPassword,
};

const REGISTER_RULES = {
  username: validators.username,
  email: validators.email,
  password: validators.password,
};

export default function AuthScreen({ onLogin }) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [busy, setBusy] = useState(false);
  const showToast = useToast();

  const rules = isRegistering ? REGISTER_RULES : LOGIN_RULES;
  const form = useForm({ username: '', email: '', password: '' }, rules);

  const switchMode = (registering) => {
    setIsRegistering(registering);
    form.reset({ username: '', email: '', password: '' });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    // Geçersizse sunucuya hiç gidilmez; eksik alanlar işaretlenir.
    if (!form.isValid) {
      form.touchAll();
      showToast('Lütfen formdaki eksikleri giderin.', 'error');
      return;
    }

    setBusy(true);
    try {
      if (isRegistering) {
        await api.register({
          username: form.values.username.trim(),
          email: form.values.email.trim(),
          password: form.values.password,
        });
        showToast('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success');
        switchMode(false);
      } else {
        const session = await api.login({
          username: form.values.username.trim(),
          password: form.values.password,
        });
        onLogin(session.access_token, session.username, session.is_admin);
      }
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const fieldProps = (name) => ({
    name,
    value: form.values[name],
    onChange: form.setValue,
    onBlur: form.markTouched,
    error: form.errors[name],
    touched: form.touched[name],
    disabled: busy,
  });

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50/40 to-slate-100 flex flex-col items-center justify-center p-4 sm:p-6">
      <div className="text-center mb-6">
        <div className="w-12 h-12 bg-blue-600 rounded-xl mx-auto flex items-center justify-center shadow-lg shadow-blue-500/30 mb-2">
          <CheckIcon className="w-6 h-6 text-white" />
        </div>
        <h2 className="text-lg sm:text-xl font-bold text-slate-800">Görev Yöneticisi</h2>
      </div>

      <div className="w-full max-w-md bg-white border border-slate-200/80 rounded-2xl p-6 sm:p-8 shadow-xl shadow-slate-200/50">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-slate-900">
            {isRegistering ? 'Kayıt Ol' : 'Giriş Yap'}
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {isRegistering
              ? 'Hemen bir hesap oluşturun ve projelerinizi koordine etmeye başlayın.'
              : 'Devam etmek için hesap bilgilerinizi girin.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <Field
            label="KULLANICI ADI"
            placeholder="Kullanıcı Adınız"
            icon={<UserIcon className="w-4 h-4" />}
            {...fieldProps('username')}
          />

          {isRegistering && (
            <Field
              label="E-POSTA ADRESİ"
              type="email"
              placeholder="isim@sirket.com"
              icon={<MailIcon className="w-4 h-4" />}
              {...fieldProps('email')}
            />
          )}

          <Field
            label="ŞİFRE"
            type="password"
            placeholder="••••••••"
            icon={<LockIcon className="w-4 h-4" />}
            hint={
              isRegistering
                ? 'En az 8 karakter ve bir büyük harf içermelidir.'
                : undefined
            }
            {...fieldProps('password')}
          />

          <button
            type="submit"
            disabled={busy}
            className={`w-full text-white font-semibold py-3 rounded-xl text-sm transition-colors shadow-md mt-2 flex items-center justify-center gap-2 disabled:opacity-70 ${
              isRegistering
                ? 'bg-green-600 hover:bg-green-700 shadow-green-500/20'
                : 'bg-blue-600 hover:bg-blue-700 shadow-blue-500/20'
            }`}
          >
            {busy && <SpinnerIcon className="w-4 h-4" />}
            {isRegistering ? 'Kayıt Ol' : 'Giriş Yap'}
          </button>
        </form>
      </div>

      <div className="mt-6 text-center">
        <p className="text-xs text-slate-500">
          {isRegistering ? 'Zaten bir hesabın var mı? ' : 'Hesabın yok mu? '}
          <button
            type="button"
            onClick={() => switchMode(!isRegistering)}
            className="text-blue-600 font-bold hover:underline"
          >
            {isRegistering ? 'Giriş Yap' : 'Kayıt Ol'}
          </button>
        </p>
      </div>
    </div>
  );
}
