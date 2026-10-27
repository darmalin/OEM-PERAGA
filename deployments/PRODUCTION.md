# Production dan staging di satu server

Dua stack Docker Compose yang **terpisah total** di satu mesin. Yang dipakai bersama hanya Docker,
nginx host, dan sertifikat TLS. Database, Redis, storage, worker, secret, dan email masing-masing
punya sendiri.

```
                       ┌── ems.example.com ─────────► 127.0.0.1:8081 ─► stack "ems-prod"
internet ─► nginx host ┤
  (TLS, certbot)       └── staging.ems.example.com ─► 127.0.0.1:8080 ─► stack "ems-staging"
```

| | Staging | Production |
|---|---|---|
| Folder | `/srv/ems-staging` | `/srv/ems-prod` |
| Kode | branch `main` (terbaru) | tag rilis, mis. `v1.0.0` |
| Project Compose (dibuat `setup.sh`) | `ems-staging` | `ems-prod` |
| Port lokal | `127.0.0.1:8080` | `127.0.0.1:8081` |

Alurnya: **clone → `setup.sh init` → isi `.env` → nginx → `setup.sh check` → jalankan.**

## 0. Hapus staging lama (sekali saja)

Menghapus folder **tidak** menghapus container dan data Docker-nya. Matikan dulu dari folder lama.

```bash
cd /path/staging-lama
docker compose ps                  # lihat nama project-nya (kolom NAME, mis. ems-api-1 → "ems")
docker compose down --remove-orphans
```

Kalau data staging lama **tidak dibutuhkan lagi**, hapus juga volume-nya:

```bash
docker compose down -v --remove-orphans        # menghapus database dan file staging lama
```

Lalu hapus foldernya. Pastikan tidak ada yang tertinggal:

```bash
docker ps -a
docker volume ls
```

Aplikasi baru hanya terhubung ke nginx host. Nonaktifkan site nginx staging lama kalau namanya akan
dipakai ulang:

```bash
sudo rm /etc/nginx/sites-enabled/<site-lama>
```

## 1. Clone

```bash
sudo mkdir -p /srv/ems-staging /srv/ems-prod && sudo chown "$USER" /srv/ems-staging /srv/ems-prod
git clone git@github.com:darmalin/OEM-PERAGA.git /srv/ems-staging
git clone git@github.com:darmalin/OEM-PERAGA.git /srv/ems-prod
cd /srv/ems-prod && git checkout v1.0.0     # prod selalu dari tag rilis
```

Belum ada tag? Buat dulu dari komputer developer, dari commit yang sudah lolos di staging:
`git tag v1.0.0 && git push origin v1.0.0`.

## 2. Buat `.env` dengan script

Di tiap folder, sekali saja:

```bash
cd /srv/ems-staging && deployments/setup.sh init staging
cd /srv/ems-prod    && deployments/setup.sh init prod
```

Script ini:
- mengisi password Postgres, kunci storage, dan `EMS_APP_ENCRYPTION_KEY` dengan nilai acak, tanpa
  menampilkannya di layar;
- mengatur `COMPOSE_FILE=compose.yaml`, sehingga file dev (`compose.override.yaml`) tidak pernah ikut;
- mengatur nama project dan port lokal;
- membuat `.env` dengan izin `600`;
- menolak berjalan kalau `.env` sudah ada, supaya kunci enkripsi tidak tertimpa.

## 3. Isi `.env` (manual)

Buka `.env` dan ganti setiap `CHANGE_ME`. Yang lain biarkan.

| Variabel | Isi dengan | Contoh |
|---|---|---|
| `EMS_PUBLIC_BASE_URL` | alamat yang dibuka orang, pakai `https://` | `https://ems.example.com` |
| `EMS_SMTP_HOST`, `EMS_SMTP_PORT`, `EMS_SMTP_USE_TLS` | server SMTP | `smtp.gmail.com`, `587`, `true` |
| `EMS_SMTP_USERNAME`, `EMS_SMTP_PASSWORD` | login SMTP | |
| `EMS_EMAIL_FROM` | pengirim email sistem | `EMS <no-reply@ems.example.com>` |

- **Staging:** pakai SMTP sandbox (Mailtrap atau sejenisnya), supaya QR tidak terkirim ke visitor asli.
- **SMTP di `.env` hanya cadangan.** Setelah login, atur Email Account di menu System > Email Accounts,
  lalu jadikan default. Akun default itulah yang dipakai untuk mengirim.
- **Simpan salinan `.env` prod di password manager tim.** `EMS_APP_ENCRYPTION_KEY` jangan pernah diganti
  atau hilang: kunci ini mengenkripsi token QR dan password Email Account.

## 4. nginx host (manual)

Template ada di `deployments/nginx/host-site.conf.example`. Satu file per domain:

```bash
sudo cp /srv/ems-prod/deployments/nginx/host-site.conf.example /etc/nginx/sites-available/ems-prod
sudo sed -i 's/DOMAIN/ems.example.com/; s/PORT/8081/g' /etc/nginx/sites-available/ems-prod

sudo cp /srv/ems-staging/deployments/nginx/host-site.conf.example /etc/nginx/sites-available/ems-staging
sudo sed -i 's/DOMAIN/staging.ems.example.com/; s/PORT/8080/g' /etc/nginx/sites-available/ems-staging

sudo ln -sf /etc/nginx/sites-available/ems-prod /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/ems-staging /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d ems.example.com -d staging.ems.example.com
```

DNS kedua domain harus sudah mengarah ke server sebelum menjalankan `certbot`. Setelah certbot selesai,
aktifkan baris `Strict-Transport-Security` di blok 443.

## 5. Cek, jalankan, buat Super Admin

Di tiap folder:

```bash
deployments/setup.sh check                    # harus "Ready"; kalau ada ✗, perbaiki dulu
docker compose up -d --build                  # migration jalan otomatis sebelum api
docker compose ps                             # semua running/healthy, "migrate" exited (0)
curl -fsS http://127.0.0.1:8081/api/v1/health/ready          # staging: 8080
docker compose run --rm api python -m app.cli create-superuser
```

Lalu login di browser:
1. Buat Email Account, jadikan default, lalu klik **Test**.
2. Buat Exhibition, Edition, Team, dan user.
3. Uji dari HP: import kecil, kirim QR, lalu scan di `/scanner/`.

## 6. Alur rilis

1. Merge ke `main`, lalu deploy ke **staging**:
   ```bash
   cd /srv/ems-staging && git pull && docker compose up -d --build
   ```
2. Uji di staging.
3. Kalau sudah oke, beri tag dari komputer developer:
   ```bash
   git tag v1.3.0 && git push origin v1.3.0
   ```
4. Deploy ke **prod**. Backup selalu dulu:
   ```bash
   cd /srv/ems-prod
   deployments/backup/backup.sh /srv/backups/ems-prod
   git fetch --tags && git checkout v1.3.0
   docker compose up -d --build
   docker compose ps && curl -fsS http://127.0.0.1:8081/api/v1/health/ready
   ```

Saat container diganti, ada jeda singkat (beberapa detik sampai semenit, lebih lama kalau migration
besar). Deploy di jam sepi.

## 7. Backup

Jalankan dari folder prod supaya yang di-backup adalah stack prod:

```cron
# crontab -e   (setiap hari 02:00)
0 2 * * * cd /srv/ems-prod && deployments/backup/backup.sh /srv/backups/ems-prod >> /var/log/ems-backup.log 2>&1
30 2 * * * find /srv/backups/ems-prod -mtime +30 -delete
```

- Salin `/srv/backups/ems-prod` ke luar server. Backup di disk yang sama ikut hilang kalau disk rusak.
- Jalankan `deployments/backup/drill.sh` minimal sebulan sekali (lihat `deployments/backup/README.md`).
- Staging tidak perlu backup harian.

## 8. Rollback

- **Rilis tanpa migration:** `git checkout <tag sebelumnya> && docker compose up -d --build`.
- **Rilis dengan migration:** hentikan `api`, `worker`, dan `beat`, restore backup sebelum deploy
  (`deployments/backup/restore.sh`), lalu checkout tag lama dan build.

## 9. Larangan dan jebakan

- **Jangan** `docker compose down -v` di prod. `-v` menghapus database.
- **Jangan** `make test`, `make e2e`, atau `make fmt` di server. Itu untuk komputer developer.
- **Jangan** salin database prod ke staging tanpa anonimisasi. Data visitor itu data pribadi.
- **Jangan** jalankan `setup.sh init` lagi di folder yang sudah berjalan. Kunci enkripsi baru membuat
  QR lama tidak terbaca. Script juga menolak kalau `.env` sudah ada.
- Selalu jalankan perintah dari **folder yang benar**. `docker compose ls` menampilkan kedua project.
  `docker compose -p ems-prod ps` bisa dipakai dari folder mana pun.
- RAM: dua stack lengkap butuh kira-kira 2× satu stack. Pantau dengan `docker stats`. Staging boleh
  dimatikan saat tidak dipakai (`docker compose stop`).
- nginx host harus **mengganti** `X-Forwarded-For` dengan `$remote_addr`, bukan menambahkan (`$proxy_add_x_forwarded_for`). Kalau server dipasang dari template lama, ubah baris itu. Tanpa ini, orang bisa memalsukan IP untuk melewati batas login dan batas form campaign.
- Form Campaign Link (`/r/...`) disajikan oleh container web, jadi nginx host tidak perlu diubah. Kalau tim marketing memasang tag di GTM yang memakai domain di luar Google, Meta, atau TikTok, tag itu diblokir browser sampai domainnya ditambahkan ke CSP `location /r/` di `deployments/nginx/default.conf`.
- Storage (`storage`, port 9000) tidak dibuka ke luar dan memang tidak perlu. Download Export dan
  Error Report import dialirkan lewat API.
