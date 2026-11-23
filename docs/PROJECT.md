# Struktur Proyek — XToolKit-Diego

[Pusat Dokumentasi](README.md) · [README Utama](../README.md) · [Keamanan](SAFETY.md)

Halaman ini menjelaskan susunan direktori, peran setiap modul utama, dan arsitektur **XToolKit-Diego**.

---

## 1. Peta Direktori & File Utama

Peluncur utama dan modul Python inti berada di root proyek agar perintah instalasi dan impor modul tetap konsisten di macOS maupun Windows.

| Lokasi | Peran |
| --- | --- |
| `run-macos.sh` | Peluncur POSIX native macOS (membuat `.venv`, memasang Textual + Frida 16.5.9, membuka dasbor Step 0–4 atau mode `--check`/`--list`) |
| `XToolKit-Diego.command` | Pintasan klik-ganda Finder di macOS yang memanggil `run-macos.sh` |
| `macos_runner.py` | Adapter native macOS untuk Step 0–4 (preflight pemulihan ADB, `--open-only`, `--reinject`, verifikasi akun ketat tanpa `--force`) |
| `run-all.ps1` | Peluncur utama Windows PowerShell (Dasbor Textual bawaan & CLI terpandu Step 0–4) |
| `tui.py` | Antarmuka dasbor modern Textual (*cyber-slate*) berbahasa Indonesia, manajemen subproses, log teknis realtime, tombol Hentikan & Inject Ulang |
| `tui_core.py` | Logika murni (pure helpers): definisi `STAGES` (0–4), format log berwarna, pembacaan laporan segar, dan interpretasi hasil |
| `device_diagnostics.py` | Pemantauan koneksi ADB berkala, diagnostik perangkat, dan pemulihan otomatis (`adb start-server`, `disconnect`, `connect`, `kill-server`) |
| `stage_history.py` | Penyimpanan dan pemulihan riwayat eksekusi per akun pada `logs/stage-history/` |
| `ultra0.py` | Mesin inti integrasi Android, ADB, Frida, dan Google Play BillingClient (termasuk dukungan `--open-only` dan pemulihan ADB saat `pick_device()`) |
| `setup_env.py` | Utilitas persiapan lingkungan Windows (penemuan/unduhan Platform-Tools & Frida) |
| `device_selector.py` | Pemilihan perangkat ADB deterministik berbasis boot UUID & deteksi aplikasi Google One |
| `query_sku.py` | Utilitas kueri produk/penawaran Google Play |
| [`tools/windows/`](../tools/windows/README.md) | Pintasan opsional setup manual Windows (`setup-environment.bat`) |
| [`legacy/windows/`](../legacy/windows/README.md) | Pintasan `.bat` historis (sebagian memakai `--force`; tidak disarankan untuk pemakaian harian) |
| `scripts/` | Skrip utilitas runtime (`diagnose-activity.py`, `runtime-lookup.py`, `user-errors.ps1`) |
| `assets/` | Hook Frida (`assets/frida/billing.js`) dan modul Android (`assets/modules/`) |
| `tests/` | Suite pengujian regresi offline berbasis *mock* (tanpa koneksi ke perangkat atau transaksi nyata) |
| `docs/` | Seluruh dokumentasi pengguna & teknis dalam Bahasa Indonesia |
| `images/` | Tangkapan layar antarmuka dasbor **XToolKit-Diego** |

---

## 2. Arsitektur Singkat

```text
run-macos.sh / XToolKit-Diego.command (macOS)   ──┐
                                                  ├──► tui.py (Dasbor Textual Modern)
run-all.ps1 (Windows PowerShell)                ──┘       ├──► tui_core.py (Pemetaan Step 0–4 & Parser)
                                                          ├──► device_diagnostics.py (Pemulihan ADB)
                                                          ├──► stage_history.py (Riwayat Per Akun)
                                                          └──► macos_runner.py / run-all.ps1 CLI
                                                                   └──► ultra0.py + assets/frida/billing.js
```

Prinsip arsitektur utama:

1. **Pemisahan UI dan mesin:** `tui.py` fokus pada tampilan interaktif, kontrol proses, dan log realtime; seluruh interaksi Android/Frida/Billing tetap dijalankan melalui adapter native (`macos_runner.py` / `run-all.ps1`) dan `ultra0.py`.
2. **Pemulihan ADB terpadu:** Baik dasbor, adapter macOS, maupun mesin inti memanggil rutinitas pemulihan ADB yang sama di `device_diagnostics.py` agar kasus `127.0.0.1:16384 offline` dan `Connection refused` ditangani konsisten.
3. **Pengujian offline aman:** Seluruh pengujian di `tests/` menggunakan *mock* subproses/ADB dan tidak pernah mengeksekusi transaksi Google Play sungguhan.

---

## 3. Dokumen Pendukung

- [Penafian Lengkap (`DISCLAIMER.md`)](../DISCLAIMER.md)
- [Kebijakan Keamanan (`SECURITY.md`)](../SECURITY.md)
- [Panduan Kontribusi (`CONTRIBUTING.md`)](../CONTRIBUTING.md)
- [Pemberitahuan Pihak Ketiga (`THIRD_PARTY_NOTICES.md`)](../THIRD_PARTY_NOTICES.md)
