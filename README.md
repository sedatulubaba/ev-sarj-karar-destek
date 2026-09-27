# Ev Şarj Cihazı Karar Desteği

Python ve Streamlit ile hazırlanan akademik örnek. Ürünler ve fiyatlar **temsili** veridir.

## Çalıştırma

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Linux/macOS'ta Python yolu `.venv/bin/python` olur. [Streamlit Community Cloud](https://share.streamlit.io/) için depo kökündeki `app.py` giriş dosyasıdır.

## Karar akışı

`decision_engine.run_decision` aşağıdaki sırayı uygular:

1. CSV şemasını ve değerlerini doğrular.
2. Bütçe ile evin fazında cihaz desteğini kontrol eder; elenen her cihazın nedenini kaydeder.
3. Her uygun cihaz için fazdaki kullanılabilir gücü alır ve `P_eff = min(P_araç, P_ev, P_istasyon_faz)` hesaplar. `E_gün = günlük_km × tüketim / 100`, `t_gün = E_gün / P_eff` olur. Süre ideal ve teoriktir; kayıplar hesaba katılmaz.
4. Harici AHP karşılaştırma matrisini okur. Karelik, pozitiflik, ana köşegen ve karşılıklılık doğrulanır. Sütun normalizasyonu ve satır ortalaması ağırlıkları üretir. `lambda_max` gerçek en büyük özdeğerden hesaplanır; `CI = (lambda_max − n)/(n − 1)` ve `CR = CI/RI`. `CR >= 0.10` ise karar akışı hata ile durur. Çok küçük negatif CI yalnızca kayan nokta toleransı dahilinde sıfırlanır.
5. TOPSIS nihai sıralamayı verir. Fiyat maliyet, diğer ölçütler faydadır. Vektör normalizasyonu, ağırlıklandırma, idealler, Öklid uzaklıkları ve `C* = S−/(S+ + S−)` hesaplanır. Tek veya özdeş alternatifler 0,5 alır.
6. ELECTRE I üstünlük ilişkilerini ayrıca hesaplar. Varsayılan eşikler, uyum ve uyumsuzluk matrislerinin **köşegen dışı** değerlerinin ortalamasıdır. `config/decision_config.json` üzerinden `"mode": "fixed"`, `"concordance"` ve `"discordance"` ile sabit eşikler de verilebilir. Bu ilişki TOPSIS sıralamasını değiştirmez.
7. Başka bir cihaz, TOPSIS birincisine ELECTRE'de tek yönlü üstünse `method_disagreement = true` döner ve kullanıcıya yöntem farkı söylenir. İlişki yokluğu veya iki yönlü üstünlük anlaşmazlık sayılmaz.

## Veri ve ayarlar

- `data/sarj_istasyonlari.csv`: Faz desteği (`supports_single_phase`, `supports_three_phase` değerleri 0/1) ve faza göre güç (`max_single_phase_kw`, `max_three_phase_kw`) dahil cihaz verileri. Desteklenmeyen fazın gücü 0 olmalıdır. S06 iki fazı da destekleyen örnek cihazdır.
- `config/decision_config.json`: Kriterlerin sırası, `name`, `type` (`benefit`/`cost`), `weight_source` (`ahp`) ve ELECTRE eşik politikası. Şu anda kaynak olarak yalnızca AHP ve cihaz verisindeki altı sayısal kriter desteklenir. Kriter sırası AHP dosyasıyla aynı olmalıdır.
- `data/ahp_ornek_matris.json`: **Yalnızca örnek/test amaçlı tutarlı matris; uzman görüşü değildir.** Üretim veya tez verisi için gerçek uzman karşılaştırmalarıyla değiştirin veya `run_decision(..., matrix_path=...)` kullanın.

Ev fazı bilinmiyorsa nihai teknik uygunluk ve sıralama yapılmaz. Diğer bilinmeyen teknik değerlerde arayüz varsayımları açıklar; sonuç ön değerlendirmedir.

## Denetim sonucu

`run_decision(user_inputs)` tek, JSON'a dönüştürülebilir sözlük döndürür: kullanıcı girdileri ve varsayımlar; uygun ve elenen cihazlar; AHP matrisi, ağırlıklar, `lambda_max`, `CI`, `CR`; TOPSIS'in ham, normalize ve ağırlıklı matrisleri, idealleri, uzaklıkları, skorları ve sırası; ELECTRE'nin kümeleri, matrisleri ve eşikleri; nihai TOPSIS sıralaması, yöntem farkı ve açıklama. Hiç uygun cihaz kalmazsa `status = "no_alternatives"` ve boş sıralama döner. CR tutarsızlığında `InconsistentAHPError` yükselir.

Streamlit ekranında yalnızca karar için gerekli bilgiler gösterilir. **Hesaplama detaylarını göster** bölümünden tam denetim sonucu JSON olarak indirilebilir.

## Testler

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```

`algorithms/` bağımsız matematiksel hesaplar; `utils/` veri ve config doğrulaması; `decision_engine.py` sıralı akış ve denetim çıktısı; `app.py` arayüzdür.
