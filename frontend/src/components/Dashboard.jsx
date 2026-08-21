import { useCallback, useEffect, useState } from 'react';

import { api } from '../api';
import Header from './Header';
import TaskCard from './TaskCard';
import TaskForm from './TaskForm';
import { useToast } from './toastContext';
import { SpinnerIcon } from './icons';

/** Bir seferde çekilecek görev sayısı. */
const PAGE_SIZE = 12;

const SOURCES = [
  { key: 'mssql', label: 'MSSQL Görevleri' },
  { key: 'mongodb', label: 'MongoDB Görevleri' },
];

export default function Dashboard({ username, isAdmin, view, onViewChange, onLogout }) {
  const [dataSource, setDataSource] = useState('mssql');
  const [editingTask, setEditingTask] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const showToast = useToast();

  // Yüklenen verinin hangi kaynağa ve hangi yükleme turuna ait olduğu
  // birlikte tutulur; böylece ayrı bir "loading" bayrağı gerekmez.
  const [loaded, setLoaded] = useState({ source: null, key: -1, tasks: [], total: 0 });

  const loading = loaded.source !== dataSource || loaded.key !== reloadKey;
  const tasks = loading ? [] : loaded.tasks;
  const total = loading ? 0 : loaded.total;
  const hasMore = tasks.length < total;

  const reload = useCallback(() => setReloadKey((key) => key + 1), []);

  // İlk sayfa: kaynak değiştiğinde veya yeniden yükleme istendiğinde.
  useEffect(() => {
    // Kaynak hızlıca değiştirilirse geç gelen yanıt yeni veriyi ezmesin.
    let active = true;

    api
      .listTasks(dataSource, { limit: PAGE_SIZE, offset: 0 })
      .then(({ items, total: toplam }) => {
        if (active) {
          setLoaded({ source: dataSource, key: reloadKey, tasks: items, total: toplam });
        }
      })
      .catch((error) => {
        if (!active) return;
        showToast(error.message, 'error');
        setLoaded({ source: dataSource, key: reloadKey, tasks: [], total: 0 });
      });

    return () => {
      active = false;
    };
  }, [dataSource, reloadKey, showToast]);

  /** Sonraki sayfayı getirip mevcut listenin sonuna ekler. */
  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const { items, total: toplam } = await api.listTasks(dataSource, {
        limit: PAGE_SIZE,
        offset: tasks.length,
      });

      setLoaded((current) => {
        // Bu sırada kaynak değiştiyse gelen sayfa artık geçersizdir.
        if (current.source !== dataSource || current.key !== reloadKey) return current;

        // Araya yeni kayıt girmiş olabilir; aynı görevin iki kez
        // eklenmesini kimliğe bakarak engelliyoruz.
        const mevcut = new Set(current.tasks.map((task) => task.id));
        const yeniler = items.filter((task) => !mevcut.has(task.id));

        return { ...current, tasks: [...current.tasks, ...yeniler], total: toplam };
      });
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setLoadingMore(false);
    }
  };

  const handleDelete = async (task) => {
    setBusy(true);
    try {
      await api.deleteTask(task.id, task.db_source);
      showToast('Görev silindi.', 'success');
      if (editingTask?.id === task.id) setEditingTask(null);
      reload();
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const handleFinished = () => {
    setEditingTask(null);
    reload();
  };

  const activeCount = tasks.filter((task) => task.status !== 'Tamamlandı').length;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 p-4 sm:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto">
        <Header
          username={username}
          isAdmin={isAdmin}
          view={view}
          onViewChange={onViewChange}
          onLogout={onLogout}
        />


        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
          {/* Sol sütun */}
          <div className="lg:col-span-1 space-y-6">
            <TaskForm
              editingTask={editingTask}
              onFinished={handleFinished}
              onCancelEdit={() => setEditingTask(null)}
            />

            <div className="bg-white border border-slate-200 rounded-2xl p-5 sm:p-6 shadow-sm">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Sistem Durumu
                </h3>
                <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-50 border border-slate-100 p-4 rounded-xl">
                  <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                    TOPLAM
                  </span>
                  <span className="text-2xl font-black text-slate-800">{total}</span>
                </div>
                <div className="bg-slate-50 border border-slate-100 p-4 rounded-xl">
                  <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                    {hasMore ? 'YÜKLENEN' : 'AKTİF'}
                  </span>
                  <span className="text-2xl font-black text-blue-600">
                    {hasMore ? tasks.length : activeCount}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Sağ sütun */}
          <div className="lg:col-span-2 space-y-6">
            <div className="flex flex-col sm:flex-row gap-2 bg-white border border-slate-200 p-1.5 rounded-2xl w-full sm:w-fit shadow-sm">
              {SOURCES.map((source) => (
                <button
                  key={source.key}
                  type="button"
                  onClick={() => setDataSource(source.key)}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold transition-colors ${
                    dataSource === source.key
                      ? 'bg-blue-600 text-white shadow'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                  }`}
                >
                  {source.label}
                </button>
              ))}
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-5 sm:p-6 shadow-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-2 mb-6">
                <h2 className="font-bold text-base sm:text-lg text-slate-900">
                  Mevcut Görevler ({dataSource.toUpperCase()})
                </h2>
                {!loading && total > 0 && (
                  <span className="text-xs text-slate-400">
                    {tasks.length} / {total} görev
                  </span>
                )}
              </div>

              {loading ? (
                <div className="flex items-center justify-center gap-2 py-12 text-slate-400 text-sm">
                  <SpinnerIcon className="w-4 h-4" />
                  Yükleniyor...
                </div>
              ) : tasks.length === 0 ? (
                <p className="text-slate-400 text-sm py-12 text-center">
                  Bu veritabanında henüz kayıtlı görev bulunmuyor.
                </p>
              ) : (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {tasks.map((task) => (
                      <TaskCard
                        key={`${task.db_source}-${task.id}`}
                        task={task}
                        busy={busy}
                        onEdit={setEditingTask}
                        onDelete={handleDelete}
                      />
                    ))}
                  </div>

                  {hasMore && (
                    <div className="mt-6 flex flex-col items-center gap-2">
                      <button
                        type="button"
                        onClick={loadMore}
                        disabled={loadingMore}
                        className="w-full sm:w-auto px-6 py-2.5 rounded-xl text-sm font-semibold border border-slate-200 text-slate-700 bg-white hover:bg-slate-50 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                      >
                        {loadingMore && <SpinnerIcon className="w-4 h-4" />}
                        {loadingMore ? 'Yükleniyor...' : 'Daha fazla yükle'}
                      </button>
                      <span className="text-[11px] text-slate-400">
                        {total - tasks.length} görev daha var
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
