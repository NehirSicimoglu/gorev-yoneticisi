/**
 * Etiket + giriş alanı + hata mesajını birlikte yöneten bileşen.
 *
 * Hata mesajı yalnızca alan bir kez dokunulduktan sonra gösterilir;
 * böylece kullanıcı forma başlar başlamaz kırmızı uyarı görmez.
 *
 * ``hint`` kuralı önceden anlatır ve hata çıkınca yerini ona bırakır;
 * ikisi aynı anda görünmez, yoksa alanın altı kalabalıklaşır.
 */
export default function Field({
  label,
  name,
  type = 'text',
  value,
  onChange,
  onBlur,
  error,
  touched,
  placeholder,
  hint,
  icon,
  textarea = false,
  disabled = false,
  rows = 4,
}) {
  const showError = Boolean(touched && error);

  const baseClass =
    'w-full bg-slate-50 border rounded-xl py-2.5 text-sm text-slate-800 placeholder-slate-400 ' +
    'focus:outline-none focus:bg-white transition-colors disabled:opacity-60 disabled:cursor-not-allowed';
  const borderClass = showError
    ? 'border-red-300 focus:border-red-500'
    : 'border-slate-200 focus:border-blue-500';
  const paddingClass = icon ? 'pl-10 pr-4' : 'px-3.5';

  const shared = {
    id: name,
    name,
    value,
    onChange: (event) => onChange(name, event.target.value),
    onBlur: () => onBlur(name),
    placeholder,
    disabled,
    'aria-invalid': showError,
    'aria-describedby': showError
      ? `${name}-error`
      : hint
        ? `${name}-hint`
        : undefined,
  };

  return (
    <div>
      <label
        htmlFor={name}
        className="block text-[11px] font-bold text-slate-600 uppercase tracking-wider mb-1.5"
      >
        {label}
      </label>

      <div className="relative">
        {icon && (
          <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
            {icon}
          </span>
        )}

        {textarea ? (
          <textarea
            {...shared}
            rows={rows}
            className={`${baseClass} ${borderClass} px-3.5 resize-none`}
          />
        ) : (
          <input
            {...shared}
            type={type}
            className={`${baseClass} ${borderClass} ${paddingClass}`}
          />
        )}
      </div>

      {!showError && hint && (
        <p id={`${name}-hint`} className="mt-1.5 text-xs text-slate-500">
          {hint}
        </p>
      )}

      {showError && (
        <p id={`${name}-error`} className="mt-1.5 text-xs text-red-600 flex items-center gap-1">
          <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {error}
        </p>
      )}
    </div>
  );
}
