import pandas as pd
import matplotlib.pyplot as plt # Tetap diimpor karena seaborn mungkin membutuhkannya secara internal
import seaborn as sns # Tetap diimpor karena pandas atau modul lain mungkin menggunakannya
from datetime import datetime
import numpy as np
import time
import threading
import requests
from bs4 import BeautifulSoup
import csv
import os
from concurrent.futures import ThreadPoolExecutor # Digunakan untuk multithreading
import re
from urllib.parse import urljoin, urlparse
import concurrent.futures # Ditambahkan untuk as_completed

class ArticleScrapingResultAnalyzer:
    def __init__(self, csv_file):
        # Membaca CSV dan memastikan kolom 'word_count' dan 'timestamp' ditangani dengan baik
        self.df = pd.read_csv(csv_file)
        if 'word_count' in self.df.columns:
            self.df['word_count'] = pd.to_numeric(self.df['word_count'], errors='coerce').fillna(0)
        if 'timestamp' in self.df.columns:
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'], errors='coerce')
        
    def generate_comprehensive_report(self):
        print("=" * 60)
        print("LAPORAN ANALISIS SCRAPING ARTIKEL KOMPREHENSIF")
        print("=" * 60)
        
        print(f"Total artikel yang berhasil diproses: {len(self.df)}")
        
        if 'word_count' in self.df.columns and self.df['word_count'].sum() > 0:
            print(f"\nAnalisis Konten Artikel:")
            print(f"  Rata-rata jumlah kata: {self.df['word_count'].mean():.2f} kata")
            print(f"  Total kata yang di-scrape: {int(self.df['word_count'].sum()):,} kata")
        else:
            print("\nKolom 'word_count' tidak ditemukan atau tidak ada data kata.")
        
        if 'thread_id' in self.df.columns and not self.df['thread_id'].empty:
            print(f"\nPerforma Thread:")
            thread_summary = self.df.groupby('thread_id').agg(
                count=('url', 'size'),
                avg_words=('word_count', 'mean')
            ).reset_index()
            for index, row in thread_summary.iterrows():
                print(f"  {row['thread_id']}: {row['count']} artikel, rata-rata {row['avg_words']:.0f} kata")
        else:
            print("\nKolom 'thread_id' tidak ditemukan atau tidak ada data thread.")

        if 'timestamp' in self.df.columns and not self.df['timestamp'].empty:
            valid_timestamps_df = self.df.dropna(subset=['timestamp'])
            if not valid_timestamps_df.empty:
                print(f"\nAnalisis Waktu:")
                print(f"  Artikel pertama: {valid_timestamps_df['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Artikel terakhir: {valid_timestamps_df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S')}")
                
                if len(valid_timestamps_df) > 1:
                    total_duration_seconds = (valid_timestamps_df['timestamp'].max() - valid_timestamps_df['timestamp'].min()).total_seconds()
                    if total_duration_seconds > 0:
                        articles_per_second = len(valid_timestamps_df) / total_duration_seconds
                        print(f"  Rata-rata kecepatan scraping: {articles_per_second:.2f} artikel per detik")
                    else:
                        print("  Durasi scraping terlalu singkat untuk menghitung kecepatan per detik.")
                else:
                    print("  Hanya ada satu artikel dengan timestamp valid, tidak bisa menghitung rata-rata waktu per artikel.")
            else:
                print("\nKolom 'timestamp' tidak ditemukan atau tidak ada timestamp yang valid.")
        else:
            print("\nKolom 'timestamp' tidak ditemukan atau tidak ada data timestamp.")

class RealTimeArticleScrapingMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.processed_articles = 0
        self.total_words = 0
        self.lock = threading.Lock()
    
    def update_stats(self, url, word_count, thread_id):
        with self.lock:
            self.processed_articles += 1
            self.total_words += word_count
            elapsed_time = time.time() - self.start_time
            
            print(f"[{elapsed_time:.1f}s] {thread_id}: {url}")
            print(f"  Content: {word_count:,} words")
            print(f"  Progress: {self.processed_articles} articles, {self.total_words:,} words total")
            if elapsed_time > 0:
                print(f"  Rate: {self.processed_articles/elapsed_time:.2f} articles/sec, {self.total_words/elapsed_time:.0f} words/sec")
            print("-" * 80)

def extract_article_content(soup, url):
    """
    Mengekstrak judul, konten utama, jumlah kata, deskripsi meta, penulis, dan tanggal publikasi dari BeautifulSoup object.
    Mencoba beberapa selektor umum untuk menemukan elemen yang relevan.
    """
    title_selectors = ['h1', 'title', '.title', '.headline', '.entry-title']
    title = "No Title"
    for selector in title_selectors:
        title_elem = soup.select_one(selector)
        if title_elem and title_elem.get_text().strip():
            title = title_elem.get_text().strip()
            break
    
    content_selectors = [
        'article', '.article', '.content', '.entry-content', '.post-content',
        '.article-body', '.story-body', '.main-content', 'main', '.post-body'
    ]
    
    article_content = ""
    for selector in content_selectors:
        content_elem = soup.select_one(selector)
        if content_elem:
            # Hapus skrip, gaya, navigasi, header, footer, sidebar, iklan, dan komentar
            for junk_tag in content_elem(["script", "style", "nav", "header", "footer", "aside", "form", ".ads", "#comments"]):
                junk_tag.decompose()
            article_content = content_elem.get_text()
            break
    
    # Fallback: Jika tidak ada konten spesifik artikel yang ditemukan, ambil semua teks dari body
    if not article_content:
        body_elem = soup.find('body')
        if body_elem:
            for junk_tag in body_elem(["script", "style", "nav", "header", "footer", "aside", "form", ".ads", "#comments"]):
                junk_tag.decompose()
            article_content = body_elem.get_text()
        
    article_content = re.sub(r'\s+', ' ', article_content).strip() # Hapus spasi berlebih
    
    words = article_content.split()
    word_count = len(words)
    
    meta_description = ""
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc:
        meta_description = meta_desc.get('content', '')
    
    author = "Unknown"
    author_elem = soup.select_one('.author, .byline, [rel="author"], .post-author, .article-author, .read__info')
    if author_elem:
        author = author_elem.get_text().strip()
    
    publish_date = "Unknown"
    date_elem = soup.select_one('time, .date, .published, .post-date, [datetime], .read__time')
    if date_elem:
        publish_date = date_elem.get('datetime', date_elem.get_text().strip())
    
    return {
        'title': title[:200], # Batasi panjang string untuk CSV
        'word_count': word_count,
        'author': author[:100],
        'publish_date': publish_date[:50],
        'meta_description': meta_description[:200],
        'content_preview': article_content[:500] # Batasi panjang string untuk CSV
    }

def advanced_article_scraping_demo():
    
    article_urls = [
        'https://www.bola.com/tag/timnas-indonesia', # Halaman tag, bukan artikel spesifik (akan gagal di word_count)
        'https://www.halodoc.com/kesehatan/skincare', # Halaman kategori/info (akan gagal di word_count)
        'https://www.orami.co.id/magazine/make-up-natural', # Halaman kategori/info (akan gagal di word_count)
        'https://www.alodokter.com/beragam-manfaat-olahraga', 
        'https://www.mitrakesmas.com/2023/03/pengertian-penyakit-menurut-who-kbbi.html', 
        'https://www.maybelline.co.id/makeup-tips/all-makeup-tips/ini-10-urutan-make-up-yang-benar-dan-simple-untuk-pemula', 
        'https://news.detik.com/berita/d-7953059/pembobol-rekening-incar-pensiunan-asn-dpo-jaringan-pelaku-ada-di-kamboja', 
        'https://news.detik.com/internasional/d-7953999/kecaman-rasis-ke-trump-karena-larang-warga-12-negara-masuk-as', 
        'https://www.detik.com/jateng/berita/d-7952416/detik-detik-kecelakaan-maut-tewaskan-wakil-ketua-dprd-ngawi-di-tol-sragen?mtype=mpc.ctr.B-boxccxmpcxmp-modelB',
        'https://www.hukumonline.com/berita/a/membedah-asas-legalitas-dan-hukum-yang-hidup-di-masyarakat-dalam-kuhp-nasional-lt6841635b4f92e/' 
    ]
    
    monitor = RealTimeArticleScrapingMonitor()
    successful_results = []
    failed_urls_info = [] # Daftar untuk menyimpan URL yang gagal dan alasannya
    
    def enhanced_article_fetch(url):
        thread_name = threading.current_thread().name
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            })
            
            response = session.get(url, timeout=15)
            response.raise_for_status() # Akan memunculkan HTTPError untuk status kode 4xx/5xx
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            article_data = extract_article_content(soup, url)
            
            # Kunci: Menentukan apakah scraping dianggap berhasil berdasarkan jumlah kata
            if article_data['word_count'] < 100: # Jika kurang dari 100 kata, anggap bukan artikel yang valid
                error_msg = f"Konten artikel terlalu pendek ({article_data['word_count']} kata), mungkin bukan artikel utama atau konten valid."
                # Tidak mencetak error di sini, akan dicetak di laporan akhir
                return None, error_msg 
            
            result = {
                'url': url,
                'title': article_data['title'],
                'word_count': article_data['word_count'],
                'author': article_data['author'],
                'publish_date': article_data['publish_date'],
                'meta_description': article_data['meta_description'],
                'content_preview': article_data['content_preview'],
                'thread_id': thread_name,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            monitor.update_stats(url, article_data['word_count'], thread_name)
            
            return result, None # Mengembalikan hasil dan None untuk error (berhasil)
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error: {e.response.status_code} - {e.response.reason}"
            return None, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection Error: {e}"
            return None, error_msg
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout Error: {e}"
            return None, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Requests Error: {e}"
            return None, error_msg
        except Exception as e:
            error_msg = f"Unexpected Error: {e}"
            return None, error_msg
    
    print("Memulai Demo Scraping Artikel Multithreading Lanjutan...")
    print("=" * 80)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Membuat kamus yang memetakan objek Future ke URL aslinya
        futures_map = {executor.submit(enhanced_article_fetch, url): url for url in article_urls}
        
        # Mengumpulkan hasil saat future selesai
        for future in concurrent.futures.as_completed(futures_map):
            original_url = futures_map[future] # Dapatkan URL asli dari future yang selesai
            try:
                # Dapatkan hasil dan pesan error dari fungsi fetch
                result, error_reason = future.result() 
                if result:
                    successful_results.append(result)
                else:
                    # Jika result adalah None, tambahkan ke daftar gagal
                    failed_urls_info.append({'url': original_url, 'reason': error_reason})
            except Exception as e:
                # Tangani pengecualian yang sangat jarang terjadi jika future.result() itu sendiri gagal
                failed_urls_info.append({'url': original_url, 'reason': f"Kesalahan tak terduga saat mendapatkan hasil: {e}"})
            # time.sleep(0.1) # Jeda ini opsional, bisa dihapus jika ingin lebih cepat

    # --- Laporan Akhir (Diperbarui) ---
    if successful_results or failed_urls_info:
        fieldnames = ['url', 'title', 'word_count', 
                      'author', 'publish_date', 'meta_description',
                      'content_preview', 'thread_id', 'timestamp']
        
        output_dir = '.' 
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, 'hasil_scraping.csv')

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in successful_results:
                csv_row = {}
                for field in fieldnames:
                    value = result.get(field, '')
                    if isinstance(value, str):
                        # Bersihkan newline dari string sebelum menulis ke CSV
                        value = value.replace('\n', ' ').replace('\r', ' ')
                    csv_row[field] = value
                writer.writerow(csv_row)
    
    print(f"\nScraping artikel selesai! Hasil berhasil disimpan ke '{csv_path}'")
    
    print("\n" + "=" * 60)
    print("Analisis Artikel Cepat:")
    print("=" * 60)
    print(f"Total URL yang dicoba: {len(article_urls)}")
    print(f"Berhasil di-scrape: {len(successful_results)}")
    print(f"Gagal di-scrape: {len(failed_urls_info)}")
    
    if len(article_urls) > 0:
        success_rate = (len(successful_results) / len(article_urls)) * 100
        print(f"Tingkat keberhasilan: {success_rate:.2f}%")
    
    # Buat kamus untuk pencarian cepat berdasarkan URL
    successful_results_map = {res['url']: res for res in successful_results}
    failed_urls_map = {info['url']: info['reason'] for info in failed_urls_info}

    print("\nRingkasan Hasil per URL Input (Terurut):")
    for i, url in enumerate(article_urls):
        status = "BERHASIL"
        detail = ""
        if url in successful_results_map:
            article_info = successful_results_map[url]
            detail = f"Judul: '{article_info['title']}' ({article_info['word_count']} kata)"
        elif url in failed_urls_map:
            status = "GAGAL"
            detail = f"Alasan: {failed_urls_map[url]}"
        else:
            status = "TIDAK DIKETAHUI" # Seharusnya tidak terjadi jika semua futures diproses

        print(f"  {i+1}. URL: {url}\n     Status: {status}\n     Detail: {detail}")
        print("-" * 30)

    if successful_results:
        total_words = sum(r.get('word_count', 0) for r in successful_results)
        avg_words = total_words / len(successful_results) if successful_results else 0
        
        print(f"\nRata-rata panjang artikel (berhasil): {avg_words:.0f} kata")
        print(f"Total kata yang di-scrape (berhasil): {total_words:,} kata")
        
        # Contoh judul akan tetap 5 pertama dari yang berhasil (tidak harus terurut berdasarkan input URL)
        print(f"\nContoh Judul Artikel (5 pertama yang berhasil):")
        for i, result in enumerate(successful_results[:5]):
            title = result.get('title', 'No Title')[:80]
            word_count = result.get('word_count', 0)
            print(f"  {i+1}. {title}... ({word_count} kata)")
    else:
        print("\nTidak ada artikel yang berhasil di-scrape untuk analisis cepat.")

if __name__ == "__main__":
    advanced_article_scraping_demo()
    
    csv_output_path = os.path.join('.', 'hasil_scraping.csv')

    if os.path.exists(csv_output_path) and os.path.getsize(csv_output_path) > 0:
        print("\n" + "=" * 80)
        print("MENGANALISIS HASIL SCRAPING ARTIKEL (Detail Laporan)...") # Perbarui pesan
        try:
            analyzer = ArticleScrapingResultAnalyzer(csv_output_path)
            analyzer.generate_comprehensive_report()
            print("\nAnalisis selesai! Periksa file CSV untuk hasil detail.")
        except Exception as e:
            print(f"Terjadi kesalahan saat menganalisis hasil scraping: {e}")
            print("Pastikan file 'hasil_scraping.csv' tidak kosong atau rusak.")
    else:
        print("Tidak ditemukan file hasil untuk dianalisis atau file kosong. Pastikan scraping berhasil.")
