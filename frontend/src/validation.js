/**
 * Form doğrulama kuralları.
 *
 * Kurallar backend'deki Pydantic kısıtlarıyla birebir aynıdır
 * (schemas.py). Böylece kullanıcı hatayı sunucuya gitmeden,
 * yazarken anında görür.
 *
 * Her kural hatalıysa mesaj, geçerliyse boş metin döner.
 */

export const validators = {
  username(value) {
    const text = (value ?? '').trim();
    if (!text) return 'Kullanıcı adı boş bırakılamaz.';
    if (text.length < 3) return 'Kullanıcı adı en az 3 karakter olmalıdır.';
    if (text.length > 50) return 'Kullanıcı adı en fazla 50 karakter olabilir.';
    return '';
  },

  email(value) {
    const text = (value ?? '').trim();
    if (!text) return 'E-posta adresi boş bırakılamaz.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text))
      return 'Geçerli bir e-posta adresi giriniz.';
    return '';
  },

  password(value) {
    const text = value ?? '';
    if (!text) return 'Şifre boş bırakılamaz.';
    if (text.length < 8) return 'Şifre en az 8 karakter olmalıdır.';
    // \p{Lu} Unicode büyük harf sınıfıdır: Ş, Ğ, İ gibi Türkçe harfleri de
    // kapsar. [A-Z] kullanılsaydı yalnızca Türkçe harfli geçerli bir şifre
    // burada reddedilir, sunucuda kabul edilirdi.
    if (!/\p{Lu}/u.test(text)) return 'Şifre en az bir büyük harf içermelidir.';
    return '';
  },

  // Girişte uzunluk kontrolü yapılmaz; yalnızca boş olmaması yeterlidir.
  loginPassword(value) {
    return (value ?? '') ? '' : 'Şifre boş bırakılamaz.';
  },

  title(value) {
    const text = (value ?? '').trim();
    if (!text) return 'Görev başlığı boş bırakılamaz.';
    if (text.length < 3) return 'Görev başlığı en az 3 karakter olmalıdır.';
    if (text.length > 100) return 'Görev başlığı en fazla 100 karakter olabilir.';
    return '';
  },
};

/**
 * Bir form nesnesini alan-kural eşlemesine göre doğrular.
 * Hata bulunan alanların adlarını ve mesajlarını döner.
 */
export function validateForm(values, fieldRules) {
  const errors = {};
  for (const [field, rule] of Object.entries(fieldRules)) {
    const message = rule(values[field]);
    if (message) errors[field] = message;
  }
  return errors;
}
