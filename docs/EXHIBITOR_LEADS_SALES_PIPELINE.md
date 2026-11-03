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
| E3 | Login portal | Satu akun per exhibitor per edition |
| P1 | Payment | Bisa termin (DP, pelunasan); tiap pembayaran dicatat sendiri |
| P2 | Lead gagal | Stage `LOST` + alasan; bisa dibuka lagi ke `LEAD` |
| P3 | Contract | Field (nomor, PIC, alamat, NPWP, harga, diskon, total) + upload PDF yang sudah ditandatangani |

Masih terbuka (jawab sebelum Phase 4): **E2** siapa yang membuat akun portal (staff mengundang
atau daftar sendiri), **E6** domain portal (sama dengan staff app atau subdomain terpisah),
dan siapa yang menerbitkan nomor contract (manual oleh staff atau otomatis).

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

### Akun portal (Phase 4)
Belum dibuat. Didesain bersama login portal: akun terpisah dari `users` staff, session terpisah
dari session staff, password Argon2id, undangan dengan token sekali pakai (hash di DB).

---

## Aturan backend khusus fitur ini

- Setiap query filter `edition_id` + scope user (`Scope`), seperti modul lain.
- Permission: `exhibitor_lead.read`, `exhibitor_lead.create`, `exhibitor_lead.update` (sudah ada);
  rencana: `booth.manage`, `exhibitor_contract.read`, `exhibitor_payment.record`,
  `exhibitor_payment.verify`. Dicek di setiap endpoint.
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
- [ ] Jawab E2, E6, dan siapa yang menerbitkan nomor contract
- [ ] Tabel akun portal + undangan (migration)
- [ ] `POST .../exhibitor-leads/{id}/convert`: stage EXHIBITOR, buat contract DRAFT, kirim undangan
- [ ] Login/logout/aktivasi portal, session terpisah dari staff
- [ ] Tes auth + rate limit login

### Phase 5: Contract (portal)
- [ ] Portal: lihat & isi contract DRAFT
- [ ] Upload PDF bertanda tangan, lalu tandai SIGNED
- [ ] Staff: lihat contract, unduh PDF (signed URL)
- [ ] Tes: SIGNED read-only, data wajib, akses hanya exhibitor sendiri

### Phase 6: Payment tagging (staff)
- [ ] Catat payment (termin), upload bukti opsional
- [ ] Verifikasi / tolak payment (`exhibitor_payment.verify`), audit
- [ ] Payment state per contract (`payment_state`), tidak boleh lebih dari total
- [ ] Portal: exhibitor lihat status pembayarannya
- [ ] Tes

### Phase 7: Frontend
- [ ] Menu Exhibitor Leads (list, detail, board per stage)
- [ ] Halaman booth
- [ ] Panel portal `/exhibitor` (login, contract, payment)
- [ ] E2E Playwright: lead → paid

### Phase 8: Dokumentasi & laporan
- [ ] Update `FEATURES/11-exhibitor-portal.md` dan `FEATURES/README.md` (scope baru)
- [ ] Ringkasan pipeline di dashboard (jumlah per stage, total terbayar)
- [ ] Regenerate OpenAPI client frontend (`make gen-api`)
- [ ] CHANGELOG
