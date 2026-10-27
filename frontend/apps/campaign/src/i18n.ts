/** The form speaks English or Indonesian; the visitor can switch (owner decision 2026-10-26). */
export type Lang = "en" | "id";

const STRINGS = {
  en: {
    switchTo: "Bahasa Indonesia",
    switchLabel: "Ganti ke Bahasa Indonesia",
    title: "Visitor Registration",
    intro: "Register to visit. Your entry QR code is sent to you after we confirm your details.",
    firstName: "Full Name",
    email: "Email",
    phone: "Phone / WhatsApp",
    contactHint: "Fill in your email or phone number (or both).",
    company: "Company",
    jobTitle: "Job Title",
    country: "Country",
    chooseCountry: "Choose a country",
    city: "City",
    choose: "Choose",
    yes: "Yes",
    optional: "optional",
    required: "Required.",
    needContact: "Enter your email or phone number.",
    consent:
      "I agree that the organizer stores and uses my details to manage my registration and to contact me about this event, and that visits to this page are measured for marketing.",
    needConsent: "Tick the box to agree.",
    submit: "Register",
    sending: "Sending",
    fixErrors: "Check the fields marked below.",
    tooMany: "Too many attempts from this network. Try again in an hour.",
    failed: "Your registration could not be sent. Check your connection and try again.",
    loading: "Loading the form",
    doneTitle: "Thank you",
    done: "We have received your registration. If your details are complete, our team will send your entry QR code by email.",
    closedTitle: "Registration closed",
    closed: "This registration form is no longer open. Contact the organizer if you need help.",
    dates: (start: string, end: string) => `${start} to ${end}`,
  },
  id: {
    switchTo: "English",
    switchLabel: "Switch to English",
    title: "Pendaftaran Pengunjung",
    intro: "Daftar untuk berkunjung. QR code masuk dikirim setelah data Anda kami konfirmasi.",
    firstName: "Nama Lengkap",
    email: "Email",
    phone: "Nomor HP / WhatsApp",
    contactHint: "Isi email atau nomor HP Anda (boleh keduanya).",
    company: "Perusahaan",
    jobTitle: "Jabatan",
    country: "Negara",
    chooseCountry: "Pilih negara",
    city: "Kota",
    choose: "Pilih",
    yes: "Ya",
    optional: "opsional",
    required: "Wajib diisi.",
    needContact: "Isi email atau nomor HP Anda.",
    consent:
      "Saya setuju data saya disimpan dan digunakan penyelenggara untuk mengelola pendaftaran saya dan menghubungi saya tentang acara ini, serta kunjungan ke halaman ini diukur untuk keperluan pemasaran.",
    needConsent: "Centang kotak ini untuk menyetujui.",
    submit: "Daftar",
    sending: "Mengirim",
    fixErrors: "Periksa isian yang ditandai di bawah.",
    tooMany: "Terlalu banyak percobaan dari jaringan ini. Coba lagi dalam satu jam.",
    failed: "Pendaftaran gagal dikirim. Periksa koneksi Anda lalu coba lagi.",
    loading: "Memuat formulir",
    doneTitle: "Terima kasih",
    done: "Pendaftaran Anda sudah kami terima. Jika data Anda lengkap, tim kami akan mengirim QR code masuk lewat email.",
    closedTitle: "Pendaftaran ditutup",
    closed: "Formulir pendaftaran ini sudah tidak dibuka. Hubungi penyelenggara jika butuh bantuan.",
    dates: (start: string, end: string) => `${start} sampai ${end}`,
  },
} satisfies Record<Lang, Record<string, string | ((a: string, b: string) => string)>>;

export type Strings = (typeof STRINGS)["en"];

export const strings = (lang: Lang): Strings => STRINGS[lang];

const KEY = "ems.campaign.lang";

/** Saved choice, else the browser language (Indonesian for id-*), else English. */
export function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "en" || saved === "id") return saved;
  } catch {
    /* storage blocked: fall back to the browser language */
  }
  return navigator.language.toLowerCase().startsWith("id") ? "id" : "en";
}

export function saveLang(lang: Lang): void {
  try {
    localStorage.setItem(KEY, lang);
  } catch {
    /* not kept; the form still works */
  }
}

export function formatDate(iso: string, lang: Lang): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y!, m! - 1, d!)).toLocaleDateString(lang === "id" ? "id-ID" : "en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}
