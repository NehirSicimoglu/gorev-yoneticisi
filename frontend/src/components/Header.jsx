import { LogoutIcon, ShieldIcon, TasksIcon, UserIcon } from './icons';

/**
 * Tüm ekranlarda ortak üst çubuk.
 *
 * Yönetim sekmesi yalnızca yetkili kullanıcıya gösterilir — ama bu
 * sadece görsel bir kolaylıktır. Yetki denetimi sunucuda yapılır;
 * sekme gizli olsa da olmasa da yetkisiz istek 403 alır.
 */
export default function Header({ username, isAdmin, view, onViewChange, onLogout }) {
  const sekme = (deger, etiket, Icon) => (
    <button
      key={deger}
      type="button"
      onClick={() => onViewChange(deger)}
      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
        view === deger
          ? 'bg-white text-slate-900 shadow-sm'
          : 'text-slate-500 hover:text-slate-800'
      }`}
    >
      <Icon className="w-3.5 h-3.5" />
      {etiket}
    </button>
  );

  return (
    <header className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-6 lg:mb-8 bg-white px-4 sm:px-6 py-4 rounded-2xl shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <h1 className="text-lg sm:text-xl font-bold text-slate-900">
          Görev Yönetim Paneli
        </h1>

        {isAdmin && (
          <div className="flex gap-1 bg-slate-100 p-1 rounded-xl w-fit">
            {sekme('tasks', 'Görevler', TasksIcon)}
            {sekme('admin', 'Yönetim', ShieldIcon)}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between sm:justify-end gap-3 sm:gap-4">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-600 bg-slate-100 px-3 py-1.5 rounded-xl min-w-0">
          <UserIcon className="w-4 h-4 text-slate-500 shrink-0" />
          <span className="truncate">Hoş geldiniz, {username}</span>
          {isAdmin && (
            <span className="shrink-0 text-[10px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
              YÖNETİCİ
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={onLogout}
          className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center gap-1.5 shadow-md shadow-red-500/20 shrink-0"
        >
          <LogoutIcon className="w-3.5 h-3.5" />
          Çıkış Yap
        </button>
      </div>
    </header>
  );
}
