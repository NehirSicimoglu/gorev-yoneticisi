import { useCallback, useEffect, useState } from 'react';

import { api } from '../api';
import Header from './Header';
import { SpinnerIcon } from './icons';
import { useToast } from './toastContext';

/**
 * Yönetim ekranı: kullanıcılar, oturumlar ve kimlik doğrulama olayları.
 *
 * Bu bileşenin görünür olması yetki vermez — her istek sunucuda
 * ayrıca denetlenir. Yetkisiz bir kullanıcı adres çubuğundan bu
 * ekrana ulaşsa bile veri gelmez, 403 alır.
 */

const OLAY_ETIKETLERI = {
  register: 'Kayıt',
  login: 'Giriş',
  logout: 'Çıkış',
  refresh: 'Yenileme',
  token_reuse: 'ANAHTAR TEKRARI',
};

const SEKMELER = [
  { key: 'users', label: 'Kullanıcılar' },
  { key: 'sessions', label: 'Oturumlar' },
  { key: 'events', label: 'Olaylar' },
];

const zaman = (deger) =>
  deger ? new Date(deger).toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' }) : '—';

export default function AdminPanel({ username, view, onViewChange, onLogout }) {
  const [sekme, setSekme] = useState('users');
  const [tazele, setTazele] = useState(0);
  const showToast = useToast();

  // Hangi sekmenin ve hangi tazeleme turunun verisi elimizde olduğu
  // birlikte tutulur; böylece "yükleniyor" ayrı bir bayrak olmadan
  // durumdan türetilir ve tutarsızlaşamaz.
  const [yuklenen, setYuklenen] = useState({ tab: null, key: -1, rows: [] });

  const yukleniyor = yuklenen.tab !== sekme || yuklenen.key !== tazele;
  const satirlar = yukleniyor ? null : yuklenen.rows;

  const getir = useCallback(async (hangi) => {
    if (hangi === 'users') return api.adminUsers();
    if (hangi === 'sessions') return api.adminSessions();
    return api.adminEvents(50);
  }, []);

  useEffect(() => {
    // Sekme hızlıca değiştirilirse geç gelen yanıt yeni veriyi ezmesin.
    let active = true;

    getir(sekme)
      .then((sonuc) => {
        if (active) setYuklenen({ tab: sekme, key: tazele, rows: sonuc });
      })
      .catch((error) => {
        if (!active) return;
        showToast(error.message, 'error');
        setYuklenen({ tab: sekme, key: tazele, rows: [] });
      });

    return () => {
      active = false;
    };
  }, [sekme, tazele, getir, showToast]);

  const oturumSonlandir = async (familyId, kullanici) => {
    try {
      await api.adminRevokeSession(familyId);
      showToast(`${kullanici} kullanıcısının oturumu sonlandırıldı.`, 'success');
      setTazele((n) => n + 1);
    } catch (error) {
      showToast(error.message, 'error');
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 p-4 sm:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto">
        <Header
          username={username}
          isAdmin
          view={view}
          onViewChange={onViewChange}
          onLogout={onLogout}
        />

        <div className="flex flex-col sm:flex-row gap-2 bg-white border border-slate-200 p-1.5 rounded-2xl w-full sm:w-fit shadow-sm mb-6">
          {SEKMELER.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setSekme(s.key)}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-colors ${
                sekme === s.key
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-5 sm:p-6 shadow-sm">
          {yukleniyor ? (
            <div className="flex items-center justify-center gap-2 py-12 text-slate-400 text-sm">
              <SpinnerIcon className="w-4 h-4" />
              Yükleniyor...
            </div>
          ) : !satirlar?.length ? (
            <p className="text-slate-400 text-sm py-12 text-center">Kayıt bulunamadı.</p>
          ) : (
            <div className="overflow-x-auto">
              {sekme === 'users' && <Kullanicilar satirlar={satirlar} />}
              {sekme === 'sessions' && (
                <Oturumlar satirlar={satirlar} onSonlandir={oturumSonlandir} />
              )}
              {sekme === 'events' && <Olaylar satirlar={satirlar} />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const baslikSinifi =
  'text-left text-[11px] font-bold text-slate-500 uppercase tracking-wider pb-3 px-3 whitespace-nowrap';
const hucreSinifi = 'py-3 px-3 text-sm text-slate-700 whitespace-nowrap';

function Kullanicilar({ satirlar }) {
  return (
    <table className="w-full min-w-[640px]">
      <thead>
        <tr className="border-b border-slate-200">
          <th className={baslikSinifi}>Kullanıcı</th>
          <th className={baslikSinifi}>E-posta</th>
          <th className={baslikSinifi}>Kayıt</th>
          <th className={baslikSinifi}>Giriş</th>
          <th className={baslikSinifi}>Görev</th>
          <th className={baslikSinifi}>Rol</th>
        </tr>
      </thead>
      <tbody>
        {satirlar.map((k) => (
          <tr key={k.id} className="border-b border-slate-50 hover:bg-slate-50/60">
            <td className={`${hucreSinifi} font-semibold text-slate-900`}>{k.username}</td>
            <td className={`${hucreSinifi} text-slate-500`}>{k.email}</td>
            <td className={hucreSinifi}>{zaman(k.created_at)}</td>
            <td className={hucreSinifi}>{k.session_count}</td>
            <td className={hucreSinifi}>{k.task_count}</td>
            <td className={hucreSinifi}>
              {k.is_admin ? (
                <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded">
                  YÖNETİCİ
                </span>
              ) : (
                <span className="text-xs text-slate-400">kullanıcı</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Oturumlar({ satirlar, onSonlandir }) {
  return (
    <table className="w-full min-w-[720px]">
      <thead>
        <tr className="border-b border-slate-200">
          <th className={baslikSinifi}>Kullanıcı</th>
          <th className={baslikSinifi}>Oturum</th>
          <th className={baslikSinifi}>Başlangıç</th>
          <th className={baslikSinifi}>Son kullanım</th>
          <th className={baslikSinifi}>Durum</th>
          <th className={baslikSinifi} />
        </tr>
      </thead>
      <tbody>
        {satirlar.map((o) => (
          <tr key={o.family_id} className="border-b border-slate-50 hover:bg-slate-50/60">
            <td className={`${hucreSinifi} font-semibold text-slate-900`}>{o.username}</td>
            <td className={`${hucreSinifi} font-mono text-xs text-slate-400`}>
              {o.family_id.slice(0, 8)}
            </td>
            <td className={hucreSinifi}>{zaman(o.started_at)}</td>
            <td className={hucreSinifi}>{zaman(o.last_used_at)}</td>
            <td className={hucreSinifi}>
              {o.revoked ? (
                <span className="text-xs text-slate-400">iptal edildi</span>
              ) : o.active ? (
                <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-1 rounded">
                  AKTİF
                </span>
              ) : (
                <span className="text-xs text-slate-400">süresi doldu</span>
              )}
            </td>
            <td className={hucreSinifi}>
              {!o.revoked && o.active && (
                <button
                  type="button"
                  onClick={() => onSonlandir(o.family_id, o.username)}
                  className="bg-red-50 hover:bg-red-500 text-red-500 hover:text-white px-3 py-1.5 text-xs font-medium rounded-xl transition-colors border border-red-100"
                >
                  Sonlandır
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Olaylar({ satirlar }) {
  return (
    <table className="w-full min-w-[680px]">
      <thead>
        <tr className="border-b border-slate-200">
          <th className={baslikSinifi}>Zaman</th>
          <th className={baslikSinifi}>Kullanıcı</th>
          <th className={baslikSinifi}>Olay</th>
          <th className={baslikSinifi}>IP</th>
          <th className={baslikSinifi}>Sonuç</th>
        </tr>
      </thead>
      <tbody>
        {satirlar.map((o) => (
          <tr
            key={o.id}
            className={`border-b border-slate-50 ${
              o.event === 'token_reuse' ? 'bg-red-50/60' : 'hover:bg-slate-50/60'
            }`}
          >
            <td className={`${hucreSinifi} text-slate-500`}>{zaman(o.created_at)}</td>
            <td className={`${hucreSinifi} font-semibold text-slate-900`}>{o.username}</td>
            <td className={hucreSinifi}>
              <span
                className={
                  o.event === 'token_reuse' ? 'text-red-600 font-bold text-xs' : 'text-xs'
                }
              >
                {OLAY_ETIKETLERI[o.event] ?? o.event}
              </span>
            </td>
            <td className={`${hucreSinifi} font-mono text-xs text-slate-400`}>
              {o.ip_address ?? '—'}
            </td>
            <td className={hucreSinifi}>
              {o.success ? (
                <span className="text-emerald-600 text-xs">başarılı</span>
              ) : (
                <span className="text-[10px] font-bold text-red-600 bg-red-50 px-2 py-1 rounded">
                  BAŞARISIZ
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
