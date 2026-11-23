# AGENTS.md — Panduan Agen Pengembang XToolKit-Diego

Instruksi kerja untuk agen pemrograman (*coding agents*) di repositori **XToolKit-Diego**. Baca berkas ini bersama [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md), dan [SECURITY.md](SECURITY.md) sebelum mengubah kode. Selalu utamakan implementasi aktual pada cabang target dibanding catatan tugas atau tangkapan layar lama.

---

## 1. Tujuan Proyek & Batas Arsitektur

**XToolKit-Diego** adalah perangkat utilitas terminal Python berbahasa Indonesia untuk **macOS** dan **Windows** yang digunakan untuk diagnostik koneksi Android, pemulihan ADB otomatis, pemeriksaan penawaran Google AI Pro melalui Google One & Google Play, serta peluncuran Google Play Billing pada **Step 0 hingga Step 4**.

Antarmuka Textual harus tetap berfungsi sebagai **lapisan orkestrasi UI** atas mesin yang sudah ada — bukan implementasi ulang logika Android, Frida, akun, maupun Google Play Billing.

| Modul / Berkas | Tanggung Jawab |
| --- | --- |
| `run-macos.sh`, `XToolKit-Diego.command`, `macos_runner.py` | Peluncur POSIX native macOS & adapter tahapan **Step 0–4** (termasuk `--open-only`, `--reinject`, pemulihan ADB di `preflight()`). **Jangan pernah memanggil `setup_env.py` atau skrip `.ps1`/`.bat` Windows di macOS.** |
| `run-all.ps1` | Peluncur utama Windows PowerShell (tanpa argumen membuka dasbor Textual; `-Step 0..4`, `-Cli`, `-AllStages`, `-Reinject` memakai jalur CLI). |
| `tui.py` | Dasbor modern Textual (*cyber-slate*) berbahasa Indonesia, manajemen subproses, tombol `■ Hentikan`, toggle Auto Step 2, tombol `↻ Inject Ulang Step N`, dan Log Teknis Realtime. |
| `tui_core.py` | Fungsi murni: definisi `STAGES` (**0–4**), konstruksi perintah per platform, pemformatan log berwarna (`format_realtime_log`), pembacaan laporan segar, dan interpretasi status (`billing_opened`, `listed`, dll.). |
| `device_diagnostics.py` | Pemantauan koneksi ADB berkala, diagnostik perangkat, dan rutinitas pemulihan ADB terpusat (`recover_adb_connection()`, `parse_adb_devices()`, `poll_connection()`). |
| `stage_history.py` | Pencatatan dan pembacaan riwayat eksekusi per akun di `logs/stage-history/`. |
| `ultra0.py` | Mesin inti integrasi Android/ADB/Frida 16.5.9/Google Play Billing (termasuk pemulihan ADB pada `pick_device()` dan mode cepat `--open-only`). Perlakukan perubahan di sini dengan kehati-hatian tinggi. |
| `setup_env.py`, `scripts/`, `tools/windows/` | Deteksi & penyiapan lingkungan khusus Windows. Pintasan lama di `legacy/windows/*.bat` bukan pintu masuk utama; pertahankan jalur relatifnya dan peringatkan risiko `--force`. |
| `tests/` | Pengujian regresi **offline (mock)**. Jangan pernah menghubungkan tes ke akun Google nyata atau melakukan pembelian. |
| `README.md`, `docs/`, `images/`, `DISCLAIMER.md`, `SECURITY.md`, `THIRD_PARTY_NOTICES.md` | Dokumentasi Bahasa Indonesia, tangkapan layar UI, penafian, keamanan, dan lisensi pihak ketiga. |

### Kontrak Tahapan Aktif (Step 0–4)

Kontrak tahapan resmi saat ini adalah **5 tahap (Step 0–4)** — **Step 5 telah dihapus**:

| Nomor | Label UI | Kode Penawaran | Keterangan |
| --- | --- | --- | --- |
| **0** | `Cek Lingkungan` | — | Cek/siapkan ADB, root, dan Frida 16.5.9 (dapat mengubah konfigurasi emulator) |
| **1** | `Cek Penawaran` | — | Verifikasi akun Google Play & baca penawaran (tanpa checkout) |
| **2** | `Pro 12 Bulan` | `12months-eft` | Buka Google Play Billing (`--open-only`), dukung **Inject Ulang** |
| **3** | `Pro +6 Bulan` | `6months-eft` | Buka pembaruan langganan +6 bulan ke-1 (`--open-only`), dukung **Inject Ulang** |
| **4** | `Pro +6 Bulan (Ke-2)` | `6months-eft-2` | Buka pembaruan langganan +6 bulan ke-2 (`--open-only`), dukung **Inject Ulang** |

---

## 2. Batasan Port macOS

- `run-macos.sh` memilih Python 3.11–3.13 (fallback `python3 >= 3.10`), membuat `.venv`, memasang Textual + **Frida 16.5.9**, dan menjalankan dasbor **Step 0–4** (atau `--check` / `--list`).
- Adapter `macos_runner.py` secara sengaja **tidak mendukung `--force`** maupun pergantian akun otomatis. Jangan melewati verifikasi perangkat tunggal, akun Google Play aktif, ID penawaran, atau pemeriksaan fase awal Rp0/US\$0.
- Pemanggilan CLI `macos_runner.py` untuk Step 2–4 mewajibkan flag izin eksplisit (`--confirm-checkout`). Mode `--reinject` melewati pengulangan Step 0/Step 1 untuk langsung memunculkan ulang dialog billing pada tahap yang sama.
- Pengujian macOS di CI/lokal dibatasi pada *mock* unit dan integrasi; **jangan pernah mengklaim** keberhasilan uji lokal sebagai verifikasi transaksi nyata di perangkat Mac/MuMu.

---

## 3. Aturan Keselamatan Non-Negosiasi

1. **Tidak ada transaksi otomatis saat aplikasi dibuka:** Menjalankan `sh run-macos.sh` atau `.\run-all.ps1` tanpa argumen hanya membuka dasbor Textual. Step 0 dapat mengubah konfigurasi ADB/Frida/emulator sehingga tidak boleh diklaim bebas efek samping.
2. **Step 2–4 berinteraksi dengan Google Play Billing nyata:** Jangan pernah menjalankan checkout sungguhan di dalam tes/CI. Mode `--open-only` segera selesai saat respons `{'ev': 'launched', 'code': 0}` diterima (status `billing_opened`) agar keputusan pembayaran tetap di tangan pengguna pada layar Android.
3. **Status lokal bukan bukti langganan aktif:** Pertahankan kompatibilitas status internal `billing_opened` dan `checkout_requested` pada kode/fixture, tetapi jangan pernah menyatakannya sebagai bukti aktivasi, gratis, atau perpanjangan berhasil. Pengguna wajib memverifikasi sendiri di Google Play sebelum lanjut ke tahap berikutnya.
4. **Pertahankan validasi akun & perangkat:** Jangan menjadikan `--force` atau `-Force` sebagai nilai bawaan, dan jangan menyiratkan bahwa fase awal Rp0/US\$0 menjamin langganan gratis.
5. **Kontrol `■ Hentikan` & `⏻ Keluar` yang aman:** Tombol `■ Hentikan` (`x`) harus mampu menghentikan proses aktif maupun pemulihan ADB tanpa meninggalkan proses yatim (*orphan*) atau mematikan proses sistem lain, serta membatalkan antrean Auto Step 2. Jelaskan bahwa menghentikan aplikasi tidak membatalkan transaksi yang sudah disetujui di Google Play.
6. **Privasi ketat:** Jangan pernah mencetak, mengkomit, atau mengekspos email penuh, kata sandi, kode 2FA, data kartu, `offerToken` / `purchaseToken`, serial perangkat nyata, atau laporan mentah (`logs/`, `ultra0-report/`, `accounts.txt`).
7. **Kepatuhan lisensi pihak ketiga:** Pertahankan pemberitahuan lisensi MIT hulu secara utuh pada [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) tanpa mengasumsikan lisensi tersebut otomatis berlaku untuk kontribusi baru yang tidak terkait.

---

## 4. Kontrak UX Dasbor Textual (`XToolKit-Diego`)

- **Identitas & bahasa:** Seluruh teks UI, status, tombol, dan bantuan menggunakan **Bahasa Indonesia** dengan merek **`✦ XToolKit-Diego`**. Jangan menambahkan kembali tautan **Support**, **Original**, atau **Maintained** di UI maupun dokumentasi pengguna.
- **Tata letak modern *cyber-slate*:** Tombol aksi lebar dengan `height: 3`, `border: round`, teks terpusat (`content-align: center middle; text-align: center;`), kartu telemetri perangkat & akun di atas, daftar Step 0–4 & kontrol di sisi kiri, serta panel kontrol + Status Langsung + Log Teknis Realtime di area kanan yang lebar.
- **Auto Step 2 & Inject Ulang:**
  - Toggle `⚡ Auto Step 2: AKTIF / MANUAL` mengendalikan kelanjutan otomatis Step 1 → Step 2 saat `12months-eft` (fase awal Rp0/US\$0) terverifikasi.
  - Step 2, Step 3, dan Step 4 masing-masing memunculkan tombol **`↻ Inject Ulang Step N`** (pintasan `i`) segera setelah `billing_opened` agar popup billing yang tertutup (*terclose*) bisa dibuka kembali dalam 1 klik.
- **Log Teknis Realtime bersih:** Konsol log otomatis tampil saat startup (`debug_visible = True`), berkode warna dengan stempel waktu. Perubahan mode (Auto/Manual) dan proses pemulihan ADB **tidak boleh** membanjiri log teknis.
- **Pemulihan ADB otomatis:** Menangani `adb start-server`, `127.0.0.1:16384 offline`, `Connection refused`, `adb disconnect`, hingga `kill-server` -> `start-server` -> `connect`. Pemulihan senyap di latar belakang tidak boleh menimpa label tombol utama `#quickstart` secara permanen.
- **Penguncian saat sibuk:** Saat proses berjalan, kunci seluruh pemicu tahap baru (baik tombol maupun pintasan keyboard) dalam **logika maupun tampilan**, sambil tetap membuka akses **`■ Hentikan` (`x`)**, **Panduan**, dan **Log Teknis Realtime**.
- **Responsif:** Uji geometri, visibilitas tombol, dan scroll pada ukuran terminal ringkas (`90×20`), normal (`110×35`), hingga lebar (`136×42`) tanpa teks terpotong atau tumpang tindih.

---

## 5. Alur Pengembangan & Verifikasi

1. Utamakan patch kecil dan terarah; pisahkan interaksi UI (`tui.py`), helper murni (`tui_core.py`), dan diagnostik ADB (`device_diagnostics.py`).
2. Tambahkan uji regresi *mock* untuk setiap perbaikan bug.
3. Jalankan pemeriksaan sesuai sistem operasi host:

   **macOS Terminal (`zsh` / `bash`):**

   ```sh
   .venv/bin/python -m unittest tests/test_docs_navigation.py tests/test_adb_recovery.py tests/test_tui.py tests/test_macos.py tests/test_tui_connection_offer.py tests/test_connection_guide.py tests/test_offer_explorer.py -v
   .venv/bin/python -m py_compile tui.py tui_core.py macos_runner.py device_diagnostics.py
   sh -n run-macos.sh
   ```

   **Windows PowerShell:**

   ```powershell
   python -m unittest discover -s tests -v
   python -m py_compile tui.py tui_core.py device_diagnostics.py
   ```

4. Perbarui [README.md](README.md), halaman terkait di `docs/`, dan tangkapan layar di `images/` setiap kali perintah, label UI, tahapan, atau perilaku keamanan berubah.
5. Dokumentasi pengguna menggunakan **Bahasa Indonesia tunggal** (hanya `README.md` di root dan halaman-halaman di `docs/`, tanpa `docs/i18n/` maupun README multi-bahasa). Validasi selalu dengan `tests/test_docs_navigation.py`.

---

## 6. Sumber Kebenaran & Pelaporan

Jika terjadi perbedaan informasi, ikuti urutan prioritas berikut:
1. Batasan keamanan & privasi
2. Kode sumber aktual dan suite pengujian
3. [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), dan dokumentasi pengguna

Dalam setiap ringkasan perubahan, selalu bedakan secara eksplisit antara hal yang **sudah diverifikasi** (tes/kompilasi yang benar-benar dijalankan) dan hal yang **belum diverifikasi** (perangkat keras nyata Windows/MuMu, transaksi Google Play langsung, atau perangkat Android fisik).
