# Exhibition Management System (EMS)
## Visitor Leads CRM — Development Specification

**Dokumen:** `EMS-Visitor-CRM-Specification.md`  
**Versi:** 1.0 (Draft untuk implementasi awal)  
**Tanggal:** 20 Oktober 2026  
**Status:** Spesifikasi kerja awal; beberapa keputusan teknis masih perlu dikonfirmasi.

---

## 1. Tujuan dan Ruang Lingkup

Dokumen ini menjadi acuan awal pengembangan **Visitor Leads CRM** untuk Exhibition Management System (EMS). Sistem dirancang untuk satu perusahaan penyelenggara yang mengelola banyak exhibition, dengan pemisahan data dan akses berdasarkan exhibition edition.

### 1.1 Termasuk dalam fase awal

- Authentication dan permission dasar.
- Pengelolaan exhibition dan edition.
- Visitor lead CRUD, pencarian, filter, dan pagination.
- Validasi duplicate visitor.
- Import leads melalui Excel.
- Assignment manual, bulk assignment, dan round robin.
- Telemarketing call history.
- Verification visitor.
- Follow-up scheduling dan notifikasi email.
- Registrasi visitor dan penerbitan QR.
- Pengiriman dan pengiriman ulang QR melalui email.
- Gate scanner, termasuk dukungan offline dan sinkronisasi.
- Activity/audit log.
- Dashboard dan export report visitor.

### 1.2 Di luar ruang lingkup fase awal

- Exhibitor CRM dan sales pipeline.
- Booth inventory dan reservation.
- Proposal dan contract.
- Customer portal exhibitor.
- Dua belas form exhibitor.
- Invoice, payment, dan finance.
- Refund dan credit note.

### 1.3 Prinsip desain

1. Gunakan **Golang Modular Monolith**: satu aplikasi API dengan modul domain yang terpisah.
2. PostgreSQL adalah sumber data utama.
3. Semua data visitor, registrasi, aktivitas, dan attendance terhubung ke `edition_id`.
4. Permission harus diperiksa di backend, bukan hanya dengan menyembunyikan menu frontend.
5. Semua perubahan penting harus tercatat dalam audit log.
6. Operasi yang memicu email atau proses berat dilakukan melalui background worker.
7. Operasi yang dapat diulang harus idempotent jika sesuai, terutama registrasi, QR email, dan sinkronisasi scan.

---

## 2. Teknologi yang Direkomendasikan

| Lapisan | Teknologi |
|---|---|
| Backend API | Go + Gin |
| Frontend | React + Vite + TypeScript |
| UI | Tailwind CSS + shadcn/ui |
| Database | PostgreSQL |
| PostgreSQL access | pgx + sqlc |
| Queue/cache | Redis + Asynq |
| Authentication | Server-side session dengan cookie aman |
| Email | SMTP atau email provider API |
| File storage | S3-compatible storage / MinIO |
| Scanner | React PWA |
| Excel import/export | XLSX, diproses background untuk file besar |
| Reverse proxy | Nginx |
| Deployment | Docker Compose untuk awal |

Versi library dan runtime perlu dipilih serta dikunci saat proyek dibuat. Jangan memakai versi dependency yang tidak kompatibel hanya karena contoh dokumentasi menggunakan versi berbeda.

---

## 3. Konsep Exhibition dan Edition

Satu exhibition dapat mempunyai maksimal satu edition per tahun.

Contoh:

| Exhibition | Tahun | Kode |
|---|---:|---|
| IBTE | 2026 | `IBTE2026` |
| IBTE | 2027 | `IBTE2027` |
| IGHE | 2027 | `IGHE2027` |

`exhibitions` adalah master exhibition, sedangkan `exhibition_editions` merepresentasikan penyelenggaraan pada tahun tertentu.

Setiap edition menyimpan sekurang-kurangnya:

- Exhibition master.
- Tahun dan kode edition.
- Tanggal mulai dan selesai.
- Venue, country, city, dan timezone.
- Default currency.
- Registration ID prefix.
- Status.
- Konfigurasi email dan registrasi.
- Pengaturan gate.
- Tim dan user yang diizinkan mengakses edition.

Database harus menerapkan unique constraint pada pasangan `(exhibition_id, year)`. Semua query yang berhubungan dengan data event harus dibatasi oleh `edition_id` dan scope user.

---

## 4. Visitor Lead Specification

### 4.1 Field dari screenshot yang harus dipertahankan

| Kelompok | Field | Tipe awal | Aturan |
|---|---|---|---|
| Identitas | Date | Datetime | Dibuat sistem atau mengikuti tanggal registrasi yang didefinisikan |
| Identitas | Registration ID | String | Dibuat otomatis |
| Identitas | First Name | Text | Wajib |
| Identitas | Email | Email | Email atau phone minimal satu harus diisi |
| Identitas | Phone | String | Email atau phone minimal satu harus diisi |
| Identitas | Gender | Select | Opsional |
| Perusahaan | Company Name | Text | Opsional |
| Perusahaan | Job Title | Text | Opsional |
| Lokasi | Country | Select/reference | Opsional |
| Lokasi | City | Text | Opsional |
| Perusahaan | Website | URL | Opsional |
| Perusahaan | Business Type | Select/configurable | Opsional |
| Exhibition | Branch | Select/configurable | Nilai terkait konfigurasi event |
| Exhibition | Exhibition Type | Select/configurable | Nilai terkait konfigurasi event |
| Source | Source | Select | Misalnya Excel, API, Manual, Website, Telemarketing |
| Assignment | Lead Owner | User reference | Opsional saat lead belum di-assign |
| Status | Status | Select | Status operasional yang didefinisikan |
| Interest | Product Categories Interested In | Multi-select | Opsional |
| Notes | Comment | Textarea | Opsional |
| Verification | Valid Lead | Checkbox | Tidak boleh bersamaan dengan Invalid |
| Verification | Invalid | Checkbox | Tidak boleh bersamaan dengan Valid Lead |
| Verification | Attend | Select | Pilihan tetap di bawah |
| Verification | B2B Matching | Checkbox | Opsional |
| Verification | Type of Buyers | Select | B-Side atau C-Side |
| System | Updated At | Datetime | Otomatis |

Nama dan pilihan field harus dikonfirmasi terhadap screenshot/sumber data asli saat implementasi. Jangan mengubah label yang sudah digunakan tim tanpa persetujuan.

### 4.2 Pilihan Attend

Pilihan harus tetap:

1. `Attend`
2. `Attend Sourcing`
3. `Under Consideration`
4. `Not Attend`
5. `Hang Up Immediately`

`Hang Up Immediately` dipertahankan karena merupakan kebutuhan bisnis yang dikonfirmasi, tetapi secara semantik hasil panggilan juga harus direkam dalam `call_result`. Jangan menyimpulkan bahwa visitor benar-benar tidak hadir hanya dari nilai Attend.

### 4.3 Type of Buyers

Pilihan yang diizinkan:

- `B-Side`
- `C-Side`

### 4.4 Field sistem tambahan yang disarankan

- `id`
- `edition_id`
- `registration_status`
- `qr_status`
- `last_call_at`
- `next_followup_at`
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`
- `custom_fields` (JSONB untuk nilai custom field yang sudah divalidasi)

`Status` pada screenshot perlu dipastikan apakah berarti status lead, status telemarketing, atau status registrasi. Jangan menyatukan tiga konsep berbeda menjadi satu field. Rekomendasi: status telemarketing dihitung dari call attempts, status registrasi dikelola terpisah, dan status verifikasi disimpan tersendiri.

### 4.5 Custom fields

Admin boleh menambahkan custom field per exhibition. Setiap definisi field sekurang-kurangnya memiliki:

- `field_key`
- `label`
- `field_type`
- `required`
- `options` jika select/multi-select
- `sort_order`
- `is_active`
- aturan validasi
- konfigurasi apakah field ditampilkan dalam import/export

Jenis awal yang direkomendasikan: text, textarea, number, date, select, multi-select, dan checkbox.

Definisi custom field disimpan dalam tabel konfigurasi; nilainya dapat disimpan pada JSONB setelah validasi backend. Jangan menerima key atau tipe field sembarang dari request tanpa mencocokkannya dengan definisi aktif untuk edition tersebut.

---

## 5. Registration ID dan Duplicate Rules

### 5.1 Registration ID

Format yang dipilih: **kode event + tahun + nomor unik**.

Contoh: `IBTE2027000001`.

Nomor harus dibuat aman terhadap request bersamaan. Gunakan sequence/counter transaksional atau mekanisme generator yang tidak menghasilkan ID ganda. Jangan membuat nomor hanya dengan menghitung jumlah baris.

Registration ID tidak sama dengan primary key internal. Gunakan ID internal yang stabil (misalnya UUID) dan Registration ID sebagai identifier bisnis.

**Belum dikonfirmasi:** apakah data dari API eksternal yang sudah memiliki Registration ID harus mempertahankan ID tersebut atau menggunakan ID EMS. Default yang disarankan: EMS menerbitkan Registration ID internal; ID eksternal disimpan di kolom terpisah seperti `external_source` dan `external_id`.

### 5.2 Duplicate rules

Email atau phone yang sama dalam edition yang sama dianggap kandidat duplicate dan record baru ditolak.

| Kondisi | Hasil |
|---|---|
| Email sama, phone berbeda | Reject |
| Email berbeda, phone sama | Reject |
| Email dan phone sama | Reject |
| Email sama di edition lain | Allow |
| Phone sama di edition lain | Allow |
| Email kosong, phone unik | Allow |
| Phone kosong, email unik | Allow |
| Email dan phone kosong | Reject |

Normalisasi:

- Email: trim whitespace dan lowercase.
- Phone: trim, normalisasi ke format internasional/E.164 bila dapat ditentukan.
- Nilai kosong disimpan sebagai `NULL`, bukan string kosong.

Implementasikan unique constraint/index terpisah per `edition_id` untuk email dan phone yang tidak NULL. API harus tetap menangani pelanggaran constraint untuk mengatasi race condition. Untuk duplicate API, rekomendasi respons adalah HTTP `409 Conflict`.

Import Excel harus menghasilkan laporan per baris yang memuat nomor baris, alasan gagal, dan data yang aman ditampilkan. Satu baris duplicate tidak harus menggagalkan seluruh import.

Update visitor yang sudah ada harus mengacu ke ID record yang sah dan tetap memeriksa konflik dengan record lain. Kebijakan upsert API belum diputuskan dan tidak boleh diasumsikan.

---

## 6. Telemarketing

### 6.1 Metode assignment

Sistem harus mendukung:

- Manual assignment.
- Bulk assignment.
- Round-robin assignment.

Reassignment hanya boleh dilakukan oleh Sales/Telemarketing Manager sesuai permission yang diberikan. Histori assignment tidak boleh ditimpa; setiap perubahan menghasilkan record histori dengan actor dan timestamp.

### 6.2 Status telemarketing

Lima status yang dipilih:

| Status | Makna |
|---|---|
| `NEW` | Belum ada call attempt |
| `ANSWER` | Attempt pertama dijawab |
| `NO_ANSWER` | Attempt pertama tidak dijawab |
| `RECONTACTED` | Attempt kedua atau berikutnya dijawab |
| `RETRY_NO_ANSWER` | Attempt kedua atau berikutnya tidak dijawab |

Status ditentukan otomatis berdasarkan jumlah attempt dan hasil terakhir. Simpan call attempts sebagai histori; status saat ini merupakan ringkasan dari histori tersebut.

Tidak ada integrasi telepon/VoIP. Agent mencatat hasil panggilan secara manual.

### 6.3 Call activity

Setiap call attempt minimal menyimpan:

- `id`
- `visitor_lead_id`
- `agent_id`
- `attempt_number`
- `call_result`
- `called_at`
- `duration_seconds` (opsional)
- `notes`
- `next_followup_at` (bila diperlukan)
- `created_at`

Hasil panggilan minimal mendukung Answer dan No Answer. Jika bisnis membutuhkan busy, invalid number, atau call failed, pilihan itu harus ditambahkan secara eksplisit melalui konfigurasi.

### 6.4 Verification

Ketika panggilan dijawab, agent dapat mengisi Verification. Data boleh disimpan sebagian.

- `Valid Lead` dan `Invalid` tidak boleh sama-sama aktif.
- Keduanya tidak dicentang berarti belum diputuskan.
- `Attend` menggunakan lima pilihan tetap.
- `Type of Buyers` menggunakan B-Side/C-Side.
- `B2B Matching` adalah checkbox.
- Perubahan data lead oleh telemarketing diperbolehkan.
- Perubahan wajib masuk audit log.

Disarankan menyimpan histori perubahan verification, bukan hanya menimpa nilai terakhir. Jika keputusan bisnis hanya membutuhkan nilai terkini, tabel histori tetap dapat digunakan untuk audit dan analisis perubahan.

### 6.5 Follow-up

Follow-up memiliki tanggal dan waktu berikutnya. Sistem harus mendukung:

- Pembuatan follow-up dari call activity.
- Daftar follow-up hari ini dan overdue.
- Notifikasi email sesuai jadwal yang dikonfigurasi.
- Penyelesaian atau pembatalan follow-up.
- Histori perubahan jadwal.
- Penghindaran email ganda melalui idempotency key/job deduplication.

Jadwal reminder dan aturan eskalasi masih perlu dikonfirmasi. Jangan mengasumsikan interval reminder tetap sebelum bisnis menyetujuinya.

---

## 7. Registration, QR dan Email

### 7.1 Channel registrasi

Registrasi dapat berasal dari:

- Website.
- Admin manual.
- Telemarketing.
- API.
- Excel import.

QR harus diterbitkan setelah registrasi berhasil, tanpa menunggu telemarketing mengonfirmasi attendance.

**Keputusan yang masih terbuka:** apakah semua visitor lead hasil import otomatis dianggap terdaftar dan mendapatkan QR, atau import lead dan registrasi merupakan dua proses berbeda. Rekomendasi: definisikan status lead dan registration secara terpisah; perilaku import dikonfigurasi berdasarkan jenis import.

### 7.2 QR credential

- QR menggunakan token acak yang sulit ditebak.
- QR tidak menyimpan PII langsung.
- Credential dapat dicabut.
- Pengiriman ulang email tidak otomatis menerbitkan credential baru.
- Jika QR perlu dirotasi, credential lama harus di-revoke.
- Token tidak boleh ditulis ke application log atau audit log.

### 7.3 Email

Email otomatis mengirim QR setelah registrasi berhasil. Resend manual tersedia bagi role yang berwenang.

Setiap job/email sebaiknya mencatat:

- recipient
- template/version
- related registration
- queued time
- sent time
- provider message ID jika tersedia
- delivery status jika provider mendukung
- error summary yang aman

Pengiriman email dilakukan melalui worker, bukan secara sinkron dalam request registrasi.

---

## 8. Attendance dan Gate Scanner

### 8.1 Gate dan perangkat

Setiap gate terikat pada satu edition. Perangkat scanner harus terdaftar dan dihubungkan ke gate serta edition yang diizinkan.

Scanner tidak boleh memvalidasi registrasi dari edition lain. Hak akses diperiksa di server dan konfigurasi perangkat.

### 8.2 Aturan scan

- Scan valid pertama pada suatu hari: `FIRST_ENTRY`.
- Scan valid berikutnya pada hari yang sama: `REPEAT_ENTRY`.
- Hari berikutnya: visitor kembali dapat memperoleh `FIRST_ENTRY`.
- Tidak ada proses exit/check-out.
- Setiap percobaan scan dapat dicatat terpisah dari entry valid.
- Reporting harus membedakan total scan, total entry valid, unique daily visitors, unique event visitors, first entry, dan repeat entry.

“Unique daily visitors” dihitung sebagai jumlah registration unik per tanggal lokal event. “Unique event visitors” dihitung sebagai registration unik sepanjang edition.

### 8.3 Offline mode

Scanner harus mendukung:

- Cache credential/registrasi yang diizinkan pada perangkat terdaftar.
- Masa berlaku cache.
- Queue scan lokal.
- `scan_event_id`/idempotency key unik.
- Retry sinkronisasi.
- Status pending/synced/rejected.
- Rekonsiliasi setelah online.

Perangkat offline tidak dapat mengetahui scan dari perangkat offline lain secara real-time. Karena itu, hasil First/Repeat yang ditampilkan offline dapat bersifat sementara. Server menjadi sumber keputusan final setelah sinkronisasi.

Offline cache menambah risiko keamanan. Batasi masa berlaku, data lokal, akses perangkat, dan sediakan mekanisme revoke device. Durasi cache dan kebijakan kehilangan perangkat masih harus dikonfirmasi.

---

## 9. Role dan Permission Phase 1

Role operasional awal:

1. `SUPER_ADMIN`
2. `EXHIBITION_ADMIN`
3. `TELEMARKETING_MANAGER`
4. `TELEMARKETING_AGENT`
5. `GATE_SUPERVISOR`
6. `GATE_STAFF`

Role di atas adalah baseline; hak final harus berupa permission dan scope yang dapat ditetapkan kepada user.

### 9.1 Permission awal

```text
exhibition.read
exhibition.manage
edition.read
edition.manage

visitor.read
visitor.create
visitor.update
visitor.import
visitor.export
visitor.assign
visitor.verify

telemarketing.call
telemarketing.followup
telemarketing.view_team
telemarketing.reassign

registration.create
registration.read
registration.resend_qr

gate.scan
gate.view_history
gate.manage_devices
gate.override

report.view
report.export

user.manage
role.manage
audit_log.read
```

### 9.2 Scope

Scope minimum:

- `EDITION`
- `TEAM`
- `OWNED`
- `GATE`

Super Admin dapat memperoleh scope lintas edition. Telemarketing Agent default hanya dapat melihat lead yang di-assign kepadanya, kecuali kebijakan tim menentukan akses lebih luas. Gate Staff hanya boleh scan pada gate/device yang ditugaskan.

Permission export terpisah dari read. Semua endpoint memvalidasi role, permission, scope, dan ownership di backend.

---

## 10. Audit Log

Setiap perubahan penting harus mencatat:

- actor/user
- entity type dan entity ID
- action
- before/after
- timestamp
- source (UI, API, import, worker, scanner)
- request/correlation ID jika tersedia

Audit log mencakup perubahan lead, verification, assignment, call/follow-up, registrasi, QR resend/revoke, konfigurasi gate, serta tindakan administrasi.

Jangan merekam password, session token, QR token rahasia, atau kredensial provider. Batasi akses audit log dan hindari menyimpan data pribadi berlebihan dalam metadata.

---

## 11. Reporting dan Export

Dashboard near-real-time dapat menggunakan polling/refresh. Laporan berat dan export diproses melalui worker.

Report minimum:

- Lead overview: total, new, assigned, unassigned.
- Telemarketing: attempts, answer rate, follow-up due/overdue.
- Verification: valid, invalid, attendance intention.
- Registration: registered, QR issued, email status.
- Attendance: unique daily/event visitors, first/repeat entry.
- Gate: scan per gate, jam, dan hari.
- Agent performance: leads handled, attempts, follow-up completion.
- Import: processed, rejected, duplicate, error.
- Email: queued, sent, failed, dan status provider bila tersedia.

Filter minimum:

- Exhibition/edition
- Date range
- Country
- Source
- Lead owner/team
- Telemarketing status
- Verification
- Registration/QR status
- Gate

Semua report harus menerapkan scope permission. Export memerlukan permission tersendiri dan menghasilkan audit event.

---

## 12. Database Domain Awal

Tabel utama yang direncanakan:

| Domain | Tabel |
|---|---|
| Exhibition | `exhibitions`, `exhibition_editions`, `venues` |
| Identity/Permission | `users`, `roles`, `permissions`, `role_permissions`, `user_role_assignments`, `teams`, `user_team_memberships` |
| Visitor | `visitor_leads`, `visitor_custom_field_definitions` |
| Telemarketing | `visitor_call_activities`, `visitor_verifications`, `visitor_followups`, `lead_assignment_history` |
| Registration | `visitor_registrations`, `qr_credentials` |
| Email | `email_templates`, `email_jobs`, `email_logs` |
| Attendance | `gates`, `scanner_devices`, `scan_attempts`, `visitor_checkins` |
| Import/Export | `import_jobs`, `import_errors`, `export_jobs` |
| System | `audit_logs`, `outbox_events` |

Nama tabel dan kolom dapat disesuaikan pada ERD dan migration final. Relasi serta constraint harus ditetapkan sebelum implementasi endpoint terkait.

---

## 13. API Contract Awal

Prefix: `/api/v1`.

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/exhibitions` | List exhibition |
| POST | `/exhibitions` | Create exhibition |
| GET | `/editions` | List editions sesuai scope |
| POST | `/editions` | Create edition |
| GET | `/visitor-leads` | List/filter/paginate |
| POST | `/visitor-leads` | Create lead |
| GET | `/visitor-leads/{id}` | Detail |
| PATCH | `/visitor-leads/{id}` | Update |
| POST | `/visitor-leads/imports` | Mulai import |
| GET | `/visitor-leads/imports/{id}` | Status/report import |
| POST | `/visitor-leads/assignments` | Bulk/manual assignment |
| POST | `/visitor-leads/{id}/calls` | Catat call attempt |
| PATCH | `/visitor-leads/{id}/verification` | Update verification |
| POST | `/visitor-leads/{id}/followups` | Buat follow-up |
| POST | `/visitor-registrations` | Buat registrasi |
| POST | `/visitor-registrations/{id}/resend-qr` | Resend QR email |
| POST | `/gate/scans` | Online scan |
| POST | `/gate/scans/sync` | Sinkronisasi offline scan |
| GET | `/reports/visitors` | Dashboard/report |
| POST | `/exports/visitors` | Buat export job |
| GET | `/exports/{id}` | Status/download export sesuai izin |

API publik untuk website registration harus mempunyai rate limiting, validasi, perlindungan spam, dan kebijakan duplicate yang sama. API internal menggunakan autentikasi dan scope yang sesuai.

---

## 14. Struktur Repository yang Direkomendasikan

```text
ems/
├── backend/
│   ├── cmd/
│   │   ├── api/
│   │   ├── worker/
│   │   └── migrate/
│   ├── internal/
│   │   ├── platform/
│   │   │   ├── config/
│   │   │   ├── database/
│   │   │   ├── auth/
│   │   │   ├── authorization/
│   │   │   ├── email/
│   │   │   ├── storage/
│   │   │   ├── audit/
│   │   │   └── observability/
│   │   └── modules/
│   │       ├── exhibition/
│   │       ├── visitor/
│   │       ├── telemarketing/
│   │       ├── registration/
│   │       ├── checkin/
│   │       ├── importexport/
│   │       └── reporting/
│   ├── migrations/
│   ├── queries/
│   ├── generated/
│   └── go.mod
├── frontend/
│   └── src/
│       ├── app/
│       ├── features/
│       │   ├── auth/
│       │   ├── exhibitions/
│       │   ├── visitors/
│       │   ├── telemarketing/
│       │   ├── registrations/
│       │   ├── checkin/
│       │   └── reports/
│       ├── components/
│       ├── lib/
│       └── types/
├── deployments/
├── docs/
└── docker-compose.yml
```

Frontend disarankan memakai React Router atau TanStack Router, TanStack Query untuk server state, React Hook Form + Zod untuk form, dan TanStack Table untuk daftar leads. Pilihan final library dapat diputuskan saat bootstrap.

---

## 15. Milestone Implementasi

### Milestone 1 — Foundation dan Visitor CRUD

- Bootstrap Go API, React, PostgreSQL, migration.
- Login/session dan permission/scope.
- Exhibition dan edition CRUD.
- Visitor list/detail/create/update.
- Filter, pagination, dan duplicate validation.
- Audit log.
- Unit dan integration test.

**Acceptance criteria:** user tidak dapat membaca/mengubah edition di luar scope; duplicate email/phone ditolak oleh database; setiap update tercatat di audit log.

### Milestone 2 — Import dan Assignment

- Excel import dengan validasi per baris.
- Error report.
- Manual, bulk, dan round-robin assignment.
- Assignment history.

**Acceptance criteria:** file besar tidak memblokir request; hasil import bisa dilacak; assignment tidak menghilangkan histori.

### Milestone 3 — Telemarketing

- Call history.
- Perhitungan status otomatis.
- Verification form.
- Follow-up scheduling.
- Daftar follow-up due/overdue.
- Email notification worker.

**Acceptance criteria:** attempt tersimpan sebagai histori; status dihitung konsisten; verification parsial diperbolehkan; perubahan lead tercatat.

### Milestone 4 — Registration dan QR

- Registration flow.
- QR token issuance/revoke.
- Email QR otomatis.
- Resend manual.
- Delivery/error log.

**Acceptance criteria:** registrasi idempotent; QR tidak mengandung PII; email gagal dapat di-retry tanpa membuat registrasi duplikat.

### Milestone 5 — Gate Scanner

- Gate/device management.
- Online scan.
- PWA offline cache dan queue.
- Sync API dan conflict reconciliation.
- First/repeat entry.
- Scan history.

**Acceptance criteria:** scan yang sama tidak tercatat dua kali akibat retry; scanner tidak menerima edition yang tidak ditugaskan; konflik offline ditangani dan dapat diaudit.

### Milestone 6 — Dashboard, Export, dan Hardening

- Dashboard/report.
- Excel export worker.
- Permission export.
- Load, security, dan backup-restore testing.

**Acceptance criteria:** seluruh laporan mengikuti scope; export diaudit; restore database telah diuji.

---

## 16. Testing dan Non-Functional Requirements

Pengujian minimum:

- Unit test untuk business rules.
- Integration test dengan PostgreSQL dan Redis.
- Permission matrix test.
- Concurrency test untuk duplicate registration ID, duplicate leads, dan check-in.
- Idempotency test untuk registrasi, email job, dan offline sync.
- E2E test untuk alur telemarketing.
- Load test untuk list/filter leads dan scan API.
- Backup/restore drill.

Target performa harus ditetapkan berdasarkan perkiraan volume leads, jumlah scanner, dan concurrent users. Jangan menganggap target latency tertentu sudah terjamin sebelum pengujian beban dilakukan.

---

## 17. Keputusan yang Masih Terbuka

Bagian ini sengaja dipertahankan agar developer tidak menganggap asumsi sebagai keputusan final.

1. **API Registration ID:** apakah ID eksternal dipertahankan atau disimpan terpisah? Default: EMS membuat ID internal.
2. **Import vs registration:** apakah import lead otomatis membuat registrasi dan mengirim QR? Rekomendasi: dibedakan dan dikonfigurasi.
3. **Status pada screenshot:** apakah `Status` berarti status lead atau status lain? Rekomendasi: pisahkan status telemarketing, registration, dan verification.
4. **Follow-up reminders:** interval, jam kirim, dan aturan eskalasi.
5. **Custom field:** scope definisi per exhibition master atau per edition.
6. **Offline cache:** masa berlaku, aktivasi device, dan kebijakan perangkat hilang.
7. **Call result tambahan:** apakah Answer/No Answer sudah cukup atau memerlukan Busy/Invalid Number.
8. **Country/phone:** referensi negara dan kebijakan normalisasi nomor telepon.
9. **Retention:** masa penyimpanan PII, audit log, dan data scanner.

Keputusan ini harus ditutup sebelum fitur terkait dinyatakan siap production.

---

## 18. Catatan untuk Developer / Codex

- Jangan membangun modul Exhibitor, Contract, Finance, atau 12 Form dalam fase ini.
- Jangan membuat satu status generik untuk telemarketing, registration, verification, dan attendance.
- Jangan mengandalkan validasi frontend untuk aturan duplicate atau permission.
- Jangan menjalankan email dan export berat secara sinkron di API.
- Jangan menghapus call history, assignment history, atau audit log ketika data lead berubah.
- Jangan menjanjikan First/Repeat global secara real-time ketika scanner sedang offline.
- Semua migration, API, dan permission harus disertai test.
- Dokumentasikan perubahan requirement sebelum mengubah schema atau workflow.

**Hasil yang dituju:** Visitor CRM yang dapat dipakai untuk mengelola leads per exhibition, mengassign telemarketing, mencatat panggilan dan verification, mengirim QR, merekam attendance online/offline, serta menghasilkan report yang aman berdasarkan permission.
