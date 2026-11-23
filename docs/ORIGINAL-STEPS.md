# Referensi Tahapan Step 0–4 — XToolKit-Diego

[Pusat Dokumentasi](README.md) · [README Utama](../README.md) · [Panduan Teknis Mendalam](DETAILED-GUIDE.md)

> **Catatan Penting:** Rangkaian 12 + 6 + 6 bulan pada Step 2–4 merupakan alur historis tahapan penawaran dan **bukan jaminan layanan gratis atau perpanjangan otomatis**. Kelayakan akun, nominal tagihan, dan masa berlaku akhir selalu ditentukan oleh Google Play.

---

## 1. Pemetaan Tahapan Aktif (Step 0–4)

**XToolKit-Diego** berfokus pada lima tahap inti (**Step 0 hingga Step 4**):

| Tahap | Nama Tahap | Opsi Python (`ultra0.py`) | Keterangan |
| --- | --- | --- | --- |
| **Step 0** | Cek Lingkungan | `--check` | Memeriksa ADB, perangkat, akses root, Google Play/One, dan Frida 16.5.9 |
| **Step 1** | Cek Penawaran | `--list --plan pro12` | Membaca daftar penawaran akun aktif tanpa membuka checkout |
| **Step 2** | Pro 12 Bulan | `--plan pro12 --open-only` | Membuka Google Play Billing untuk penawaran awal 12 bulan (`12months-eft`) |
| **Step 3** | Pro +6 Bulan | `--plan pro6 --stack --open-only` | Membuka pembaruan langganan tambahan 6 bulan pertama (`6months-eft`) |
| **Step 4** | Pro +6 Bulan (Ke-2) | `--plan pro6b --stack --open-only` | Membuka pembaruan langganan tambahan 6 bulan kedua (`6months-eft-2`) |

> Tahap opsional lama (Step 5) telah dihapus dari antarmuka dan alur kerja **XToolKit-Diego** agar proses lebih ringkas dan fokus pada alur Step 0–4.

---

## 2. Perintah Setara di CLI

### macOS (`run-macos.sh` & `macos_runner.py`)

```sh
# Step 0: Cek lingkungan (tanpa checkout)
sh run-macos.sh --check

# Step 1: Daftar penawaran (tanpa checkout)
sh run-macos.sh --list

# Membuka dasbor langsung ke tahap tertentu
sh run-macos.sh --step 2
sh run-macos.sh --step 3 --sequence

# Inject ulang popup billing langsung via adapter macOS
.venv/bin/python macos_runner.py --step 2 --confirm-checkout --reinject
```

### Windows PowerShell (`run-all.ps1`)

```powershell
# Step 0: Cek lingkungan (tanpa checkout)
.\run-all.ps1 -Step 0

# Step 1: Daftar penawaran (tanpa checkout)
.\run-all.ps1 -Step 1

# Step 2: Pro 12 Bulan (membuka Google Play Billing)
.\run-all.ps1 -Step 2 -Email akun@gmail.com

# Step 3: Pro +6 Bulan
.\run-all.ps1 -Step 3 -Email akun@gmail.com

# Step 4: Pro +6 Bulan (Ke-2)
.\run-all.ps1 -Step 4 -Email akun@gmail.com

# Rangkaian terpandu Step 2–4 dengan konfirmasi angka (1/2/0)
.\run-all.ps1 -AllStages

# Melanjutkan dari Step 3 tanpa mengulang Step 2 (jika paket 12 bulan sudah aktif)
.\run-all.ps1 -AllStages -StartStep 3
```

---

## 3. Cara Kerja Pembaruan Langganan (`--stack`) di Step 3 & Step 4

Untuk produk yang sudah memiliki langganan aktif, mesin Python membaca `purchaseToken` langganan aktif yang cocok milik akun saat ini lalu menyusun parameter `BillingFlowParams.SubscriptionUpdateParams` agar Google Play membuka layar pembaruan langganan.

- Jika `purchaseToken` tidak ditemukan, kedaluwarsa, milik akun berbeda, atau mode pembaruan tidak didukung, sistem **menolak secara aman (fail-closed)** dan tidak memaksa membuat pembelian baru secara diam-diam.
- Begitu layar pembayaran terbuka (`Google Play billing flow response: {'ev': 'launched', 'code': 0}`), proses selesai dengan status `billing_opened` sehingga Anda memegang kendali penuh di layar Android.
- Bila popup tertutup (*terclose*), tombol **`↻ Inject Ulang Step 3`** / **`↻ Inject Ulang Step 4`** di dasbor dapat memunculkannya lagi kapan saja.

---

## 4. Peringatan Tentang Skrip Legacy Windows (`legacy/windows/`)

Direktori `legacy/windows/` menyimpan pintasan `.bat` lawas demi kompatibilitas historis. Pintasan lama tersebut menyertakan `--force` yang **melewati verifikasi kecocokan akun Google Play** dan berisiko membuka transaksi pada akun yang keliru. Gunakan selalu peluncur utama **`run-all.ps1`** (Windows) atau **`run-macos.sh`** (macOS).
