# Migrasi dari Dify ke Langchain + DeepSeek

## 📋 Overview

Bot Discord (@Kei) telah dimigrasikan dari menggunakan Dify API ke Langchain dengan DeepSeek API. Perubahan ini dilakukan karena Dify sedang mengalami masalah.

## 🚀 Langkah-langkah Migrasi

### 1. Dapatkan API Key DeepSeek
1. Kunjungi https://platform.deepseek.com
2. Buat akun atau login
3. Buka https://platform.deepseek.com/api_keys
4. Buat API key baru
5. Salin API key tersebut

### 2. Update File `.env`
Edit file `.env` dan ganti `your_deepseek_api_key_here` dengan API key DeepSeek Anda:

```bash
# DeepSeek API Configuration (REQUIRED for migration)
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 3. Install Dependencies Baru
Jalankan perintah berikut untuk menginstall dependencies Langchain:

```bash
pip install -r requirements.txt
```

Atau install manual:
```bash
pip install langchain langchain-openai langchain-community
```

### 4. Test Migrasi
Jalankan test script untuk memastikan migrasi berhasil:

```bash
python test_langchain.py
```

### 5. Jalankan Bot
```bash
python bot.py
```

## 🔧 Perubahan Teknis

### File-file yang Diubah:
1. **`langchain_client.py`** - File baru untuk handle Langchain + DeepSeek
2. **`bot.py`** - Mengganti `ask_dify` dengan `ask_langchain`
3. **`requirements.txt`** - Menambahkan dependencies Langchain
4. **`.env`** - Menambahkan konfigurasi DeepSeek
5. **`.env.example`** - Template environment yang diperbarui

### File-file yang Tidak Diubah:
1. **`memory_db.py`** - Sistem memory tetap sama
2. **`dify_client.py`** - Dipertahankan untuk referensi (tidak digunakan)

## 🎯 Fitur yang Tetap Berfungsi

✅ **Semua command Discord**:
- `@Kei` mention untuk chat
- `!kei ask` untuk pertanyaan spesifik
- `!kei reset` untuk reset percakapan
- `!kei purge` untuk hapus semua data channel

✅ **Memory System**:
- Penyimpanan percakapan ke database
- Context dari pesan sebelumnya
- Conversation history

✅ **Semua fitur bot lainnya**

## 🔍 Troubleshooting

### Error: "DEEPSEEK_API_KEY not found"
- Pastikan API key sudah dimasukkan di `.env`
- Format: `DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### Error: ModuleNotFoundError (langchain)
- Install dependencies: `pip install -r requirements.txt`
- Atau install manual: `pip install langchain langchain-openai langchain-community`

### Error: API rate limit
- DeepSeek memiliki rate limit gratis
- Tunggu beberapa saat atau upgrade ke plan berbayar

### Bot tidak merespon
- Cek token Discord masih valid
- Jalankan `python test_langchain.py` untuk test API
- Cek logs untuk error detail

## 📞 Support

Jika mengalami masalah:
1. Cek logs error
2. Jalankan test script
3. Update dependencies
4. Hubungi developer jika masih bermasalah

## 🎉 Migrasi Selesai!

Setelah semua langkah di atas, bot @Kei akan berjalan dengan Langchain + DeepSeek tanpa bergantung pada Dify API lagi.