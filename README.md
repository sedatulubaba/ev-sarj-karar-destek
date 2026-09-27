# Ev Tipi Şarj İstasyonu Karar Destek Sistemi

Python ve Streamlit ile hazırlanmış sade, modüler akademik proje.

## Kurulum ve çalıştırma

Python 3.10 veya üzeri kullanın. Proje klasöründe:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Tarayıcıda `http://localhost:8501` adresini açın. Linux/macOS'ta Python yolu `.venv/bin/python` olur.

## Streamlit Community Cloud'da yayınlama

1. [Streamlit Community Cloud](https://share.streamlit.io/) üzerinde GitHub hesabınızla giriş yapın.
2. **Create app** ile mevcut GitHub deposundan uygulama oluşturun.
3. Repository: `sedatulubaba/ev-sarj-karar-destek`
4. Branch: `main`
5. Main file path: `app.py`
6. Advanced settings altında Python **3.14** seçin (yerel testlerde kullanılan sürüm).
7. **Deploy** düğmesine basın. Uygulama herhangi bir secret veya API anahtarı gerektirmez.

Bağımlılıklar kökteki `requirements.txt` dosyasından kurulur. Örnek CSV depoya dahildir.
GitHub Pages yerine Streamlit Community Cloud kullanılır; uygulama Python sunucusu gerektirir.

Resmî kılavuz: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## Dosyalar

- `app.py`: Türkçe arayüz ve modüllerin çalışma sırası.
- `algorithms/filter.py`: teknik filtreler, enerji ve süre hesabı.
- `algorithms/ahp.py`: kriter ağırlıkları ve tutarlılık hesabı.
- `algorithms/electre.py`: uyum/uyumsuzluk kümeleri, matrisler ve üstünlük ilişkileri.
- `algorithms/topsis.py`: ideal çözümler, uzaklıklar ve sıralama.
- `utils/helpers.py`: CSV doğrulaması ve ortak normalizasyon.
- `data/sarj_istasyonlari.csv`: 10 temsili istasyon.
- `tests/test_algorithms.py`: bilinen sonuçlar ve sınır durumları.
- `tests/test_app.py`: Streamlit kullanıcı akışları (varsayılan, trifaz, uygun cihaz yok, tutarsız AHP).

## Yöntem ve varsayımlar

1. Bütçeyi aşan veya ev ile aynı fazda olmayan cihazlar elenir. CSV farklı fazda çalışabilme bilgisi içermediğinden aynı faz şartı uygulanır. Gerçekte bazı monofaz cihazlar trifaz tesisata bağlanabilir; bu model bunu değerlendirmez. Ev gücü, diğer tüketimler sonrasında şarja ayrılabilecek güç olarak girilir.
2. Efektif güç `min(araç AC gücü, ev gücü, istasyon gücü)`; günlük enerji `km × tüketim / 100`; süre `enerji / efektif güç` olarak hesaplanır. Batarya kapasitesi ideal tam şarj süresinde ve günlük enerji uyarısında kullanılır; günlük ihtiyacı sınırlandırmaz. Şarj kayıpları, sıcaklık ve güç değişimi süre hesabına dahil değildir.
3. AHP için 6 kriterin 15 ikili karşılaştırması alınır. Köşegen 1, alt üçgen üst üçgenin tersidir. Sütun normalizasyonunun satır ortalamaları ağırlıkları verir. `lambda_max ≈ ortalama((A @ w) / w)`, `CI = (lambda_max − n) / (n − 1)`, `CR = CI / RI`. Altı kriter için Saaty RI değeri 1.24 kullanılır. Bu, satır ortalaması ağırlıklarıyla yaklaşık lambda hesabıdır. Yalnızca `CR < 0.10` olduğunda devam edilir.
4. Karar kriterleri sırasıyla fiyat (maliyet), efektif güç, güvenlik, akıllı özellik, garanti ve verimliliktir (fayda). Günlük şarj süresi güçten türediği için ayrıca kriter yapılmamıştır. Verimlilik 0–1, puanlar 0–10 aralığındadır.
5. ELECTRE I ve TOPSIS sütunlarda Öklid normuyla normalizasyon yapar, ardından AHP ağırlıklarını uygular. ELECTRE uyumu, satır alternatifinin kötü olmadığı kriterlerin ağırlık toplamıdır. Uyumsuzluk, ağırlıklı matriste en büyük aleyhte farkın tüm kriterlerdeki en büyük mutlak farka oranıdır. Fark yoksa 0 alınır. Eşikler kullanıcı tarafından ayarlanır; varsayılanlar 0.65 ve 0.35'tir. Köşegen üstünlük ilişkisi yoktur.
6. ELECTRE ilişkileri açıklayıcı olarak sunulur; ayrıca eleme yapılmaz. TOPSIS bütün teknik olarak uygun alternatifleri sıralar. Böylece ELECTRE döngüleri veya karşılaştırılamayan alternatifler TOPSIS'i engellemez.
7. TOPSIS `C = S− / (S+ + S−)` ile azalan sırada sıralar. Tek alternatif veya tüm alternatifler aynıysa skor 0.5 kabul edilir. Eşitlikte CSV sırası korunur. Bu skor bir olasılık değildir.

CSV ürünleri ve fiyatları tamamen temsili olup gerçek piyasa önerisi değildir. Bütçe cihaz bedelidir; kurulum maliyeti modele dahil değildir.

## Test

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

Örnek: 50 km/gün, 18 kWh/100 km tüketim, 11 kW araç AC gücü, 7.4 kW ev gücü, monofaz ve 19.000 TL bütçede S01, S02 ve S04 kalır. Günlük enerji 9 kWh; S02 için günlük süre yaklaşık 1.22 saattir.
