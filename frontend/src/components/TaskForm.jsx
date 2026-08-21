import { useEffect, useState } from 'react';

import { api } from '../api';
import { useForm } from '../useForm';
import { validators } from '../validation';
import Field from './Field';
import { useToast } from './toastContext';
import { EditIcon, PlusIcon, SaveIcon, SpinnerIcon } from './icons';

const RULES = { title: validators.title };
const EMPTY = { title: '', description: '', status: 'Beklemede', dbTarget: 'mssql' };

/**
 * Görev ekleme ve düzenleme formu.
 *
 * `editingTask` doluysa güncelleme kipine geçer. Düzenleme sırasında
 * veritabanı seçimi kilitlenir: bir kayıt sonradan başka bir veritabanına
 * taşınamaz.
 */
export default function TaskForm({ editingTask, onFinished, onCancelEdit }) {
  const [busy, setBusy] = useState(false);
  const showToast = useToast();
  const form = useForm(EMPTY, RULES);
  const isEditing = Boolean(editingTask);

  const { setValues, reset } = form;

  useEffect(() => {
    if (editingTask) {
      setValues({
        title: editingTask.title ?? '',
        description: editingTask.description ?? '',
        status: editingTask.status ?? 'Beklemede',
        dbTarget: editingTask.db_source ?? 'mssql',
      });
    } else {
      reset(EMPTY);
    }
  }, [editingTask, setValues, reset]);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!form.isValid) {
      form.touchAll();
      showToast('Lütfen formdaki eksikleri giderin.', 'error');
      return;
    }

    const payload = {
      title: form.values.title.trim(),
      description: form.values.description.trim(),
      status: form.values.status,
      db_target: form.values.dbTarget,
    };

    setBusy(true);
    try {
      if (isEditing) {
        await api.updateTask(editingTask.id, payload);
        showToast('Görev güncellendi.', 'success');
      } else {
        const created = await api.createTask(payload);
        const where = created.map((task) => task.db_source.toUpperCase()).join(' ve ');
        showToast(`Görev ${where} üzerine kaydedildi.`, 'success');
      }
      form.reset(EMPTY);
      onFinished();
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const selectClass =
    'w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs text-slate-800 ' +
    'focus:outline-none focus:border-blue-500 disabled:opacity-60 disabled:cursor-not-allowed';

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 sm:p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        {isEditing ? (
          <EditIcon className="w-5 h-5 text-amber-600" />
        ) : (
          <PlusIcon className="w-5 h-5 text-blue-600" />
        )}
        <h2 className="text-base font-bold text-slate-900">
          {isEditing ? 'Görevi Düzenle' : 'Yeni Görev Ekle'}
        </h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <Field
          label="GÖREV BAŞLIĞI"
          name="title"
          placeholder="Örn: Veritabanı Optimizasyonu"
          value={form.values.title}
          onChange={form.setValue}
          onBlur={form.markTouched}
          error={form.errors.title}
          touched={form.touched.title}
          disabled={busy}
        />

        <Field
          label="AÇIKLAMA"
          name="description"
          textarea
          rows={4}
          placeholder="Görev detaylarını buraya yazın..."
          value={form.values.description}
          onChange={form.setValue}
          onBlur={form.markTouched}
          disabled={busy}
        />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label htmlFor="status" className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
              DURUM
            </label>
            <select
              id="status"
              value={form.values.status}
              onChange={(event) => form.setValue('status', event.target.value)}
              disabled={busy}
              className={selectClass}
            >
              <option value="Beklemede">Beklemede</option>
              <option value="Tamamlandı">Tamamlandı</option>
            </select>
          </div>

          <div>
            <label htmlFor="dbTarget" className="block text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
              KAYNAK
            </label>
            <select
              id="dbTarget"
              value={form.values.dbTarget}
              onChange={(event) => form.setValue('dbTarget', event.target.value)}
              disabled={busy || isEditing}
              className={selectClass}
            >
              <option value="mssql">MSSQL</option>
              <option value="mongodb">MongoDB</option>
              {!isEditing && <option value="both">İkisi de</option>}
            </select>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <button
            type="submit"
            disabled={busy}
            className={`flex-1 text-white font-semibold py-3 rounded-xl text-sm transition-colors shadow-md flex items-center justify-center gap-2 disabled:opacity-70 ${
              isEditing
                ? 'bg-amber-600 hover:bg-amber-700 shadow-amber-500/20'
                : 'bg-blue-600 hover:bg-blue-700 shadow-blue-500/20'
            }`}
          >
            {busy ? <SpinnerIcon className="w-4 h-4" /> : <SaveIcon className="w-4 h-4" />}
            {isEditing ? 'Değişiklikleri Kaydet' : 'Görevi Kaydet'}
          </button>

          {isEditing && (
            <button
              type="button"
              onClick={onCancelEdit}
              disabled={busy}
              className="sm:w-32 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-3 rounded-xl text-sm transition-colors"
            >
              Vazgeç
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
