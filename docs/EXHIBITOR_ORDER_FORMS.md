# Exhibitor Order Forms

**Status:** Rancangan disetujui; semua keputusan (O1–O12) dijawab owner 2026-11-09 · **Ditulis:** 2026-11-09 · **Author:** Fikri Darmawan

Dokumen kerja untuk fitur ini. AI/developer yang melanjutkan: baca dokumen ini, lalu
`docs/EXHIBITOR_LEADS_SALES_PIPELINE.md` (fitur exhibitor yang sudah ada), lalu `BACKEND_RULES/`
(aturan wajib), lalu centang task di bawah begitu selesai. Yang masih ditunggu dari owner hanya
katalog dan harga (Phase 0); Phase 1 bisa dimulai tanpa itu.

---

## Ringkasan

Begitu menjadi exhibitor (setelah Convert), exhibitor memesan layanan untuk booth-nya lewat
portal: listrik, furnitur, air, internet, parkir, badge, iklan, listing e-directory, dan lain-lain.
Di sistem lama (Laravel, `Peraga_OEM_2026_Pack/Source Codes/OEM WEB`) ini adalah 14 "Order Forms".

```
Convert (akun portal aktif) → portal: daftar Order Forms → isi form (draft) → submit
  → staff review → Approved (form berharga: setelah contract SIGNED) → payment (termin, diverifikasi staff)
```

- **Satu modul generik, bukan 14 tabel.** Semua form memakai tabel yang sama. Form berharga
  memakai katalog item yang diatur staff per edition; form isian memakai skema field per jenis form
  yang didefinisikan di kode.
- **Harga dan total selalu dihitung di server.** Browser hanya mengirim `item_id` + jumlah.
- **Status tidak dicampur** (aturan #9): status order, status per form, dan payment terpisah.

### Scope

Spec §1.2/§18 menaruh "the twelve exhibitor forms" di luar phase 1. Owner membukanya pada
2026-11-09 (O1), sama seperti fitur exhibitor sales pada 2026-11-03. Proposal, invoice formal,
refund, credit note, dan payment gateway tetap di luar scope.

---

## Pelajaran dari sistem lama

Dari analisa 2026-11-09. Sistem lama dipakai sebagai contoh tampilan dan isi form, **bukan** contoh
kode.

| Ditiru | Tidak ditiru (masalah di sistem lama) |
|---|---|
| Daftar "All Forms" dengan deadline, sisa waktu, status, filter | Status dan deadline di sidebar ditulis di kode (contoh "Saved 14 December 2025") |
| Katalog item per section (A. Lighting, B. Power, ...) dengan gambar, ukuran, harga, qty | Harga ditulis di HTML (`data-price`), total dihitung di browser, admin membuat invoice dari angka kiriman browser |
| Ringkasan pesanan (subtotal, total) sebelum submit | Exhibitor bisa mengirim `status=approved` sendiri |
| Save draft / Submit, catatan (remarks) | Setiap Save membuat baris baru; draft tidak bisa dibuka lagi |
| "I don't require this form" | "Additional Equipment": exhibitor mengetik **harga sendiri** |
| Data perusahaan terisi otomatis | Upload file hanya simulasi (`setTimeout`) |
| Jatah gratis per luas booth (badge, parking pass) | Tidak ada approve/reject di admin; `exhibition_id` tidak pernah terisi |

---

## Keputusan owner

### Sudah dijawab (2026-11-09)

| # | Keputusan | Jawaban |
|---|---|---|
| O1 | Order Forms masuk scope | Ya, sebagai slice baru seperti 2026-11-03 |
| O2 | Kapan exhibitor bisa mengisi | **Langsung setelah Convert**, tanpa menunggu contract `SIGNED`. Aturannya ada di bagian **Mengisi sebelum contract SIGNED** |
| O3 | Pesanan dibayar lewat sistem | Ya: payment tagging untuk order (termin, bukti bayar, verifikasi staff), aturan sama seperti payment contract. Lihat Phase 7 |

### Default disetujui (2026-11-09)

Owner menyetujui semua usulan default di bawah tanpa perubahan.

| # | Keputusan | Jawaban |
|---|---|---|
| O4 | Harga per periode | Item punya harga Regular, Surcharge, dan Onsite (dua terakhir opsional, kosong = pakai Regular). Periode dipilih dari tanggal submit, memakai `price_*_from/to` edition yang sudah ada (zona waktu edition) |
| O5 | Pajak (PPN) | Harga di katalog sudah final; tidak ada hitungan pajak (invoice di luar scope) |
| O6 | Item di luar katalog ("Additional Equipment") | Exhibitor menulis nama, ukuran, jumlah, dan gambar **tanpa harga**; staff mengisi harga saat review. Exhibitor melihat harga setelah Approved |
| O7 | Mengubah pesanan | Satu draft terbuka per form. Setelah submit terkunci; staff bisa mengembalikan (Returned) dengan alasan. Pesanan tambahan setelah Approved = order baru untuk form yang sama. Order Approved tidak bisa diubah; kalau salah, staff Cancel lalu exhibitor membuat order baru |
| O8 | Lewat deadline | Tiap form punya `deadline_on` (ditampilkan, dengan hitung mundur) dan `closes_on` (setelah tanggal ini submit ditolak; default `order_expired_on` edition). Antara keduanya masih bisa submit dengan harga periode yang berlaku |
| O9 | Jatah gratis (badge, parking) | Aturan per form: rentang luas booth → jumlah gratis. Jatah gratis mengurangi jumlah yang ditagih. Dibangun di Phase 6 |
| O10 | Field form isian (01, 02a, 08, 08a, 09, 10) | Didefinisikan di kode per jenis form (skema Pydantic), bukan form builder di desk. Pilihan seperti kategori produk dan daftar forwarder resmi tetap bisa diatur sebagai opsi per edition |
| O11 | Notifikasi | Belum ada email; status terlihat di portal dan desk. Email Approved/Returned bisa ditambah lewat `mail.service.queue_email` |
| O12 | Siapa yang review | Permission baru `exhibitor_order.review` (Super Admin + Exhibition Admin), bisa diberikan ke tim operasional lewat custom role |

---

## Mengisi sebelum contract SIGNED (O2)

Selama contract masih `DRAFT`, booth exhibitor masih bisa dipindah staff (lihat pipeline Phase 3–4),
padahal luas booth menentukan fasilitas standard booth (form 03) dan jatah gratis (form 09, 12).
Aturannya:

1. **Portal Order Forms terbuka** untuk lead stage `EXHIBITOR` dengan akun portal aktif, apa pun
   status contract-nya. Exhibitor bisa membuat draft dan submit.
2. **Approve form berharga butuh contract `SIGNED`.** Order dengan total > 0 baru bisa di-Approve
   setelah contract `SIGNED` (422 `CONTRACT_NOT_SIGNED`), sehingga tagihan baru muncul setelah booth
   pasti. Order bertotal 0 (form isian murni seperti 01, 08, 10) boleh di-Approve kapan saja.
   Portal menampilkan "Waiting for your signed contract" pada order seperti ini.
3. **Order mencatat booth saat submit** (`booth_id_at_submit`, `area_sqm_at_submit`). Jatah gratis
   dihitung dari luas itu. Kalau booth sudah berbeda saat staff membuka order `SUBMITTED`, halaman
   review menampilkan peringatan "Booth changed since submit"; staff mengembalikan order (Returned)
   supaya exhibitor submit ulang dengan luas yang baru.
4. **Pindah booth tidak mengubah order secara otomatis.** Order `APPROVED` tetap; kalau isinya tidak
   cocok lagi, staff Cancel (aturan payment di Phase 7 berlaku) dan exhibitor memesan ulang.
5. **Reopen contract** (F8) tidak menyentuh order. Order yang belum Approved hanya tertahan lagi di
   aturan 2 sampai contract `SIGNED` kembali.

---

## Jenis form

Setiap form adalah gabungan dari bagian-bagian berikut. Bagian mana yang aktif diatur per form.

| Bagian | Isi | Dipakai form |
|---|---|---|
| Katalog | Item dari `order_form_items`, exhibitor mengisi jumlah | 02, 03, 04, 05, 06, 07, 11, 12 |
| Item tambahan | Baris bebas tanpa harga (O6) + gambar | 04, 05, 06, 07 |
| Isian | Field terstruktur, divalidasi skema di kode (`details_type`) | 01, 02, 02a, 03, 08, 08a, 09, 10, 11 |
| Lampiran | File dengan tujuan tertentu (logo, denah titik listrik, daftar visa) | 02, 02a, 04, 05, 06, 09 |
| Jatah gratis | Jumlah gratis dari luas booth | 09, 12 |

Daftar 14 form dan pemetaannya ada di **Lampiran A**.

---

## Status

| Di mana | Kolom | Nilai |
|---|---|---|
| `exhibitor_orders` | `status` | `DRAFT`, `SUBMITTED`, `RETURNED`, `APPROVED`, `CANCELLED` |
| `exhibitor_orders` | `price_period` (diisi saat submit) | `REGULAR`, `SURCHARGE`, `ONSITE` |
| dihitung, tidak disimpan | progres per form per exhibitor | `NOT_STARTED`, `IN_PROGRESS` (ada draft/returned), `SUBMITTED`, `APPROVED`, `NOT_REQUIRED` |
| `exhibitor_payments` (dengan `order_id`) | `status` per pembayaran | `PENDING`, `VERIFIED`, `REJECTED` (sama seperti payment contract) |
| dihitung, tidak disimpan | payment state per order `APPROVED` | `UNPAID`, `PARTIAL`, `PAID` (total `VERIFIED` vs `total`) |

Perpindahan status order (`app/modules/orders/rules.py` `ORDER_TRANSITIONS`):

| Dari | Ke | Oleh | Syarat |
|---|---|---|---|
| `DRAFT` | `SUBMITTED` | exhibitor | Lolos validasi; sebelum `closes_on`; harga dan periode disalin ke baris |
| `DRAFT` | (dihapus) | exhibitor | Draft boleh dihapus; tidak ada baris lain yang terhapus |
| `SUBMITTED` | `APPROVED` | staff `exhibitor_order.review` | Semua baris item tambahan sudah punya harga; kalau total > 0, contract `SIGNED` (O2) |
| `SUBMITTED` | `RETURNED` | staff | Alasan wajib |
| `RETURNED` | `SUBMITTED` | exhibitor | Sama seperti submit pertama (harga dihitung ulang dari tanggal submit baru) |
| `SUBMITTED`, `RETURNED`, `APPROVED` | `CANCELLED` | staff | Alasan wajib; diblok kalau ada payment `VERIFIED` (tidak bisa) atau `PENDING` (tolak dulu), sama seperti reopen contract |

`NOT_REQUIRED` disimpan di tabel sendiri (`exhibitor_form_waivers`), bukan sebagai status order,
dan hanya boleh selama form itu tidak punya order `SUBMITTED`/`APPROVED`.

Semua perpindahan dicatat di `audit_logs` (entity `exhibitor_order`, source `PORTAL` untuk aksi
exhibitor), tidak ada tabel history baru.

---

## Database (modul baru `app/modules/orders/`, migration mulai `0030`)

Semua tabel per edition (`edition_id NOT NULL`), punya `created_by`/`updated_by`, `version`, uang
`NUMERIC(14,2)` + `currency`, sama seperti modul `exhibitors`.

### `order_forms` (pengaturan form per edition)
`code` (`01`, `02a`, ...; unik per edition), `title`, `details_type` (nama skema di kode atau
NULL), `has_catalog`, `allow_custom_items`, `attachment_purposes` (array), `deadline_on`,
`closes_on`, `secondary_deadline_label` + `secondary_deadline_on` (form 02: Booking dan Material
Deadline), `instructions` (teks catatan dan syarat), `currency`, `sort_order`, `is_published`.
Form yang belum `is_published` tidak terlihat di portal.

### `order_form_items` (katalog)
`form_id`, `section` (contoh "A. Lighting & Equipment"), `code` (unik per form), `name`,
`description`, `size`, `unit`, `image_key`, `price_regular`, `price_surcharge`, `price_onsite`
(dua terakhir NULL = pakai regular), `max_quantity`, `is_active`, `sort_order`. Item tidak dihapus,
hanya dinonaktifkan, karena baris order lama menunjuk ke sana.

### `order_form_allowances` (Phase 6)
Dibangun di migration `0033`: `item_id` (selalu per item katalog), `min_area_sqm`, `free_quantity`; satu
baris per tingkatan, unik per (item, luas). Exhibitor mendapat tingkatan dengan `min_area_sqm` terbesar
yang dicapai booth-nya ("mulai 18 m²: 2 gratis"), lebih jelas daripada "< 9 m²" di sistem lama yang ambigu
untuk booth tepat 9 m². Luas diambil dari `booths.area_sqm`.

### `exhibitor_orders`
`exhibitor_lead_id`, `form_id`, `order_number` (`<kode edition>-O-0001`, counter
`exhibitor_order_counters` per edition, diberikan saat submit pertama supaya draft yang dihapus
tidak meninggalkan lubang), `status`, `price_period`, `details` (JSONB, divalidasi skema
`details_type`; pengecualian JSONB dicatat di `BACKEND_RULES/database.md`), `remarks`, `total`
(jumlah baris yang sudah berharga, dijaga oleh service; tidak ada `subtotal` karena tidak ada pajak
atau diskon, O5), `currency`, `submitted_at`, `submitted_by_account_id`, `booth_id_at_submit`,
`area_sqm_at_submit` (O2), `reviewed_by`, `reviewed_at`, `review_notes`, `cancel_reason`.

Constraint di database:
- satu order terbuka (`DRAFT`/`RETURNED`) per (lead, form): partial unique index;
- lead dan form dari edition yang sama (FK `(exhibitor_lead_id, edition_id)` dan
  `(form_id, edition_id)`; migration 0030 menambah `uq_exhibitor_leads_id_edition`);
- nomor, `submitted_at`, `price_period`, dan booth saat submit terisi tepat ketika status bukan `DRAFT`;
  `reviewed_*` wajib untuk `APPROVED`/`RETURNED`; `RETURNED` wajib alasan; `CANCELLED` wajib alasan.

Lead harus stage `EXHIBITOR` dicek di service (stage ada di tabel lain, jadi tidak bisa jadi CHECK).

Baris (`exhibitor_order_lines`) dan file tidak punya `created_by`/`updated_by`: keduanya ditulis
bersama order di bawah `version` order, jadi siapa dan kapan ada di order dan audit log.

### `exhibitor_order_lines`
`order_id`, `item_id` (NULL = item tambahan), salinan `code`, `name`, `size`, `section`,
`quantity` (> 0), `free_quantity` (≥ 0, ≤ quantity), `unit_price` (NULL hanya untuk item tambahan
sebelum staff mengisi harga), `amount` (= (quantity − free_quantity) × unit_price), `image_key`
(item tambahan), `notes`. Selama `DRAFT` harga di baris hanya perkiraan; saat submit server menyalin
harga sesuai periode, dan setelah itu tidak berubah.

### `exhibitor_order_files`
`order_id`, `purpose` (`LOGO`, `PRODUCT_IMAGE`, `FITTING_LOCATION`, `VISA_LIST`, `OTHER`),
`file_key`, `file_name`, `content_type`, `size_bytes`. Bucket baru `orders`
(`EMS_S3_BUCKET_ORDERS`, dibuat oleh `python -m app.cli ensure-buckets`).

### `exhibitor_form_waivers`
`exhibitor_lead_id`, `form_id`, `waived_at`, `waived_by_account_id`. Unik per (lead, form).

---

## Aturan backend khusus fitur ini

- Setiap query filter `edition_id` + scope user (`Scope`); di portal, lead harus milik akun yang login
  (lead lain = 404), sama seperti contract.
- Body dari portal **tidak pernah** berisi harga, total, status, atau `price_period`. Field yang tidak
  dikenal ditolak (`extra="forbid"`).
- Periode harga dihitung dari tanggal submit di zona waktu edition. Tanggal di luar semua periode
  (atau edition tanpa periode Regular) ditolak dengan 422 `ORDERING_NOT_OPEN`; server tidak menebak
  harga.
- Submit setelah `closes_on` → 422 `FORM_CLOSED`. Edition `ARCHIVED` → read-only seperti modul lain.
- Approve mengunci baris order (`SELECT ... FOR UPDATE`) dan memeriksa `version`.
- Upload: cek ekstensi, MIME, dan isi file; gambar JPG/PNG maks 5 MB, dokumen PDF/XLSX maks 10 MB;
  key acak; unduh lewat API, sama seperti contract.
- Item tambahan dibatasi (misalnya 20 baris per order) dan teksnya dibatasi panjangnya.
- Permission baru: `order_form.manage` (atur form dan katalog), `exhibitor_order.review` (approve,
  return, cancel, isi harga item tambahan). Membaca order memakai `exhibitor_lead.read` dan scope lead.

---

## API (usulan)

URL mengikuti pola project: flat, `edition_id` di query/body.

**Staff: pengaturan**
- `GET/POST /api/v1/order-forms?edition_id=`, `PATCH /api/v1/order-forms/{id}` (`order_form.manage`)
- `GET/POST /api/v1/order-forms/{id}/items`, `PATCH .../items/{item_id}`, `POST .../items/{item_id}/image`
- `POST /api/v1/order-forms/copy` `{from_edition_id, to_edition_id}`: salin form dan katalog dari edition
  sebelumnya (tanggal dikosongkan), supaya staff tidak mengetik ulang ratusan item
- `POST /api/v1/order-forms/{id}/items/import` (xlsx) dan `GET /api/v1/order-forms/item-import-template`:
  import katalog dari Excel, dipakai juga untuk memindahkan harga dari sistem lama satu kali
- `GET /api/v1/order-forms/{id}/items/{item_id}/image`: gambar item (portal mendapat endpoint sendiri di Phase 3)

**Staff: review**
- `GET /api/v1/exhibitor-orders?edition_id=&form_id=&status=&q=` (antrian review)
- `GET /api/v1/exhibitor-orders/{id}`
- `PATCH /api/v1/exhibitor-orders/{id}/lines/{line_id}` `{unit_price, version}` (harga item tambahan, hanya `SUBMITTED`)
- `POST /api/v1/exhibitor-orders/{id}/review` `{decision: APPROVED|RETURNED, notes, version}`
- `POST /api/v1/exhibitor-orders/{id}/cancel` `{reason, version}`
- `GET /api/v1/exhibitor-leads/{id}/orders`: semua order dan progres per form untuk satu exhibitor
- `GET /api/v1/exhibitor-orders/export?edition_id=&form_id=&status=`: export per form (xlsx), contoh rekap furnitur untuk kontraktor
- `GET /api/v1/exhibitor-orders/{id}/files/{file_id}` dan `.../lines/{line_id}/image`: lampiran dan gambar item tambahan

**Portal** (`/api/v1/portal/exhibitors/{lead_id}/...`)
- `GET .../order-forms`: daftar form `is_published` dengan deadline, progres, jumlah order
- `GET .../order-forms/{code}`: form, katalog dengan harga periode sekarang, jatah gratis, isian dan draft yang ada
- `POST .../order-forms/{code}/orders` (buat draft), `PATCH .../orders/{order_id}` `{lines: [{item_id, quantity}], custom_lines, details, remarks, version}`
- `POST .../orders/{order_id}/quote`: ringkasan total dari server (dipakai halaman Review)
- `POST .../orders/{order_id}/submit` `{version}`, `DELETE .../orders/{order_id}` (hanya draft)
- `POST .../orders/{order_id}/files` (multipart `file` + `purpose` + `version`), `DELETE .../files/{file_id}?version=`, `GET .../files/{file_id}` (hanya draft/returned untuk menambah dan menghapus)
- `POST/GET .../orders/{order_id}/lines/{line_id}/image` (gambar item tambahan), `GET .../order-forms/{code}/items/{item_id}/image` (gambar katalog)
- `PUT/DELETE .../order-forms/{code}/not-required`

---

## Frontend

**Portal (`apps/exhibitor`)**
- Halaman exhibition mendapat bagian **Order Forms** (progres "3 / 14 submitted").
- Halaman daftar form: nomor, judul, deadline, sisa waktu, status, aksi; filter All / Not Filled / In Progress / Submitted.
- Halaman form: data perusahaan dari contract (read-only), tabel katalog per section dengan input jumlah,
  item tambahan, isian, lampiran, remarks, "I don't require this form", Save Draft.
- Halaman Review & Submit (halaman, bukan modal, sesuai DESIGN.md): ringkasan dari endpoint `quote`.
- Order yang Returned menampilkan alasan dari staff di atas form.
- Portal memakai router kecilnya sendiri (`exhibitorRouteOf` di `lib.ts`); lihat catatan Phase 3.

**Desk (`apps/web`, menu Exhibitors)**
- **Order Forms** (`order_form.manage`): daftar form per edition, edit form (judul, tanggal, instruksi,
  publish), katalog item per form, Copy from Edition.
- **Orders** (`exhibitor_lead.read`): antrian dengan filter form/status, halaman order (baris, isian,
  lampiran, isi harga item tambahan, Approve / Return / Cancel).
- Halaman lead exhibitor mendapat tab **Orders** (progres 14 form + daftar order).

---

## Implementation Tasks

### Phase 0: Keputusan
- [x] Owner menjawab O1 (masuk scope), O2 (langsung setelah Convert), O3 (bayar lewat sistem), 2026-11-09
- [x] Owner menyetujui default O4–O12, 2026-11-09
- [ ] Owner menyerahkan katalog dan harga edisi berikutnya (atau setuju harga diambil dari sistem lama)
- [x] Update `FEATURES/README.md` dan `FEATURES/11-exhibitor-portal.md` (scope baru)

### Phase 1: Database & rules
- [x] Modul `app/modules/orders/` dengan `rules.py` (transisi, pemilihan periode harga, harga per periode, hitung baris dan total, progres per form, syarat contract SIGNED)
- [x] Model + migration `0030` (tabel di atas kecuali allowances); `alembic check` tidak menemukan selisih di tabel order
- [x] Permission `order_form.manage`, `exhibitor_order.review` (migration `0031` + katalog `identity/rules.py`)
- [x] Bucket `orders` (`EMS_S3_BUCKET_ORDERS`) di config dan `ensure-buckets`
- [x] Unit test rules (`tests/test_order_rules.py`); integration test constraint (`tests/test_order_schema.py`). Syarat lead stage EXHIBITOR diuji di Phase 3 (service)

Catatan Phase 1 untuk Phase 3: periode yang berimpit di satu hari memakai periode yang lebih awal
(lebih murah). `ORDERING_NOT_OPEN` = `price_period()` mengembalikan `None`.

### Phase 2: Pengaturan form & katalog
- [x] API pengaturan form dan item (`app/modules/orders/router.py`, `service.py`): form dibuat belum publish, mata uang default dari edition; publish ditolak kalau tidak ada yang bisa diisi (422 `FORM_EMPTY`, juga saat item aktif terakhir dinonaktifkan); nomor form tidak bisa diubah; ganti mata uang ditolak kalau sudah ada order terkirim (409 `FORM_HAS_ORDERS`); kode duplikat 409 `DUPLICATE_FORM_CODE` / `DUPLICATE_ITEM_CODE`; edition ARCHIVED read-only
- [x] Gambar item: `POST/GET .../items/{item_id}/image` (JPG/PNG, cek ekstensi, MIME, magic bytes, maks 5 MB, bucket `orders`, tampil inline dengan `nosniff`)
- [x] Copy dari edition lain: `POST /order-forms/copy` (butuh `order_form.manage` edition-wide di kedua edition; nomor yang sudah ada dilewati; salinan tanpa tanggal dan belum publish; gambar dipakai bersama)
- [x] Import katalog Excel: `POST .../items/import` sinkron (maks 1.000 baris, 2 MB), semua atau tidak sama sekali, upsert per kode (tanpa membedakan huruf besar), sel harga kosong menghapus harga itu; template `GET /order-forms/item-import-template`. Tidak lewat `importexport`: katalog kecil, hasil langsung terlihat
- [ ] Isi katalog awal dari harga sistem lama: menunggu katalog dari owner (Phase 0); kalau owner setuju memakai harga lama, siapkan file Excel per form dari HTML sistem lama lalu import
- [x] Desk: menu Exhibitors → Order Forms (`order_form.manage`): daftar, tambah form, detail dengan tab Catalog / Settings, tambah dan edit item (dengan gambar), Import from Excel (daftar baris yang salah), Copy from Edition
- [x] Tes: `tests/test_order_forms.py` (aturan, permission dan scope, gambar, copy, import); E2E `apps/web/e2e/order-forms.mjs` (`make e2e-order-forms`); halaman baru masuk `smoke.mjs`

Catatan Phase 2: daftar form dan item juga bisa dibaca dengan `exhibitor_lead.read` (untuk tab Orders di
lead dan halaman review nanti); pengaturan tetap hanya `order_form.manage`.

### Phase 3: Portal, form katalog (03, 04, 05, 06, 07, 11, 12)
- [x] API portal (`app/modules/orders/portal.py`, `portal_router`): daftar form (progres, deadline, `closes_on` efektif, periode harga hari ini), detail (katalog dengan harga periode hari ini, draft terbuka, order terkirim, perusahaan dan booth), buat draft (409 `ORDER_OPEN`, 422 `FORM_CLOSED`), simpan draft (ganti semua baris; batas `max_quantity`; item nonaktif ditolak), quote, submit (nomor `<edition>-O-0001` saat submit pertama, harga dan periode dikunci, booth dan luas dicatat; 422 `ORDERING_NOT_OPEN` / `FORM_CLOSED` / `ORDER_EMPTY`), hapus draft (hanya DRAFT), not-required (409 `FORM_HAS_ORDERS`; submit menghapusnya)
- [x] Item tambahan tanpa harga + gambar (`.../lines/{line_id}/image`, JPG/PNG 5 MB; disimpan ulang dengan `id` tetap memakai gambarnya); lampiran sesuai `attachment_purposes` (jenis file per tujuan, maks 10 MB, maks 20 file per order); gambar katalog lewat route portal sendiri
- [x] Portal (`apps/exhibitor/src/pages/order-forms.tsx`): panel Order Forms di halaman exhibition, daftar form dengan filter, halaman form (katalog per section, item tambahan, lampiran, remarks, "I don't require this form", Save Draft, Delete Draft, order terkirim), halaman Review and Send, pesan Returned, "Waiting for your signed contract", tombol Order More setelah ada order terkirim
- [x] Tes: `tests/test_order_portal.py` (harga dari server dan body berisi harga ditolak, periode Regular/Surcharge/Onsite dan tutup, `closes_on`, akses exhibitor lain = 404, sesi staff = 401, CSRF, submit dengan contract DRAFT, lampiran dan gambar, not-required, edition ARCHIVED); E2E `apps/exhibitor/e2e/order-forms.mjs` (`make e2e-portal-orders`), unit test route dan hitung mundur

Catatan Phase 3:
- Portal tetap memakai router kecil sendiri (`lib.ts` `exhibitorRouteOf`), tidak memasang TanStack Router:
  empat halaman baru masih sederhana dan tidak perlu dependency baru.
- Ditemukan saat E2E: API melakukan commit **setelah** response terkirim (`get_session` berjalan sebagai
  dependency ber-scope request), jadi data yang baru dibuat bisa belum terlihat oleh request berikutnya, dan
  klien bisa menerima sukses walau commit gagal. Bukan bagian fitur ini; perbaikannya
  `Depends(get_session, scope="function")` di semua router. E2E mencoba ulang sekali pada 404 sampai itu diperbaiki.

### Phase 4: Review di desk
- [x] API (`app/modules/orders/review.py`, `orders_router`): antrian (draft tidak pernah tampil; filter status, form, cari perusahaan/nomor; scope lead: edition, team, atau lead sendiri), detail, harga item tambahan (hanya SUBMITTED; item katalog 422 `CATALOG_PRICE`), review Approve / Return (alasan wajib; Approve butuh semua harga 422 `UNPRICED_LINES` dan, untuk order berharga, contract SIGNED 422 `CONTRACT_NOT_SIGNED`), cancel dengan alasan; semua tercatat di audit (`price_line`, `approve`, `return`, `cancel`, `export`). Membaca: `exhibitor_lead.read`; mengubah: `exhibitor_order.review`, keduanya dalam scope lead
- [x] Desk: menu Exhibitors → Orders (antrian, mulai dari "Waiting for Review"), halaman order (baris, isi harga item tambahan, lampiran, gambar, Approve, Return to Exhibitor, Cancel Order sebagai halaman), tab Orders di halaman lead (progres per form + order terkirim)
- [x] Export per form: `GET /exhibitor-orders/export?edition_id=&form_id=&status=` (xlsx, satu baris per item). Sinkron, bukan job worker: satu form paling banyak beberapa ratus order; batas 20.000 baris
- [x] Peringatan "Booth changed since submit" di antrian dan halaman order (O2)
- [x] Tes: `tests/test_order_review.py` (antrian dan scope, harga, approve dan syarat contract, order gratis tanpa contract, return lalu kirim ulang dengan nomor sama, harga staff bertahan saat item tambahan tidak diubah, cancel, versi basi, edition ARCHIVED, booth berubah, tab lead, file dan export); E2E portal diperluas dengan alur desk (harga, Return, kirim ulang, tanda tangan, Approve, tab lead)

Catatan Phase 4: saat order Returned lalu dikirim ulang, item tambahan yang nama dan ukurannya tidak
diubah tetap memakai harga dari staff; yang diubah perlu diberi harga lagi.

### Phase 5: Form isian (01, 02, 02a, 08, 08a, 09, 10)
- [x] Skema per `details_type` di `app/modules/orders/details.py` (9 jenis, Lampiran A). Draft hanya diperiksa bentuk dan pilihannya; submit memeriksa field wajib (422 `DETAILS_INCOMPLETE`, per field `details.<path>`), termasuk syarat bersyarat (kontraktor sendiri, forwarder non-resmi, tamu VIP). Jawaban menyimpan teks pilihan, jadi mengubah daftar pilihan tidak mengubah order terkirim
- [x] Pilihan per form (bukan per edition: setiap form punya daftarnya sendiri), tabel `order_form_options` (migration `0032`): kategori produk, stand service, kontraktor resmi, forwarder resmi, tanggal seminar. `GET/PUT /order-forms/{id}/options` (ganti satu jenis sekaligus; hanya jenis yang dipakai pertanyaan form itu); ikut disalin Copy from Edition
- [x] Lampiran logo, gambar produk, daftar visa (XLSX): sudah ada sejak Phase 3 lewat `attachment_purposes`
- [x] Portal: komponen pertanyaan per jenis (`apps/exhibitor/src/pages/questions.tsx`), jawaban di halaman Review; form tanpa katalog tidak menampilkan total. Desk: bagian Choices di Settings form, panel Answers di halaman order, kolom Answers di export
- [x] Tes: `tests/test_order_details.py` (setiap jenis lengkap dan kosong, jawaban salah, syarat bersyarat, API pilihan dan copy, simpan dan kirim form pertanyaan, form katalog dengan pertanyaan, export); E2E portal ditambah form badge (ditolak saat belum lengkap, lalu diisi dan dikirim)

### Phase 6: Jatah gratis (09, 12)
- [x] Tabel `order_form_allowances` (migration `0033`), aturan `free_allowance` / `free_quantity` di `rules.py`. `free_quantity` dihitung saat simpan draft, quote, dan submit dari luas booth saat itu (luas tercatat di order saat submit); jumlah yang ditagih = jumlah − gratis
- [x] Jatah berlaku **sekali per exhibitor**, bukan per order: order lain yang masih hidup (Submitted, Returned, Approved) mengurangi sisa jatah; order yang di-Cancel mengembalikannya. Order terkirim tetap memakai jumlah gratis saat dikirim walau tingkatan diubah
- [x] API: `PUT /order-forms/{id}/items/{item_id}/allowances` `{tiers: [{min_area_sqm, free_quantity}]}` (ganti semua; luas yang sama dua kali ditolak); item menyertakan `allowances`; ikut disalin Copy from Edition. Portal: `free_quantity` per item katalog
- [x] Desk: bagian "Free by Booth Size" di halaman item, tanda "free by booth size" di katalog. Portal: "N free with your booth" di item, amount dan total memperhitungkan jumlah gratis, "N free" di order terkirim
- [x] Tes `tests/test_order_allowances.py` (tingkatan, API, portal, sekali per exhibitor, cancel mengembalikan jatah, order terkirim tidak berubah, copy); E2E portal: satu power point gratis per booth

Catatan Phase 6: badge gratis (form 09) dibuat sebagai item katalog "Exhibitor badge" dengan jatah per
luas booth, dan nama pemegang badge tetap diisi di pertanyaan form itu.

### Phase 7: Pembayaran order (O3)

Memakai tabel `exhibitor_payments` yang sudah ada, bukan tabel baru, supaya pencatatan, bukti bayar,
verifikasi, permission, dan audit tetap satu cara.

- [x] Migration `0034`: `exhibitor_payments.contract_id` nullable, kolom `order_id` (FK `(order_id, edition_id)` ke `exhibitor_orders`, index), CHECK `num_nonnulls(contract_id, order_id) = 1`. Payment yang sudah ada tidak berubah. Downgrade menghapus payment order (tidak bisa ada tanpa kolomnya)
- [x] Query payment kontrak yang ada sudah memfilter/join `contract_id`; dibuktikan tes (`GET /exhibitor-leads/{id}/payments` dan pipeline tidak memuat payment order, dan sebaliknya)
- [x] `app/modules/orders/payments.py`: catat (`POST /exhibitor-orders/{id}/payments`, `exhibitor_payment.record`; hanya order APPROVED dengan total > 0, 422 `ORDER_NOT_APPROVED`; `paid_on` tidak di masa depan; PENDING + VERIFIED + baru <= total, baris order di-lock, 422 `PAYMENT_EXCEEDS_TOTAL`), bukti (`.../proof`, PDF/JPG/PNG 10 MB, bucket `orders`), review (`.../review`, `exhibitor_payment.verify`, tolak wajib alasan, cek ulang batas total), daftar (`GET .../payments` dengan total, verified, pending, outstanding, `payment_state`). Semua dalam scope lead; audit `exhibitor_payment` dengan `order_id`
- [x] Cancel order diblok selama ada payment PENDING atau VERIFIED (409 `ORDER_HAS_PAYMENTS`)
- [x] Portal: `GET /portal/exhibitors/{lead}/orders/{id}/payments` (tanpa notes internal dan reviewer), `payment_state` di setiap order; order Approved berbayar menampilkan Paid / Being checked / Still to pay dan daftar payment. Ringkasan terpisah "Booth contract" vs "Service orders" di halaman exhibition tidak dibuat: status bayar tampil per order di halaman form
- [x] Desk: panel Payments di halaman order (catat, bukti, Verify / Reject di halaman payment), `payment_state` di antrian Orders dan tab Orders di lead
- [x] Overview: baris "Service orders" di panel exhibitor sales lewat `GET /exhibitor-orders/summary?edition_id=` (menunggu review, dikembalikan, nilai Approved, verified, pending, outstanding per currency), terpisah dari nilai kontrak
- [x] Tes `tests/test_order_payments.py` (termin sampai PAID, hanya order Approved berbayar, tolak dan review ulang, bukti, cancel diblok, tidak tercampur dengan payment kontrak, akses, satu target per payment, ringkasan); E2E: catat dan verifikasi payment order sampai Paid di desk, portal, dan Overview

### Phase 8: Dokumentasi & laporan
- [ ] `FEATURES/13-exhibitor-order-forms.md`, CHANGELOG, known-gaps
- [ ] Panel ringkasan di Overview (order per status, nilai Approved per form)
- [ ] E2E Playwright: setup katalog → exhibitor isi dan submit → staff return → submit ulang → approve
- [ ] `make gen-api`

---

## Lampiran A: 14 form dari sistem lama

Sumber: `resources/views/order-forms/form-*.blade.php` dan `OrderFormController.php` di paket lama.
Harga di sistem lama ada di HTML dan harus dipindahkan ke katalog (Phase 2).

| Kode | Judul | Katalog | Isian (`details_type`) | Lampiran / lain |
|---|---|---|---|---|
| 01 | E-Directory Listing | – | `directory_listing`: Agent/Principal, profil singkat, listed as (Manufacturer, Distributor/Agent, ...), kategori produk + detail, daftar agent/principal, mencari agen lokal | Data perusahaan dari contract |
| 02 | E-Directory & Onsite Advertising | Iklan e-directory dan banner onsite (Giant Banner, Hanging Banner, ...; varian "printed by organizer/exhibitor" = item terpisah) | `advertising`: bentuk logo, URL gambar | Logo, gambar iklan; dua deadline (Booking, Material) |
| 02a | Social Media Promotion | – | `social_media`: kategori produk, deskripsi produk (maks 800), video (link, judul, deskripsi), link Facebook/X/LinkedIn/Instagram/YouTube | Logo, gambar produk |
| 03 | Stand Service & Stand Construction | Fasilitas standard booth per luas | `stand_service`: pilihan layanan, kontraktor (resmi dari daftar, atau lain: nama, PIC, alamat, HP, email) | Daftar kontraktor resmi = opsi per edition |
| 04 | Electrical Fittings & Supplies | A. Lighting & Equipment, B. Electricity Power | – | Item tambahan; denah titik listrik |
| 05 | Compressed Air | Item compressed air | – | Item tambahan; denah |
| 06 | Water & Waste | Item air dan limbah | – | Item tambahan; denah |
| 07 | Furniture & Display Rental | Item furnitur | – | Item tambahan |
| 08 | Exhibit Details (Machinery) | – | `exhibit_details`: baris (jumlah, isi, dimensi, berat), status jual/operasi saat pameran | – |
| 08a | Freight Forwarder Service | – | `freight`: pakai forwarder resmi (pilih dari daftar) atau non-resmi (nama, alamat, negara, telepon, email, PIC, jabatan); baris barang (jumlah, isi, P×L×T, berat) | Daftar forwarder resmi = opsi per edition |
| 09 | Exhibitor Badges & Visa | Badge tambahan (kalau berbayar) | `badges_visa`: jenis perusahaan (lokal/luar negeri), nama badge (nama, gender, jabatan), VIP badge, undangan visa | Daftar visa (XLSX); jatah badge per luas booth |
| 10 | Seminar | Paket seminar (kalau berbayar) | `seminar`: topik, tanggal, jam, sampai 3 pembicara (nama, jabatan, perusahaan, judul) | Tanggal seminar = opsi per edition |
| 11 | Internet / Wi-Fi | Paket internet | – | Username/password Wi-Fi diberikan staff setelah Approved (catatan review) |
| 12 | Parking Pass | Parking pass per hari | `parking`: nomor plat per pass | Jatah gratis per luas booth |
