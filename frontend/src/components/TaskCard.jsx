import { EditIcon } from './icons';

/** Tek bir görevi gösteren kart. */
export default function TaskCard({ task, onEdit, onDelete, busy }) {
  const isDone = task.status === 'Tamamlandı';

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 flex flex-col justify-between hover:shadow-md transition-shadow">
      <div>
        <div className="flex justify-between items-start gap-2 mb-2">
          <h3 className="font-bold text-sm text-slate-900 break-words">{task.title}</h3>
          <span
            className={`text-[10px] font-semibold px-2.5 py-1 rounded-full whitespace-nowrap shrink-0 ${
              isDone ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'
            }`}
          >
            • {task.status}
          </span>
        </div>
        <p className="text-xs text-slate-500 mb-6 break-words">
          {task.description || 'Açıklama girilmemiş.'}
        </p>
      </div>

      <div className="flex flex-wrap justify-between items-center gap-2 pt-3 border-t border-slate-100">
        <span className="text-[10px] font-mono text-blue-600 bg-blue-50 px-2.5 py-1 rounded-lg uppercase tracking-wider font-semibold">
          {task.db_source}
        </span>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onEdit(task)}
            disabled={busy}
            className="bg-slate-50 hover:bg-slate-600 text-slate-600 hover:text-white px-3 py-1.5 text-xs font-medium rounded-xl transition-colors border border-slate-200 flex items-center gap-1 disabled:opacity-50"
          >
            <EditIcon className="w-3 h-3" />
            Düzenle
          </button>

          <button
            type="button"
            onClick={() => onDelete(task)}
            disabled={busy}
            className="bg-red-50 hover:bg-red-500 text-red-500 hover:text-white px-3 py-1.5 text-xs font-medium rounded-xl transition-colors border border-red-100 disabled:opacity-50"
          >
            Sil
          </button>
        </div>
      </div>
    </div>
  );
}
