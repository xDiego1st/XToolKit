#Requires -Version 5.1
# Pesan kesalahan terminal berbahasa Indonesia untuk XToolKit-Diego.
function Get-UserIssue {
    param([string]$Code)
    if ([string]::IsNullOrWhiteSpace($Code)) { $Code = "unknown" }
    switch ($Code.ToLowerInvariant()) {
        { $_ -in @("payment_security_blocked", "checkout_security_blocked") } {
            return [pscustomobject]@{
                Title = "Google Play memblokir pembayaran ini (OR-REH-04)"
                Action = "Periksa keamanan akun Google dan peringatan Google Payments. Jangan ulangi checkout dulu."
            }
        }
        "already_subscribed" {
            return [pscustomobject]@{
                Title = "Paket Google AI Pro ini sudah aktif"
                Action = "Periksa tanggal perpanjangan di Google Play; jangan ulangi langkah ini."
            }
        }
        "ineligible" {
            return [pscustomobject]@{
                Title = "Akun ini tidak memenuhi syarat untuk penawaran tersebut"
                Action = "Periksa ketentuan promo di Google Play."
            }
        }
        "purchase_unavailable" {
            return [pscustomobject]@{
                Title = "Google Play menyatakan item ini tidak tersedia untuk dibeli"
                Action = "Periksa akun Play Store, negara, dan ketersediaan Google One."
            }
        }
        "today_price_unverified" {
            return [pscustomobject]@{
                Title = "Nominal tagihan hari ini tidak dapat dipastikan"
                Action = "Periksa harga checkout pada layar Android sebelum mencoba lagi."
            }
        }
        "trial_duration_unverified" {
            return [pscustomobject]@{
                Title = "Durasi masa percobaan tidak dapat dipastikan"
                Action = "Periksa durasi yang ditampilkan Google Play pada layar Android."
            }
        }
        "backup_payment_methods_prompt" {
            return [pscustomobject]@{
                Title = "Google Play menanyakan metode pembayaran cadangan"
                Action = "Tinjau opsi tersebut di Google Play; ini belum mengonfirmasi langganan."
            }
        }
        "processing" {
            return [pscustomobject]@{
                Title = "Google Play masih memproses transaksi"
                Action = "Periksa status langganan dan riwayat pembayaran sebelum mencoba lagi."
            }
        }
        "subscribe_button_not_found" {
            return [pscustomobject]@{
                Title = "Tombol konfirmasi langganan tidak ditemukan"
                Action = "Periksa layar Google Play, harga, dan status langganan di Android."
            }
        }
        "offer_not_available" {
            return [pscustomobject]@{
                Title = "Penawaran yang dipilih tidak tersedia"
                Action = "Jalankan pemeriksaan Step 1 untuk melihat daftar penawaran yang tersedia."
            }
        }
        { $_ -in @("offer_query_failed", "offers_unavailable") } {
            return [pscustomobject]@{
                Title = "Gagal memuat daftar penawaran Google AI"
                Action = "Buka Google One dan Google Play, cek koneksi ADB, lalu jalankan -Step 1."
            }
        }
        "account_unavailable" {
            return [pscustomobject]@{
                Title = "Akun Google Play tidak dapat diidentifikasi"
                Action = "Buka profil Play Store di Android, lalu coba ulang atau tentukan -Email."
            }
        }
        "account_mismatch" {
            return [pscustomobject]@{
                Title = "Google Play menggunakan akun yang berbeda"
                Action = "Pilih akun yang sesuai di Play Store. Checkout tidak dijalankan."
            }
        }
        "device_missing" {
            return [pscustomobject]@{
                Title = "Perangkat Android / MuMu tidak terhubung"
                Action = "Jalankan MuMuPlayer, aktifkan ADB Debugging, atau klik 'Perbaiki ADB' di dasbor."
            }
        }
        "device_ambiguous" {
            return [pscustomobject]@{
                Title = "Lebih dari satu perangkat Android terhubung"
                Action = "Putuskan perangkat tambahan atau jalankan dengan -Serial sesuai ID dari adb devices."
            }
        }
        "app_missing" {
            return [pscustomobject]@{
                Title = "Google Play atau Google One belum terpasang"
                Action = "Aktifkan aplikasi di pengaturan Android dan pasang Google One dari Play Store."
            }
        }
        "python_missing" {
            return [pscustomobject]@{
                Title = "Python tidak ditemukan"
                Action = "Pasang Python 3.10+, buka ulang PowerShell, lalu coba kembali."
            }
        }
        "adb_missing" {
            return [pscustomobject]@{
                Title = "Android Debug Bridge (ADB) tidak tersedia"
                Action = "Jalankan python setup_env.py atau pasang Android SDK Platform-Tools."
            }
        }
        "runtime_lookup_failed" {
            return [pscustomobject]@{
                Title = "Gagal memeriksa perangkat Android"
                Action = "Restart Google Play/MuMu jika perlu, lalu jalankan -Step 0 -Debug."
            }
        }
        "report_missing" {
            return [pscustomobject]@{
                Title = "Proses tidak menghasilkan laporan"
                Action = "Periksa Log Teknis Realtime dan verifikasi status di Google Play."
            }
        }
        "add_account_failed" {
            return [pscustomobject]@{
                Title = "Gagal menambahkan akun Google"
                Action = "Periksa status login Android dan profil Play Store sebelum melanjutkan."
            }
        }
        "add_account_error" {
            return [pscustomobject]@{
                Title = "Penyiapan akun Google terputus"
                Action = "Periksa prompt login di Android dan verifikasi akun Google Play."
            }
        }
        "payment_method_not_confirmed" {
            return [pscustomobject]@{
                Title = "Metode pembayaran belum terverifikasi"
                Action = "Periksa metode pembayaran Google Play secara manual."
            }
        }
        "play_account_switch_failed" {
            return [pscustomobject]@{
                Title = "Gagal mengganti akun Google Play"
                Action = "Pilih akun yang diinginkan di Play Store lalu jalankan cek penawaran lagi."
            }
        }
        "account_unverified" {
            return [pscustomobject]@{
                Title = "Akun Google Play belum terverifikasi"
                Action = "Buka profil Play Store dan pastikan akun yang benar aktif."
            }
        }
        "wrong_account" {
            return [pscustomobject]@{
                Title = "Google Play memakai akun yang salah"
                Action = "Ganti ke akun target lalu jalankan Step 1 kembali."
            }
        }
        "frida_missing" {
            return [pscustomobject]@{
                Title = "Frida Android belum siap"
                Action = "Siapkan Frida 16.5.9 dan pastikan perangkat Android terhubung."
            }
        }
        "environment_failed" {
            return [pscustomobject]@{
                Title = "Pemeriksaan lingkungan Android belum selesai"
                Action = "Periksa ADB, Google One, dan Frida sebelum mencoba ulang."
            }
        }
        "confirmation_required" {
            return [pscustomobject]@{
                Title = "Diperlukan konfirmasi untuk melanjutkan"
                Action = "Gunakan konfirmasi pada layar untuk melanjutkan langkah yang dipilih."
            }
        }
        "launch_failed" {
            return [pscustomobject]@{
                Title = "Gagal membuka checkout Google Play"
                Action = "Periksa Google One, Google Play, dan riwayat pembayaran sebelum mencoba ulang."
            }
        }
        "billing_flow_error" {
            return [pscustomobject]@{
                Title = "Google Play gagal membuka alur checkout"
                Action = "Periksa layar Android dan riwayat pembayaran sebelum mengulang langkah ini."
            }
        }
        "billing_launch_error" {
            return [pscustomobject]@{
                Title = "Tidak dapat memulai checkout Google Play"
                Action = "Periksa Google One dan log diagnostik Android."
            }
        }
        "activity_lookup_failed" {
            return [pscustomobject]@{
                Title = "Gagal mengakses layar Google One"
                Action = "Tampilkan Google One di layar depan lalu cek ADB/Frida pada Log Teknis."
            }
        }
        "no_activity" {
            return [pscustomobject]@{
                Title = "Google One belum siap"
                Action = "Buka Google One di Android dan ulangi pemeriksaan."
            }
        }
        "app_not_started" {
            return [pscustomobject]@{
                Title = "Google One gagal dibuka"
                Action = "Tutup lalu buka ulang MuMuPlayer, tunggu Android selesai boot, lalu ulangi dari Step 1."
            }
        }
        "checkout_account_mismatch" {
            return [pscustomobject]@{
                Title = "Checkout memakai akun berbeda"
                Action = "Tutup checkout, pilih akun yang tepat di Play Store & Google One, lalu ulangi Step 1."
            }
        }
        "checkout_account_unverified" {
            return [pscustomobject]@{
                Title = "Akun checkout tidak dapat dibaca"
                Action = "Perluas detail akun di layar checkout Google Play dan pastikan email sesuai."
            }
        }
        "play_store_not_started" {
            return [pscustomobject]@{
                Title = "Google Play Store gagal dibuka"
                Action = "Tutup lalu buka ulang MuMuPlayer, tunggu Android selesai boot, lalu ulangi dari Step 1."
            }
        }
        "subscription_update_unavailable" {
            return [pscustomobject]@{
                Title = "Gagal menyiapkan pembaruan langganan"
                Action = "Periksa langganan Google Play yang sedang aktif sebelum mencoba ulang."
            }
        }
        "checkout_not_visible" {
            return [pscustomobject]@{
                Title = "Layar checkout Google Play tidak terlihat"
                Action = "Periksa layar Android dan riwayat pembayaran sebelum mencoba ulang."
            }
        }
        "price_unverified" {
            return [pscustomobject]@{
                Title = "Harga checkout tidak dapat diverifikasi"
                Action = "Periksa nominal tagihan hari ini dan harga perpanjangan di Google Play."
            }
        }
        "checkout_not_confirmed" {
            return [pscustomobject]@{
                Title = "Checkout belum terkonfirmasi"
                Action = "Periksa menu Langganan Google Play sebelum mencoba ulang."
            }
        }
        default {
            return [pscustomobject]@{
                Title = "Langkah ini tidak dapat diselesaikan"
                Action = "Periksa layar Android dan Log Teknis Realtime sebelum mencoba ulang."
            }
        }
    }
}

function Get-FailureCode {
    param([string]$ErrorMessage)
    if ($ErrorMessage -match '(?i)Python not found|Python tidak ditemukan') { return "python_missing" }
    if ($ErrorMessage -match '(?i)adb\.exe was not found|ADB device discovery failed|ADB tidak ditemukan') { return "adb_missing" }
    if ($ErrorMessage -match '(?i)No online ADB devices|selected serial.*not online|Belum ada perangkat ADB') { return "device_missing" }
    if ($ErrorMessage -match '(?i)Cannot select a single Android device|Invalid device number|Lebih dari satu perangkat') { return "device_ambiguous" }
    if ($ErrorMessage -match '(?i)Android package missing|Android package.*unavailable|Paket Android belum') { return "app_missing" }
    if ($ErrorMessage -match '(?i)Play account mismatch|Play Store account changed|Akun Play Store berubah') { return "account_mismatch" }
    if ($ErrorMessage -match '(?i)Cannot identify the active Google Play account|No valid email|Invalid Play Store account|Gagal mengidentifikasi akun') { return "account_unavailable" }
    if ($ErrorMessage -match '(?i)(?:Offer query did not complete|Could not refresh the offer list for Step [2-5]): (app_not_started|play_store_not_started)\s*$') { return $Matches[1].ToLowerInvariant() }
    if ($ErrorMessage -match '(?i)Offer query did not complete|Could not refresh the offer list|Gagal mengambil penawaran') { return "offer_query_failed" }
    if ($ErrorMessage -match '(?i)No report produced|Laporan tidak ditemukan') { return "report_missing" }
    if ($ErrorMessage -match '(?i)Runtime lookup failed|No machine-readable runtime result|Gagal membaca runtime') { return "runtime_lookup_failed" }
    return "unknown"
}

function Show-UserIssue {
    param(
        [string]$Code,
        [string]$Details = "",
        [bool]$DebugMode = $false
    )
    $issue = Get-UserIssue -Code $Code
    if ($env:EPLUS_TUI -eq "1" -and $Code -match '^[a-z_]+$') {
        Write-Host ("EPLUS_ISSUE:{0}" -f $Code)
    }
    Write-Host ""
    Write-Host ("  ! {0}" -f $issue.Title) -ForegroundColor Yellow
    Write-Host ("    Saran: {0}" -f $issue.Action) -ForegroundColor Gray
    if ($DebugMode) {
        Write-Host ("    Kode: {0}" -f $Code) -ForegroundColor DarkGray
        if ($Details) { Write-Host ("    Detail: {0}" -f $Details) -ForegroundColor DarkGray }
    }
}
