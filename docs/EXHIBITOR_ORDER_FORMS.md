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
`form_id`, `item_id` (NULL = jatah untuk seluruh form), `min_area_sqm`, `max_area_sqm`,
`free_quantity`. Contoh form 12: booth < 9 m² → 1 pass gratis. Luas diambil dari `booths.area_sqm`.

### `exhibitor_orders`
`exhibitor_lead_id`, `form_id`, `order_number` (`<kode edition>-O-0001`, counter per edition
seperti `exhibitor_contract_counters`), `status`, `price_period`, `details` (JSONB, divalidasi
skema `details_type`), `remarks`, `subtotal`, `total`, `currency`, `submitted_at`,
`submitted_by_account_id`, `booth_id_at_submit`, `area_sqm_at_submit` (O2), `reviewed_by`,
`reviewed_at`, `review_notes`, `cancel_reason`.

Constraint:
- satu order terbuka (`DRAFT`/`RETURNED`) per (lead, form): partial unique index;
- lead harus stage `EXHIBITOR` dan dari edition yang sama (FK `(exhibitor_lead_id, edition_id)`);
- `submitted_at` wajib kecuali `DRAFT`; `reviewed_*` wajib untuk `APPROVED`/`RETURNED`.

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
- Import katalog dari Excel lewat modul `importexport` (template per form), dipakai juga untuk memindahkan
  harga dari sistem lama satu kali

**Staff: review**
- `GET /api/v1/exhibitor-orders?edition_id=&form_id=&status=&q=` (antrian review)
- `GET /api/v1/exhibitor-orders/{id}`
- `PATCH /api/v1/exhibitor-orders/{id}/lines/{line_id}` `{unit_price, version}` (harga item tambahan, hanya `SUBMITTED`)
- `POST /api/v1/exhibitor-orders/{id}/review` `{decision: APPROVED|RETURNED, notes, version}`
- `POST /api/v1/exhibitor-orders/{id}/cancel` `{reason, version}`
- `GET /api/v1/exhibitor-leads/{id}/orders`: semua order dan progres per form untuk satu exhibitor
- Export per form (job worker): contoh daftar nama badge untuk dicetak, rekap furnitur untuk kontraktor

**Portal** (`/api/v1/portal/exhibitors/{lead_id}/...`)
- `GET .../order-forms`: daftar form `is_published` dengan deadline, progres, jumlah order
- `GET .../order-forms/{code}`: form, katalog dengan harga periode sekarang, jatah gratis, isian dan draft yang ada
- `POST .../order-forms/{code}/orders` (buat draft), `PATCH .../orders/{order_id}` `{lines: [{item_id, quantity}], custom_lines, details, remarks, version}`
- `POST .../orders/{order_id}/quote`: ringkasan total dari server (dipakai halaman Review)
- `POST .../orders/{order_id}/submit` `{version}`, `DELETE .../orders/{order_id}` (hanya draft)
- `POST .../orders/{order_id}/files` (multipart `file` + `purpose`), `DELETE .../files/{file_id}` (hanya draft/returned)
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
- Portal sekarang tanpa router library. Dengan sekitar 4 halaman baru, pasang TanStack Router seperti
  `apps/web` (keputusan developer, dicatat di FRONTEND_RULES).

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
- [ ] Modul `app/modules/orders/` dengan `rules.py` (transisi, pemilihan periode harga, hitung baris)
- [ ] Model + migration `0030` (tabel di atas kecuali allowances), cocok dengan model (`alembic check`)
- [ ] Permission `order_form.manage`, `exhibitor_order.review` (migration `0031`)
- [ ] Bucket `orders` di config dan `ensure-buckets`
- [ ] Unit test rules; integration test constraint (satu draft per form, lead harus EXHIBITOR)

### Phase 2: Pengaturan form & katalog
- [ ] API pengaturan form dan item (termasuk gambar item)
- [ ] Copy dari edition lain
- [ ] Import katalog Excel; isi katalog awal dari harga sistem lama
- [ ] Desk: Order Forms, katalog, Copy from Edition
- [ ] Tes permission dan scope

### Phase 3: Portal, form katalog (03, 04, 05, 06, 07, 11, 12)
- [ ] API portal: daftar, detail, draft, quote, submit, hapus draft, not-required
- [ ] Item tambahan tanpa harga + upload gambar; lampiran denah (`FITTING_LOCATION`)
- [ ] Portal: daftar form, halaman form, Review & Submit, tampilan Returned
- [ ] Tes: harga dari server (body berisi harga ditolak), periode Regular/Surcharge/Onsite, `closes_on`, akses exhibitor lain = 404, CSRF, submit dengan contract DRAFT (O2)

### Phase 4: Review di desk
- [ ] API antrian, detail, harga item tambahan, review, cancel; audit
- [ ] Desk: Orders, halaman order, tab Orders di lead
- [ ] Export per form
- [ ] Peringatan "Booth changed since submit" di halaman review (O2)
- [ ] Tes: approve butuh semua harga terisi, approve order berharga dengan contract DRAFT ditolak (`CONTRACT_NOT_SIGNED`), alasan wajib, dua reviewer bersamaan (`version`)

### Phase 5: Form isian (01, 02, 02a, 08, 08a, 09, 10)
- [ ] Skema `details_type` per form (Lampiran A), opsi per edition (kategori produk, forwarder resmi, kontraktor resmi, tanggal seminar)
- [ ] Lampiran logo, gambar produk, daftar visa (XLSX)
- [ ] Portal: komponen isian per skema
- [ ] Tes validasi per skema

### Phase 6: Jatah gratis (09, 12)
- [ ] Tabel `order_form_allowances`, hitung `free_quantity` saat quote dan submit dari luas booth
- [ ] Desk: atur jatah per form; portal: tampilkan "Your free parking pass: 4"

### Phase 7: Pembayaran order (O3)

Memakai tabel `exhibitor_payments` yang sudah ada, bukan tabel baru, supaya pencatatan, bukti bayar,
verifikasi, permission, dan audit tetap satu cara.

- [ ] Migration: `exhibitor_payments.contract_id` jadi nullable, kolom baru `order_id` (FK
      `exhibitor_orders`, index), constraint `num_nonnulls(contract_id, order_id) = 1` (satu payment untuk
      contract **atau** order, tidak keduanya). Payment yang sudah ada tidak berubah
- [ ] Semua query payment contract yang ada sudah memfilter/join `contract_id`
      (`exhibitors/repository.py`), jadi payment order tidak ikut terhitung di contract. Tambahkan tes
      yang membuktikannya (pipeline dan `GET /exhibitor-leads/{id}/payments` tidak berubah)
- [ ] Catat payment order: `POST /api/v1/exhibitor-orders/{id}/payments` `{amount, paid_on, method,
      reference?, notes?}` (`exhibitor_payment.record`). Hanya order `APPROVED` dengan total > 0 (422
      `ORDER_NOT_APPROVED`); PENDING + VERIFIED + baru <= `total`, baris order di-lock (422
      `PAYMENT_EXCEEDS_TOTAL`, kode yang sama dengan contract)
- [ ] Bukti bayar dan review: endpoint proof dan review mengikuti pola payment contract
      (`.../payments/{payment_id}/proof`, `.../payments/{payment_id}/review`, `exhibitor_payment.verify`),
      dengan cek ulang batas total saat verifikasi
- [ ] `GET /api/v1/exhibitor-orders/{id}/payments`: total, verified, pending, outstanding, `payment_state`
- [ ] Cancel order diblok selama ada payment `VERIFIED` atau `PENDING` (409 `ORDER_HAS_PAYMENTS`)
- [ ] Portal: status payment per order (tanpa `notes` internal dan reviewer); halaman exhibition
      menampilkan ringkasan "Booth contract" dan "Service orders" terpisah
- [ ] Desk: tab Payments di halaman order (catat, bukti, Verify / Reject), kolom payment state di
      antrian Orders dan tab Orders di lead
- [ ] Overview: panel exhibitor sales mendapat baris "Service orders" (Approved, paid, waiting,
      outstanding per currency), terpisah dari nilai contract
- [ ] Tes: termin sampai PAID, order belum Approved, batas total (termasuk paralel), cancel dengan
      payment, payment contract dan order tidak saling tercampur, scope dan permission

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
