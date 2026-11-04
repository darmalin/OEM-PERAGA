# Exhibitor Leads & Sales Pipeline

**Requested:** 2026-10-30 (owner request) · **Last updated:** 2026-11-03 · **Author:** Fikri Darmawan

Dokumen kerja untuk fitur ini. AI/developer yang melanjutkan: baca dokumen ini, lalu
`BACKEND_RULES/` (aturan wajib), lalu centang task di bawah begitu selesai.

---

## Ringkasan

Mengelola **calon exhibitor** (perusahaan yang mau sewa booth) dari lead sampai lunas:

```
Exhibitor lead → Opportunity → pilih booth → convert ke Exhibitor (akun portal) → isi contract → payment (tagging)
```

- **Beda dengan Visitor Lead.** Visitor lead = pengunjung (`visitor_leads`, modul `visitors`).
  Exhibitor lead = calon exhibitor (`exhibitor_leads`, modul `exhibitors`). Tabel, menu, dan pipeline terpisah.
- **Opportunity bukan tabel/menu baru**, hanya stage di exhibitor lead.
- **Tanpa payment gateway.** Payment hanya dicatat dan diverifikasi manual oleh staff.

### Scope

Spec §1.2/§18 dan `FEATURES/11-exhibitor-portal.md` sebelumnya menaruh booth, contract, payment,
dan exhibitor portal **di luar phase 1**. Fitur ini adalah request owner 2026-10-30 yang
membukanya. Keputusan yang sudah dijawab (2026-11-03):

| # | Keputusan | Jawaban |
|---|---|---|
| E3 | Login portal | Satu akun per exhibitor (per email); akun yang sama dipakai lagi kalau exhibitor ikut edition lain |
| P1 | Payment | Bisa termin (DP, pelunasan); tiap pembayaran dicatat sendiri |
| P2 | Lead gagal | Stage `LOST` + alasan; bisa dibuka lagi ke `LEAD` |
| P3 | Contract | Field (nomor, PIC, alamat, NPWP, harga, diskon, total) + upload PDF yang sudah ditandatangani |

| E2 | Pembuatan akun portal | Undangan dari staff berupa **link** (tidak wajib lewat email); exhibitor membuka link lalu mengisi password |
| E6 | Domain portal | Production: subdomain sendiri (`EMS_PORTAL_BASE_URL`). Dev/staging: domain yang sama, di `/exhibitor` |
| C1 | Nomor contract | Otomatis per edition: `<kode edition>-C-0001` |

---

## Status per stage

Aturan non-negotiable #9: status tidak dicampur. Jadi ada tiga status terpisah:

| Di mana | Kolom | Nilai |
|---|---|---|
| `exhibitor_leads` | `stage` | `LEAD`, `OPPORTUNITY`, `EXHIBITOR`, `LOST` |
| `exhibitor_contracts` | `status` | `DRAFT`, `SIGNED` |
| `exhibitor_payments` | `status` (per pembayaran) | `PENDING`, `VERIFIED`, `REJECTED` |
| dihitung, tidak disimpan | payment state per contract | `UNPAID`, `PARTIAL`, `PAID` (dari total payment `VERIFIED` vs `total_amount`) |

Perpindahan stage lead (`app/modules/exhibitors/rules.py` `STAGE_TRANSITIONS`):

| Dari | Boleh ke |
|---|---|
| `LEAD` | `OPPORTUNITY`, `LOST` |
| `OPPORTUNITY` | `LEAD`, `EXHIBITOR`, `LOST` |
| `EXHIBITOR` | (final) |
| `LOST` | `LEAD` (reopen) |

Alur lengkap:

1. Lead masuk sebagai `LEAD` (input staff; form publik/import menyusul bila diminta).
2. Sales menandai `OPPORTUNITY` (`qualified_at` diisi).
3. Staff memilih booth: `booth_id` diisi (hanya saat `OPPORTUNITY`/`EXHIBITOR`).
4. Convert: stage `EXHIBITOR` (wajib punya booth), akun portal dibuat, contract `DRAFT` dibuat
   dengan `booth_price` disalin dari booth.
5. Exhibitor mengisi contract di portal, upload PDF bertanda tangan, lalu `SIGNED` (read-only).
6. Staff mencatat payment (bisa beberapa kali), lalu memverifikasi atau menolak tiap payment.

Riwayat perubahan stage, booth, contract, dan payment dicatat di `audit_logs` (`audit.record`),
tidak ada tabel history baru.

---

## Database (migration `0025`, modul `app/modules/exhibitors/`)

Semua tabel per edition (`edition_id NOT NULL`), punya `created_by`/`updated_by`, `version`
(optimistic locking), uang `NUMERIC(14,2)` + `currency`.

### `booths`
`code` (unik per edition), `hall`, `area_sqm`, `price`, `currency`, `is_active`, `notes`.
Ketersediaan booth **tidak disimpan**: booth dianggap terpakai jika ada exhibitor lead dengan `booth_id` itu.

### `exhibitor_leads`
`company_name`, `contact_name`, `email` + `email_normalized` (unik per edition), `phone` +
`phone_normalized`, `product_categories`, `booth_preference`, `budget_estimate`, `notes`,
`stage`, `lost_reason`, `qualified_at`, `converted_at`, `booth_id`, `booth_assigned_at`, `lead_owner_id`.

Constraint di database:
- satu booth hanya untuk satu lead (`uq_exhibitor_leads_booth`);
- booth harus dari edition yang sama (FK `(booth_id, edition_id)`);
- booth hanya boleh terisi saat `OPPORTUNITY`/`EXHIBITOR`, dan `EXHIBITOR` wajib punya booth.

### `exhibitor_contracts`
Satu per exhibitor lead. `contract_number` (unik per edition), `pic_name`, `company_address`,
`tax_id` (NPWP), `booth_price`, `discount_amount` (≤ harga), `total_amount`, `currency`, `status`,
`signed_at`, `signed_file_key` + `signed_file_name` (PDF di storage). `SIGNED` wajib punya nomor,
PIC, alamat, total, tanggal tanda tangan, dan PDF.

### `exhibitor_payments`
Satu baris per pembayaran (termin). `contract_id`, `amount` (> 0), `paid_on`, `method`
(`BANK_TRANSFER`, `CASH`, `OTHER`), `reference`, `proof_file_key`, `status`, `reviewed_by`,
`reviewed_at` (wajib terisi kecuali `PENDING`), `notes`.

### `exhibitor_accounts` (migration `0028`)
Login portal, terpisah dari `users` staff. **Bukan data per edition**: satu akun (per email)
bisa jadi exhibitor di beberapa edition; `exhibitor_leads.exhibitor_account_id` menunjuk ke akun
(unik per edition, wajib untuk stage EXHIBITOR). Kolom: `email` + `email_normalized` (unik),
`password_hash` (NULL sampai undangan diterima, Argon2id), `is_active`, `activated_at`,
`last_login_at`, `invite_token_hash` (SHA-256; token mentah hanya ditampilkan sekali) +
`invite_expires_at` (default 7 hari, `EMS_PORTAL_INVITE_TTL_SECONDS`).

### `exhibitor_contract_counters`
Counter nomor contract per edition, dinaikkan dengan `INSERT ... ON CONFLICT DO UPDATE ... RETURNING`.

---

## Aturan backend khusus fitur ini

- Setiap query filter `edition_id` + scope user (`Scope`), seperti modul lain.
- Permission: `exhibitor_lead.read`, `exhibitor_lead.create`, `exhibitor_lead.update`,
  `booth.manage`, `exhibitor.invite`, `exhibitor_payment.record`, `exhibitor_payment.verify`.
  Dicek di setiap endpoint.
- Portal: cookie sendiri (`ems_portal_session`), namespace session Redis sendiri (`psess:`),
  CSRF sama seperti staff, rate limit + lockout login sama seperti staff dengan counter terpisah.
  Audit dari portal memakai source `PORTAL` dan entity `exhibitor_account`.
- Duplikat email per edition ditangkap dari `IntegrityError` dan dikembalikan sebagai `Conflict`.
- Pindah booth hanya boleh sebelum contract `SIGNED`. Lead ke `LOST` melepas booth-nya.
- Contract `SIGNED` tidak bisa diedit.
- Total payment `VERIFIED` tidak boleh melebihi `total_amount` (dicek di service, dengan lock baris contract).
- Upload PDF/bukti bayar: cek ekstensi + MIME, simpan di storage dengan key acak, batas ukuran.
- Email (undangan portal, notifikasi) lewat `mail.service.queue_email`, dikirim di worker.

---

## Implementation Tasks

### Phase 1: Database & Models
- [x] Modul `app/modules/exhibitors/` dengan `rules.py` (stage, transitions, payment state)
- [x] Model `Booth`, `ExhibitorLead`, `ExhibitorContract`, `ExhibitorPayment`
- [x] Migration `0025` (upgrade/downgrade), cocok dengan model (`alembic check`)
- [x] Unit test rules (`tests/test_exhibitor_rules.py`)
- [x] Integration test constraint (`tests/test_exhibitor_schema.py`)

### Phase 2: Exhibitor Lead API (staff)
- [x] Permissions `exhibitor_lead.read` / `.create` / `.update` (migration `0026`, Super Admin + Exhibition Admin; sales pakai custom role)
- [x] `schemas.py`, `repository.py` (dengan `Scope`), `service.py`, `router.py`
- [x] `POST /api/v1/exhibitor-leads` (create, normalisasi email/phone; user scope OWNED otomatis jadi owner)
- [x] `GET /api/v1/exhibitor-leads?edition_id=` list (paginated, filter `stage`, `lead_owner_id`, `q`, `sort`) dan `GET /{id}`
- [x] `PATCH /{id}` edit (optimistic locking `version`; ganti owner hanya untuk akses edition penuh)
- [x] `POST /{id}/stage` pindah stage LEAD/OPPORTUNITY/LOST (`can_move`, `lost_reason` wajib untuk LOST, keluar dari OPPORTUNITY melepas booth), audit
- [x] `GET /{id}/activity` timeline audit
- [x] Tes endpoint + permission/scope (`tests/test_exhibitor_leads.py`)
- [x] OpenAPI + types frontend di-regenerate (`make gen-api`)

Catatan Phase 2: URL mengikuti pola project (flat, `edition_id` di query/body), bukan
`/editions/{id}/...`. Belum ada baseline role khusus sales exhibitor; owner menentukan apakah
perlu (misalnya `EXHIBITOR_SALES` dengan scope OWNED/TEAM) atau cukup custom role.

### Phase 3: Booth
- [x] Permission `booth.manage` (migration `0027`, Super Admin + Exhibition Admin)
- [x] `POST /api/v1/booths`, `PATCH /api/v1/booths/{id}` (akses edition penuh; currency default dari edition; kode unik per edition → 409 `DUPLICATE_BOOTH_CODE`; booth yang dipegang lead tidak bisa dinonaktifkan → 409 `BOOTH_IN_USE`). Tidak ada delete, pakai `is_active`
- [x] `GET /api/v1/booths?edition_id=` (`booth.manage` atau `exhibitor_lead.read`; filter `available`, `q`, `include_inactive`). `is_available` dihitung; nama perusahaan pemegang hanya untuk akses edition penuh
- [x] `PUT /api/v1/exhibitor-leads/{id}/booth` `{booth_id | null, version}` assign/pindah/lepas, audit `booth_change`. Hanya OPPORTUNITY (EXHIBITOR hanya pindah, tidak lepas); booth harus aktif dan dari edition yang sama; dipegang lead lain → 409 `BOOTH_TAKEN`; contract SIGNED → 409 `CONTRACT_SIGNED`
- [x] Lead menampilkan `booth_code`
- [x] Tes (`tests/test_booths.py`), termasuk dua user memilih booth yang sama bersamaan
- [x] OpenAPI + types frontend di-regenerate

Catatan untuk Phase 4: contract menyalin `booth_price` saat dibuat. Kalau booth exhibitor
dipindah sebelum contract SIGNED, `booth_price` (dan total) contract DRAFT harus ikut diperbarui.

### Phase 4: Convert & akun portal
- [x] Keputusan E2, E6, C1 (2026-11-03)
- [x] Migration `0028`: `exhibitor_accounts`, `exhibitor_leads.exhibitor_account_id`, `exhibitor_contract_counters`, permission `exhibitor.invite`
- [x] `POST /api/v1/exhibitor-leads/{id}/convert` `{version}` (`exhibitor.invite`): butuh OPPORTUNITY + booth; stage EXHIBITOR, akun portal (dipakai ulang kalau email sudah punya akun aktif), contract DRAFT bernomor dengan harga dari booth. Respons berisi link undangan (atau `null` kalau akun sudah punya password)
- [x] `POST /api/v1/exhibitor-leads/{id}/portal-invitation`: link baru, link lama mati; 409 kalau akun sudah aktif
- [x] Pindah booth saat contract DRAFT ikut memperbarui harga dan total contract (audit `reprice`)
- [x] Portal (`/api/v1/portal`): `POST /invitations/inspect`, `POST /invitations/accept` (set password + login), `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` (akun + exhibitor miliknya: edition, booth, nomor & status contract)
- [x] Tes (`tests/test_exhibitor_portal.py`): undangan sekali pakai/kadaluarsa/diganti, session staff dan portal tidak tercampur, CSRF, exhibitor yang kembali di edition lain

Belum dibangun (dicatat di `BACKEND_RULES/known-gaps.md` F6, F7): reset password portal,
dan menonaktifkan akun portal. Routing nginx untuk subdomain portal ikut Phase 7 (frontend).

### Phase 5: Contract (portal)
- [x] Portal: `GET/PATCH /api/v1/portal/exhibitors/{lead_id}/contract`: lihat & isi contract DRAFT (`pic_name`, `company_address`, `tax_id`, `version`). Lead exhibitor lain = 404
- [x] Upload PDF bertanda tangan: `POST .../contract/signed-copy` (multipart `file` + `version`) langsung menandai SIGNED. Wajib `pic_name` dan `company_address` (422 `CONTRACT_INCOMPLETE`); cek ekstensi, MIME, magic bytes `%PDF-`, maks 10 MB (`EMS_CONTRACT_FILE_MAX_BYTES`). File di bucket `contracts` dengan key acak
- [x] Staff: `GET/PATCH /api/v1/exhibitor-leads/{id}/contract` (`exhibitor_lead.read` / `.update`); staff juga bisa isi `discount_amount` (total = harga booth - diskon) dan upload signed copy kalau exhibitor kirim lewat chat
- [x] Unduh PDF: `GET .../contract/signed-copy` (staff dan portal). Bukan signed URL: storage tidak bisa diakses browser, file di-stream lewat API (sama seperti export). Nama file dari server: `<nomor contract>-signed.pdf`
- [x] Audit `exhibitor_contract` (`update`, `sign`); perubahan dari portal ber-source `PORTAL` dan mencatat `portal_account_id`
- [x] Tes (`tests/test_exhibitor_contracts.py`): SIGNED read-only (409 `CONTRACT_SIGNED`), data wajib, cek file, CSRF, akses hanya exhibitor sendiri, permission staff, edition ARCHIVED

Belum dibangun (F8 di `known-gaps.md`): membuka lagi contract SIGNED kalau PDF yang diupload salah.

### Phase 6: Payment tagging (staff)
- [x] Migration `0029`: permission `exhibitor_payment.record` dan `exhibitor_payment.verify` (Super Admin, Exhibition Admin)
- [x] Catat payment (termin): `POST /api/v1/exhibitor-leads/{id}/payments` `{amount, paid_on, method, reference?, notes?}` (`exhibitor_payment.record`). Hanya untuk contract SIGNED (422 `CONTRACT_NOT_SIGNED`); `paid_on` tidak boleh di masa depan (zona waktu edition); status awal PENDING
- [x] Bukti bayar opsional: `POST .../payments/{payment_id}/proof` (multipart `file` + `version`; PDF/JPG/PNG, maks 10 MB, bucket `contracts`), hanya selama PENDING; unduh `GET .../proof` (`exhibitor_lead.read`)
- [x] Verifikasi / tolak: `POST .../payments/{payment_id}/review` `{decision: VERIFIED|REJECTED, notes, version}` (`exhibitor_payment.verify`). Tolak wajib `notes` (alasan). Payment yang sudah direview = 409 `PAYMENT_REVIEWED`. Audit `exhibitor_payment` (`record`, `attach_proof`, `verify`, `reject`)
- [x] Tidak boleh lebih dari total: saat dicatat, PENDING + VERIFIED + baru <= `total_amount`; saat verifikasi dicek lagi. Baris contract di-lock, jadi dua pencatatan bersamaan tidak bisa lolos dua-duanya (422 `PAYMENT_EXCEEDS_TOTAL`)
- [x] `GET /api/v1/exhibitor-leads/{id}/payments` (`exhibitor_lead.read`): total, verified, pending, outstanding, `payment_state` (UNPAID/PARTIAL/PAID), daftar payment
- [x] Portal: `GET /api/v1/portal/exhibitors/{lead_id}/payments` (tanpa `notes` internal dan reviewer), dan `payment_state` di `GET /auth/me` (`null` selama contract belum SIGNED)
- [x] Tes (`tests/test_exhibitor_payments.py`): termin sampai PAID, contract belum SIGNED, batas total (termasuk paralel), input, bukti, permission dan scope

Catatan: rencana permission `exhibitor_contract.read` tidak dipakai; contract dan payment dibaca dengan
`exhibitor_lead.read` dan scope lead-nya. Payment PENDING tidak bisa diedit: tolak lalu catat ulang.

### Phase 7: Frontend
- [x] Menu **Exhibitors** di panel Admin: Exhibitor Leads (`exhibitor_lead.read`), Booths (`booth.manage` atau `exhibitor_lead.read`)
- [x] Exhibitor Leads: list (cari, filter stage, per edition), board per stage (read-only), tambah lead, detail dengan tab Details / Contract / Payments / Activity
- [x] Halaman aksi (bukan dialog, sesuai DESIGN.md): `/stage?to=` (Opportunity, Back to Lead, Lost + alasan, Reopen), `/booth` (pilih / lepas booth), `/convert` (link undangan ditampilkan sekali, tombol Copy), `/invitation` (link baru), `/payments/new`, `/payments/$paymentId` (bukti bayar, Verify / Reject)
- [x] Contract di desk: isi PIC, alamat, NPWP, diskon; upload PDF bertanda tangan atas nama exhibitor; unduh PDF
- [x] Halaman Booths: list (status Available / Held / Not for Sale, pemegang hanya untuk scope penuh), tambah ("Save and Add Another"), edit
- [x] Portal `apps/exhibitor` (React, tanpa router library; base `/exhibitor/`): Set Your Password dari link undangan, Sign In, My Exhibitions, halaman exhibition (isi contract, upload PDF, unduh, status payment). Bahasa Inggris, light/dark, mobile
- [x] nginx: `/exhibitor/` di host desk (dev: `make portal` di :5176 lewat `dev.conf`); prod dengan `EMS_PORTAL_BASE_URL`: `deployments/nginx/portal/` (host sendiri hanya melayani portal + `/api/v1/portal/`, link lama `/exhibitor/...` di-301 ke host baru). Panduan: `deployments/PRODUCTION.md` 4c
- [x] E2E Playwright `apps/exhibitor/e2e/pipeline.mjs` (`make e2e-portal`): booth, lead, Opportunity, booth, Convert, undangan, password, contract, PDF, payment + bukti, Verify, Paid di desk dan portal. Halaman desk baru masuk `apps/web/e2e/smoke.mjs`

Belum dibangun (FRONTEND_RULES/known-gaps.md W16, W17): memilih Lead Owner dari desk, dan drag di board.

### Phase 8: Dokumentasi & laporan
- [x] `FEATURES/11-exhibitor-portal.md` ditulis ulang (yang dibangun, keputusan, aturan, gap) dan `FEATURES/README.md` (scope baru)
- [x] Ringkasan pipeline: `GET /api/v1/exhibitor-leads/pipeline?edition_id=` (`exhibitor_lead.read`; jumlah per stage dan uang dihitung dalam scope user, booth per edition), panel "How are exhibitor sales going?" di Overview (`/app`). Tes `tests/test_exhibitor_pipeline.py`
- [x] Regenerate OpenAPI client frontend (`make gen-api`)
- [x] CHANGELOG (Unreleased)
