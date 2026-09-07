# Sistem Mimarisi — Parçalar Nasıl Birleşiyor?

> Bu dosya "hangi feature neyi besliyor" sorusunun cevabı. Jüri "sistem nasıl çalışıyor" diye sorduğunda anlatılacak hikâye burada.

---

## Nedir?

LunaPath tek bir program değil, **bir veri akışıdır**. Ham NASA arazi verisi bir uçtan girer, "şu yoldan şu saatte git, kararım GO" cevabı diğer uçtan çıkar. Arada yaklaşık 30 modül var ve her biri bir öncekinin çıktısını girdi olarak alır.

---

## Analoji: Restoran mutfağı

Bir restoran düşünün:

- **Depo** = ham veri (NASA'nın yükseklik haritası)
- **Hazırlık bölümü** = veri hattı (eğimi hesapla, gölgeyi hesapla, sıcaklığı hesapla)
- **Şef** = planlayıcı (elindeki malzemelerle en iyi tabağı kurgular)
- **Tarif kitabı** = maliyet motoru (hangi malzemenin ne kadar ağırlığı var)
- **Kalite kontrol** = doğrulama katmanı (tabak müşteriye gitmeden önce denetlenir)
- **Garson** = API + AI asistanı (müşteriye tabağı ve açıklamasını sunar)

Kritik nokta şu: **şef malzemeyi kendisi üretmez.** Planlayıcı eğimi hesaplamaz, gölgeyi hesaplamaz — bunlar hazır gelir. Planlayıcının tek işi elindeki hazır katmanlara bakıp en iyi kombinasyonu seçmektir. Bu ayrım, sistemin test edilebilir olmasının ana sebebi.

---

## Akış: baştan sona

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. VERİ HATTI                                                   │
│                                                                 │
│  NASA LOLA DEM (yükseklik)                                      │
│         │                                                       │
│         ├──► eğim (slope) ────────────────┐                     │
│         ├──► bakı (aspect) ───────────────┤                     │
│         ├──► ufuk haritası (horizon) ─────┤                     │
│         │         │                       │                     │
│         │         ├──► gölge zaman serisi │                     │
│         │         └──► Dünya görünürlüğü  │                     │
│         │                                 │                     │
│  NASA LDRM (pürüzlülük) ──────────────────┤                     │
│  NASA PSR maskesi ────────────────────────┤                     │
│  heat1d (termal model) ───────────────────┤                     │
│  NASA 100 DEM klonu (belirsizlik) ────────┤                     │
└───────────────────────────────────────────┼─────────────────────┘
                                            │
┌───────────────────────────────────────────▼─────────────────────┐
│ 2. MALİYET KATMANI                                              │
│                                                                 │
│  Katmanlı maliyet haritası (costmap):                           │
│    eğim x 0.409  +  enerji x 0.259  +  gölge x 0.142             │
│  + termal x 0.190  +  pürüzlülük x 0.15                         │
│                                                                 │
│  → her hücre için 0-1 arası "buradan geçmek ne kadar kötü" puanı│
│  → geçilemez hücreler = sonsuz maliyet                          │
│                                                                 │
│  (+ risk iştahı verilirse CVaR kuyruk değeri kullanılır)        │
└───────────────────────────────────────────┬─────────────────────┘
                                            │
┌───────────────────────────────────────────▼─────────────────────┐
│ 3. PLANLAYICI                                                   │
│                                                                 │
│  2-D A*      : (satır, sütun)          → hızlı, statik          │
│  4-D A*      : (satır, sütun, zaman)   → BEKLEME kararı verir   │
│                                                                 │
│  Kısıtlar: adım eğimi, yanal eğim, termal zarf, safe haven      │
│            marjı, hayatta kalma olasılığı, aydınlık koridoru    │
└───────────────────────────────────────────┬─────────────────────┘
                                            │
┌───────────────────────────────────────────▼─────────────────────┐
│ 4. DOĞRULAMA                                                    │
│                                                                 │
│  Simülasyon      → adım adım batarya, sıcaklık, zaman           │
│  STL monitörü    → 12 formal gereksinim, marjlı sonuç           │
│  Monte Carlo     → binlerce rastgele senaryo (SHERPA protokolü) │
│  Benchmark       → dış literatür karşılaştırması                │
│                                                                 │
│  → GO / GO-WITH-RISK / NO-GO                                    │
└───────────────────────────────────────────┬─────────────────────┘
                                            │
┌───────────────────────────────────────────▼─────────────────────┐
│ 5. SUNUM                                                        │
│                                                                 │
│  FastAPI (33 uç)  →  React arayüzü + 3-D görüntüleme            │
│  ROS 2 düğümleri  →  gerçek rover yazılım yığınına köprü        │
│  AI asistanı      →  Türkçe açıklama (uydurmaya kapalı)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Üç tasarım kuralı (her modülde geçerli)

### 1. Saf çekirdek, ince kabuk

Hesaplama yapan modüllerin hiçbiri web framework'ü (FastAPI) veya ROS bilmiyor. `cost_engine.py`, `safe_haven.py`, `safety_monitor.py` — hepsi sadece NumPy dizisi alıp NumPy dizisi veren saf Python.

**Neden önemli:** Aynı hesabı hem web API'si hem ROS 2 düğümü çağırıyor. İki ayrı kopya olsaydı zamanla birbirinden ayrışırdı. Bu projede bunun tam olarak yaşandığı bir olay var: rover'a göre grid uyarlaması bir dönem `main.py` içinde olduğu için ROS tarafı hiç uyarlanmış grid görmemiş. `rover_grids.py` bu yüzden ayrı bir modül olarak çıkarıldı.

### 2. Tek doğruluk kaynağı

Aynı formül iki yerde yazılmaz. Örnekler:

- Piksel → metre dönüşümü **sadece** `grid_frame.py` içinde. Bir dönem üç ayrı yerde vardı ve biri ters işaretliydi.
- Kayma (slip) **sadece** `cost_engine.edge_travel_time_s` içinde uygulanıyor. Tek nokta olduğu için simülatör, planlayıcı, koridor bütçesi ve Monte Carlo otomatik olarak tutarlı.
- GO/NO-GO kararı hem backend'de hem frontend'de var, ama bir test ikisini aynı veriyle karşılaştırıp eşit olduklarını doğruluyor.

### 3. Vektörel ikizler kilitli

Bazı hesapların iki hâli var: tek hücre için yazılmış okunabilir "referans" hâli, ve tüm grid için yazılmış hızlı NumPy hâli. Bunlar **testle bit-bit eşitleniyor** (`cost_vec` ile `cost_engine`). Yani birini değiştirip diğerini unutursanız test kırılır.

---

## Feature'lar arası bağımlılık haritası

Hangi feature hangisine muhtaç:

| Feature | Neye dayanıyor |
|---|---|
| Eğim / geçilebilirlik | DEM |
| Ufuk haritası | DEM |
| Aydınlanma | Ufuk + efemeris (Güneş) |
| Dünya görünürlüğü (A4) | Ufuk + efemeris (Dünya) |
| Safe Haven (A1) | Aydınlanma + Dünya görünürlüğü + geçilebilirlik |
| Aydınlık koridoru (A2) | Aydınlanma serisi + geçilebilirlik |
| Termal dwell (C6) | Termal model + aydınlanma serisi |
| Slip modeli (C3) | Eğim + rover katalogu |
| CVaR risk (B2) | Slip sigması (C3) + eğim sigması (B3) |
| Belirsizlik (B3) | NASA'nın 100 DEM klonu |
| Pürüzlülük (C4) | NASA LDRM ürünü |
| Maliyet motoru | Eğim + enerji + gölge + termal + pürüzlülük |
| 2-D A* | Maliyet haritası |
| 4-D A* | Maliyet küpü + safe haven + termal dwell + survival |
| Survival (B1) | Aydınlanma serisi + safe haven + rover enerji modeli |
| Stres testi (B5) | 4-D plan + rover fiziği |
| STL monitörü (D3) | Simülasyon izi veya 4-D plan |
| Misyon raporu | Simülasyon + STL + profil kısıtları |
| AI asistanı | Yukarıdakilerin **hepsinin** çıktısı |

---

## Jüri soruları

**S: "Bu kadar modül nasıl birbirine karışmadan duruyor?"**
Üç kural sayesinde: saf çekirdek (hesaplama modülleri framework bilmez), tek doğruluk kaynağı (formül tek yerde), vektörel ikizlerin testle kilitlenmesi. Bir de her modülün kendi test dosyası var — 100'den fazla test dosyası.

**S: "Bir feature'ı çıkarsanız sistem çöker mi?"**
Hayır, çoğu opsiyonel. Örneğin pürüzlülük katmanı diskte yoksa maliyet motoru dört kriterle çalışır ve bunu metadata'da söyler. NASA klonları yoksa belirsizlik uçları `unavailable` döner. Sistem eksik veriyle çalışmayı reddetmez — eksik olduğunu **söyler**.

**S: "En kritik tek modül hangisi?"**
`cost_engine.py`. Çünkü hem maliyet haritasını hem de `edge_travel_time_s` fonksiyonunu barındırıyor. O fonksiyon her süre ve her enerji hesabının tek çıkış noktası — planlayıcı, simülatör, koridor bütçeleri, safe haven mesafeleri, Monte Carlo hepsi oradan besleniyor.

**S: "ROS 2 gerçekten çalışıyor mu yoksa dekoratif mi?"**
Çalışıyor: dört düğüm var (planlayıcı, grid yayıncısı, poz monitörü, güvenlik monitörü). Kritik nokta şu — bu düğümler backend'in kodunu **çağırıyor**, kopyalamıyor. Planlama matematiği tek yerde.
