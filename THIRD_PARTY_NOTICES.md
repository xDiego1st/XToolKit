# Pemberitahuan Pihak Ketiga & Lisensi — XToolKit-Diego

[README Utama](README.md) · [Penafian](DISCLAIMER.md) · [Keamanan](SECURITY.md)

Dokumen ini mencatat komponen pihak ketiga dan pemberitahuan lisensi hulu yang dipertahankan dalam **XToolKit-Diego** demi kepatuhan lisensi perangkat lunak sumber terbuka.

---

## 1. Dependensi & Komponen Utama

| Komponen | Peran dalam XToolKit-Diego | Lisensi Umum |
| --- | --- | --- |
| **Textual / Rich** (`textual`, `rich`) | Kerangka antarmuka terminal interaktif (*TUI*) dan pemformatan konsol berwarna | MIT License |
| **Frida (`16.5.9`)** | Instrumentasi dinamis untuk berkomunikasi dengan proses Android & `BillingClient` | wxWindows Library Licence v3.1 |
| **Android SDK Platform-Tools (`adb`)** | Jembatan komunikasi dan diagnostik perangkat/emulator Android (dipasang terpisah) | Android SDK License (Google) |
| **Komponen Hulu Android/Frida/Billing** | Pendekatan awal integrasi Google One, ADB, Frida, dan Play Billing yang diadaptasi dalam mesin inti | MIT License (lihat salinan di bawah) |

---

## 2. Salinan Pemberitahuan Lisensi MIT Hulu

Sebagian materi fondasi integrasi Android/ADB/Frida/Play Billing yang diadaptasi dalam repositori ini berasal dari karya hulu berlisensi **MIT License**. Sesuai persyaratan lisensi MIT, salinan lengkap pemberitahuan hak cipta dan izin hulu tersebut dipertahankan secara utuh (*verbatim*) di bawah ini.

> **Catatan:** Berkas ini hanya mencatat pemberitahuan lisensi komponen hulu yang wajib disertakan; hal ini **tidak** secara otomatis menetapkan lisensi MIT pada seluruh modifikasi atau kontribusi baru yang tidak terkait dalam **XToolKit-Diego**.

```text
MIT License

Copyright (c) 2026 gylive

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
