/**
 * Backend ile tüm iletişim bu dosyadan geçer.
 *
 * Oturum modeli:
 *  - **Access token** bellekte tutulur (localStorage'da değil). Sayfa
 *    yenilenince kaybolur; bu kasıtlıdır — XSS ile çalınamaz.
 *  - **Refresh token** httpOnly çerezdedir; JavaScript onu hiç görmez.
 *    Tarayıcı çerezi otomatik gönderir, biz dokunmayız.
 *
 * Access token süresi dolduğunda (401) sessizce yenilenir ve asıl istek
 * bir kez tekrarlanır; kullanıcı hiçbir şey fark etmez.
 */

// Tarayıcıda çalıştığı için compose ağı (http://backend:8000) kullanılamaz;
// adres .env üzerinden host portu olarak verilir.
const API_URL =
  import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;

let accessToken = null;
let onSessionLost = () => {};

export function setAccessToken(token) {
  accessToken = token ?? null;
}

export function setSessionLostHandler(handler) {
  onSessionLost = handler;
}

/**
 * Backend'in standart hata gövdesini okunabilir bir mesaja çevirir.
 * FastAPI doğrulama hatalarında `detail` bir dizi olarak gelir.
 */
function readErrorMessage(body) {
  if (!body || body.detail === undefined) return null;
  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail))
    return body.detail.map((item) => cleanValidationMessage(item.msg)).join(' · ');
  return null;
}

/**
 * Pydantic kendi Türkçe mesajlarımızın başına İngilizce bir etiket ekler
 * ("Value error, Şifre en az 8 karakter olmalıdır."). Kullanıcıya yalnızca
 * bizim yazdığımız kısım gösterilir.
 */
function cleanValidationMessage(message) {
  return (message ?? '').replace(/^Value error,\s*/, '');
}

async function readError(response) {
  try {
    return readErrorMessage(await response.json()) || 'Beklenmeyen bir hata oluştu.';
  } catch {
    return 'Beklenmeyen bir hata oluştu.';
  }
}

async function send(path, options = {}) {
  try {
    return await fetch(`${API_URL}${path}`, {
      ...options,
      // Refresh çerezinin gidebilmesi için şart.
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error('Sunucuya bağlanılamadı. Backend çalışıyor mu?');
  }
}

/**
 * Çerezdeki refresh token ile yeni bir access token alır.
 * Aynı anda birden fazla istek 401 alırsa tek bir yenileme yapılır.
 */
let refreshInFlight = null;

function refreshAccessToken() {
  refreshInFlight ??= (async () => {
    try {
      const response = await send('/auth/refresh', { method: 'POST' });
      if (!response.ok) return false;

      const session = await response.json();
      setAccessToken(session.access_token);
      return session;
    } catch {
      return false;
    } finally {
      // Bir sonraki 401 yeniden denesin diye kilit bırakılır.
      setTimeout(() => {
        refreshInFlight = null;
      }, 0);
    }
  })();

  return refreshInFlight;
}

async function request(path, options = {}, { retry = true } = {}) {
  let response = await send(path, options);

  // Access token süresi dolmuş olabilir: bir kez yenileyip tekrar dene.
  if (response.status === 401 && retry && !path.startsWith('/auth/refresh')) {
    const yenilendi = await refreshAccessToken();
    if (!yenilendi) {
      setAccessToken(null);
      onSessionLost();
      throw new Error(await readError(response));
    }
    response = await send(path, options);
  }

  if (!response.ok) {
    if (response.status === 401) {
      setAccessToken(null);
      onSessionLost();
    }
    throw new Error(await readError(response));
  }

  return response.status === 204 ? null : response.json();
}

/** Listeleme: gövdeye ek olarak toplam kayıt sayısını da döner. */
async function requestPage(path) {
  let response = await send(path);

  if (response.status === 401) {
    const yenilendi = await refreshAccessToken();
    if (!yenilendi) {
      setAccessToken(null);
      onSessionLost();
      throw new Error(await readError(response));
    }
    response = await send(path);
  }

  if (!response.ok) throw new Error(await readError(response));

  const items = await response.json();
  const header = Number(response.headers.get('X-Total-Count'));
  return { items, total: Number.isFinite(header) && header >= 0 ? header : items.length };
}

const json = (method, body) => ({ method, body: JSON.stringify(body) });

export const api = {
  register: (data) => request('/auth/register', json('POST', data)),
  login: (data) => request('/auth/login', json('POST', data), { retry: false }),
  logout: () => request('/auth/logout', { method: 'POST' }, { retry: false }),

  /** Sayfa yüklenirken çağrılır: geçerli çerez varsa oturumu geri getirir. */
  restore: async () => {
    const session = await refreshAccessToken();
    return session || null;
  },

  // --- Yönetim (yalnızca yetkili kullanıcı; sunucu her istekte denetler) ---
  adminUsers: () => request('/admin/users'),
  adminSessions: () => request('/admin/sessions'),
  adminEvents: (limit = 50) => request(`/admin/events?limit=${limit}`),
  adminRevokeSession: (familyId) =>
    request(`/admin/sessions/${familyId}`, { method: 'DELETE' }),

  listTasks: (source, { limit, offset }) =>
    requestPage(`/tasks?db_source=${source}&limit=${limit}&offset=${offset}`),
  createTask: (data) => request('/tasks', json('POST', data)),
  updateTask: (id, data) => request(`/tasks/${id}`, json('PUT', data)),
  deleteTask: (id, target) =>
    request(`/tasks/${id}?db_target=${target}`, { method: 'DELETE' }),
};
