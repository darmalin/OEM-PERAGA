# Production dan staging di satu server

Dua stack Docker Compose yang **terpisah total** di satu mesin. Yang dipakai bersama hanya
Docker, nginx host, dan sertifikat TLS. Database, Redis, storage, worker, secret, dan email
masing-masing punya sendiri.

```
                       ┌── ems.example.com ──────► 127.0.0.1:8081 ─► stack "ems-prod"
internet ─► nginx host ┤                                              (postgres, redis, storage,
  (TLS, certbot)       │                                               api, worker, beat, nginx)
                       └── staging.ems.example.com ► 127.0.0.1:8080 ─► stack "ems" (staging)
```

Ganti `ems.example.com` / `staging.ems.example.com` dengan domain asli.

## 1. Folder

Satu clone repo per lingkungan. Jangan pernah menjalankan prod dari folder staging.

| | Staging | Production |
|---|---|---|
| Folder | folder staging yang sekarang (di sini ditulis `/srv/ems-staging`) | `/srv/ems-prod` |
| Kode | branch `main` (terbaru) | tag rilis, mis. `v1.3.0` |
| Project Compose | `ems` (yang sudah ada) | `ems-prod` |
| Port lokal | `127.0.0.1:8080` | `127.0.0.1:8081` |

```bash
sudo mkdir -p /srv/ems-prod && sudo chown "$USER" /srv/ems-prod
git clone git@github.com:darmalin/OEM-PERAGA.git /srv/ems-prod
```

Nama project memisahkan semuanya: container, network, image, dan **volume data**
(`ems-prod_postgres-data` vs `ems_postgres-data`). Salah nama project berarti salah database.

## 2. `.env` per lingkungan

`.env` tidak ada di git. Buat sendiri di tiap folder dan jangan menyalin `.env` staging ke prod.

Dua baris pertama **wajib**:

- `COMPOSE_FILE=compose.yaml`. Tanpa ini Compose otomatis ikut memuat `compose.override.yaml`, yang
  merupakan mode **dev**: hot reload, bind mount, Mailpit, port DB dibuka, dan kunci enkripsi dev.
- `COMPOSE_PROJECT_NAME` memisahkan data prod dari staging.

```dotenv
# /srv/ems-prod/.env
COMPOSE_FILE=compose.yaml
COMPOSE_PROJECT_NAME=ems-prod
EMS_HTTP_PORT=127.0.0.1:8081          # hanya bisa diakses dari nginx host, bukan dari internet

EMS_ENVIRONMENT=production            # mematikan /docs dan OpenAPI
EMS_PUBLIC_BASE_URL=https://ems.example.com   # dipakai di link email (reset password, dll.)
EMS_SESSION_COOKIE_NAME=ems_session
EMS_REPORT_TIMEZONE=Asia/Jakarta

POSTGRES_USER=ems
POSTGRES_DB=ems
POSTGRES_PASSWORD=<acak>
STORAGE_ACCESS_KEY=<acak>
STORAGE_SECRET_KEY=<acak>
EMS_APP_ENCRYPTION_KEY=<acak, lihat di bawah>

# Cadangan kalau belum ada Email Account default di menu System > Email Accounts
EMS_EMAIL_FROM=EMS <no-reply@ems.example.com>
EMS_SMTP_HOST=smtp.example.com
EMS_SMTP_PORT=587
EMS_SMTP_USE_TLS=true
EMS_SMTP_USERNAME=<user>
EMS_SMTP_PASSWORD=<password>
```

Staging memakai isi yang sama dengan nilai berbeda:

> **Staging yang sudah berjalan memakai nama project `ems`** (bawaan `compose.yaml`). Datanya ada di
> volume `ems_postgres-data`. Pertahankan `COMPOSE_PROJECT_NAME=ems` untuk staging. Kalau diganti jadi
> `ems-staging`, Compose membuat volume baru yang **kosong**, dan staging terlihat seperti kehilangan
> data. Cek dengan `docker volume ls | grep postgres-data`.

```dotenv
COMPOSE_PROJECT_NAME=ems                 # staging lama; ems-staging hanya kalau dari nol
EMS_HTTP_PORT=127.0.0.1:8080
EMS_ENVIRONMENT=staging
EMS_PUBLIC_BASE_URL=https://staging.ems.example.com
EMS_SESSION_COOKIE_NAME=ems_staging_session
```

Lalu isi **secret staging sendiri**, yang tidak boleh sama dengan prod.

Membuat secret langsung ke `.env` tanpa menampilkannya di layar:

```bash
cd /srv/ems-prod
for k in POSTGRES_PASSWORD STORAGE_ACCESS_KEY STORAGE_SECRET_KEY; do
  sed -i "s|^$k=.*|$k=$(openssl rand -hex 24)|" .env
done
# Kunci Fernet: 32 byte, base64 versi URL-safe
sed -i "s|^EMS_APP_ENCRYPTION_KEY=.*|EMS_APP_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')|" .env
chmod 600 .env
```

> **`EMS_APP_ENCRYPTION_KEY` jangan pernah diganti setelah prod berjalan.** Kunci ini mengenkripsi
> token QR dan password Email Account. Kalau hilang atau diganti, semua QR dan akun email harus dibuat
> ulang. Simpan salinannya di password manager tim.

Cek bahwa konfigurasinya benar sebelum menyalakan stack:

```bash
docker compose config --services   # TIDAK boleh ada "mailpit" atau "web"
docker compose config | grep -E "name:|8081"
```

## 3. nginx host

Satu file per domain di `/etc/nginx/sites-available/`. TLS dari certbot.

```nginx
# /etc/nginx/sites-available/ems-prod
server {
    listen 443 ssl http2;
    server_name ems.example.com;
    # ssl_certificate ... (diisi certbot)

    client_max_body_size 25m;                 # upload Excel
    add_header Strict-Transport-Security "max-age=31536000" always;

    location /scanner/ {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # Scanner butuh kamera; container mengirim camera=() untuk halaman desk.
        proxy_hide_header Permissions-Policy;
        add_header Permissions-Policy "camera=(self), microphone=(), geolocation=()" always;
    }

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}

server {
    listen 80;
    server_name ems.example.com;
    return 301 https://$host$request_uri;
}
```

Untuk staging, salin file itu dengan domain staging dan port `8080`. Lalu:

```bash
sudo ln -sf /etc/nginx/sites-available/ems-prod /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d ems.example.com
```

## 4. Deploy pertama prod

```bash
cd /srv/ems-prod
git fetch --tags && git checkout v1.0.0          # tag rilis yang sudah lolos di staging
docker compose up -d --build                      # migrate jalan otomatis sebelum api
docker compose ps                                 # semua "running"/"healthy", migrate "exited (0)"
curl -fsS http://127.0.0.1:8081/api/v1/health/ready
docker compose run --rm api python -m app.cli create-superuser
```

Setelah login sebagai Super Admin:

1. Tambah Email Account produksi, set sebagai default, lalu klik **Test**.
2. Buat Exhibition, Edition, Team, dan user.
3. Coba sekali dari HP: import kecil, kirim QR, lalu scan di `/scanner/`.

## 5. Alur rilis

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

`--build` membuat image baru, lalu Compose mengganti container. Selama `migrate` berjalan dan api
menyala ulang, ada jeda singkat (biasanya beberapa detik sampai semenit). Deploy di jam sepi, apalagi
kalau ada migration besar seperti membuat index di tabel lead.

## 6. Backup

Jalankan dari folder prod supaya yang di-backup adalah stack prod:

```cron
# crontab -e   (setiap hari 02:00)
0 2 * * * cd /srv/ems-prod && deployments/backup/backup.sh /srv/backups/ems-prod >> /var/log/ems-backup.log 2>&1
```

- Salin `/srv/backups/ems-prod` ke luar server (object storage, server lain). Backup di disk yang
  sama ikut hilang kalau disk rusak.
- Hapus backup yang berumur lebih dari 30 hari:
  `find /srv/backups/ems-prod -mtime +30 -delete`.
- Jalankan `deployments/backup/drill.sh` minimal sebulan sekali dan setelah migration besar
  (lihat `deployments/backup/README.md`).
- Staging tidak perlu backup harian.

## 7. Rollback

- **Rilis tanpa migration:** `git checkout <tag sebelumnya> && docker compose up -d --build`.
- **Rilis dengan migration:** downgrade database tidak dijamin aman. Hentikan `api`, `worker`, dan
  `beat`, restore backup sebelum deploy (`deployments/backup/restore.sh`, lihat README), lalu
  checkout tag lama dan build.

## 8. Larangan dan jebakan

- **Jangan** `docker compose down -v` di prod. `-v` menghapus volume database.
- **Jangan** `make test`, `make e2e`, atau `make fmt` di server. Itu untuk komputer developer.
  `make test` menjalankan migration naik-turun di database `ems_test`.
- **Jangan** salin database prod ke staging tanpa anonimisasi. Data visitor itu data pribadi.
- **Email staging**: pakai akun SMTP terpisah atau sandbox, supaya staging tidak mengirim QR ke
  visitor asli.
- Semua perintah `docker compose` dijalankan **dari folder yang benar**. `docker compose ls`
  menampilkan dua project. `docker compose -p ems-prod ps` bisa dipakai dari folder mana pun.
- RAM: dua stack lengkap butuh kira-kira 2× pemakaian staging sekarang. Pantau dengan `docker stats`.
  Kalau sempit, staging boleh dimatikan saat tidak dipakai (`docker compose stop` di folder staging).
- Port Postgres, Redis, dan storage **tidak** dibuka di `compose.yaml`. Biarkan begitu. Akses DB lewat
  `docker compose exec postgres psql ...`.
