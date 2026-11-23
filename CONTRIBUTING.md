# Panduan Kontribusi — XToolKit-Diego

[README Utama](README.md) · [Panduan Agen (`AGENTS.md`)](AGENTS.md) · [Keamanan](SECURITY.md) · [Pusat Dokumentasi](docs/README.md)

Terima kasih telah membantu menyempurnakan **XToolKit-Diego** untuk **macOS** dan **Windows**. Panduan ini menjelaskan standar pelaporan masalah, alur pengembangan, pengujian offline, serta aturan dokumentasi proyek.

---

## 1. Melaporkan Masalah (Bug Report)

Saat melaporkan kendala, sertakan informasi berikut agar masalah cepat direproduksi:

- Sistem operasi (versi macOS / Windows), versi Python, dan versi emulator/Android (mis. MuMuPlayer + Android 12).
- Perintah atau tombol dasbor yang dijalankan (`sh run-macos.sh`, `.\run-all.ps1`, **`⚡ Perbaiki ADB`**, **`↻ Inject Ulang`**, dll.).
- Cuplikan pesan error relevan beserta langkah reproduksi.
- **Wajib samarkan data sensitif:** jangan pernah menyertakan email Google penuh, kata sandi, kode OTP/2FA, detail kartu, `offerToken` / `purchaseToken`, serial perangkat unik, atau file mentah dari `logs/` dan `ultra0-report/`.

---

## 2. Alur Cabang (Branch) & Rilis

- **`main`** adalah cabang rilis stabil; jangan mengembangkan fitur baru atau menata ulang struktur file secara langsung di `main`.
- **`dev`** adalah cabang integrasi utama. Buat cabang fitur/perbaikan dari `dev` dan ajukan *Pull Request* dengan target **`dev`**.
- Setelah ditinjau dan seluruh pengujian lulus, promosikan `dev` → `main` melalui PR terpisah. Rilis hanya dipublikasikan dari cabang `main` yang sudah teruji.

---

## 3. Prinsip Perubahan Kode (macOS & Windows)

- **Tahapan tetap fokus Step 0–4:** pertahankan pemetaan numerik **Step 0 (Cek Lingkungan)**, **Step 1 (Cek Penawaran)**, **Step 2 (Pro 12 Bulan)**, **Step 3 (Pro +6 Bulan)**, dan **Step 4 (Pro +6 Bulan Ke-2)**. Jangan mengembalikan Step 5 tanpa kesepakatan desain.
- **Pemisahan antarmuka dan mesin inti:** `tui.py` hanya mengelola interaksi, tampilan modern *cyber-slate*, dan orkestrasi subproses; aturan murni berada di `tui_core.py`; pemulihan ADB di `device_diagnostics.py`; sedangkan logika Android/Frida/Billing tetap melalui `macos_runner.py`, `run-all.ps1`, dan `ultra0.py`.
- **Aturan khusus macOS:** `run-macos.sh` dan `macos_runner.py` tidak boleh bergantung pada PowerShell maupun `setup_env.py` milik Windows, dan tidak menyediakan flag `--force`.
- **Pengujian berbasis mock:** setiap perbaikan bug atau fitur baru wajib menyertakan uji regresi *mock* di `tests/`. **Jangan pernah menjalankan transaksi Google Play Billing sungguhan** di pengujian otomatis atau CI.

---

## 4. Menjalankan Pengujian Sebelum Mengajukan Perubahan

Pasang dependensi antarmuka (`requirements-tui.txt`), lalu jalankan pengujian menggunakan shell bawaan sistem operasi Anda (**tanpa perangkat Android maupun transaksi nyata**):

### macOS Terminal (`zsh` / `bash` — tanpa PowerShell)

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m py_compile tui.py tui_core.py macos_runner.py device_diagnostics.py
sh -n run-macos.sh
```

Atau jalankan grup pengujian inti & dokumentasi secara terarah:

```sh
.venv/bin/python -m unittest \
  tests/test_docs_navigation.py \
  tests/test_adb_recovery.py \
  tests/test_tui.py \
  tests/test_macos.py \
  tests/test_tui_connection_offer.py \
  tests/test_connection_guide.py \
  tests/test_offer_explorer.py -v
```

### Windows PowerShell

```powershell
python -m pip install -r requirements-tui.txt
python -m unittest discover -s tests -v
python -m py_compile tui.py tui_core.py device_diagnostics.py
```

Jika Node.js dan PowerShell tersedia di Windows, jalankan pula pengujian JavaScript & PowerShell offline:

```powershell
node --test tests/test_activity_lookup.test.mjs tests/test_subscription_update.test.mjs
pwsh -File ./tests/test_report_identity.ps1
pwsh -File ./tests/test_terminal_prompts.ps1
pwsh -File ./tests/test_user_errors.ps1
```

Pengujian offline yang lulus **bukan bukti** kompatibilitas perangkat keras nyata (MuMuPlayer/Android fisik) maupun keberhasilan pembayaran di Google Play. Selalu bedakan hasil **terverifikasi** dan **belum diverifikasi di perangkat nyata** pada ringkasan PR.

---

- Pertahankan salinan pemberitahuan lisensi pihak ketiga di [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
