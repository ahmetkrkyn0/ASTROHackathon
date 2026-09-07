# CVaR Risk İştahı (B2) — "Ortalamaya mı, En Kötü Senaryoya mı Göre Planla?"

**Kodda:** `backend/app/risk.py`
**API:** `risk_alpha` parametresi (`/api/plan`, `/api/plan-4d`), `POST /api/risk-sweep`
**Özellik kodu:** B2

---

## Nedir?

Operatörün, rotayı **ortalama beklentiye** göre değil, **en kötü senaryolara** göre sıralamasını sağlayan bir ayar.

Teknik adı: **CVaR** — Conditional Value at Risk (Koşullu Riske Maruz Değer). Dağılımın en kötü `(1 − α)` kuyruğunun ortalaması.

Parametre: `risk_alpha ∈ [0,5 – 0,999]`. Yüksek α = daha temkinli.

---

## Hangi problemi çözüyor?

B2'den önce bir hücrenin maliyeti **tek bir sayıydı**: DEM'in en iyi tahmin eğiminde, slip eğrisinin ortalaması.

Ama artık iki girdinin de **yayılımı** var:

| Girdi | Yayılım kaynağı |
|---|---|
| Slip | [C3](slip-modeli.md) her çapaya bir σ koydu |
| Eğim | [B3](../01-arazi-ve-veri/dem-belirsizligi-100-klon.md) NASA'nın 100 klonundan hücre başına σ verdi |

Yayılım varken ortalamayı kullanmak bir **seçim**. Ve bazı misyonlarda yanlış seçim: bir bilim aracı için ortalama iyidir, kritik bir kurtarma görevi için "en kötü %1'de ne olur" daha önemlidir.

---

## Analoji: Trafikte yola çıkış saati

İşe gitmeniz 30 dakika sürüyor — **ortalama olarak.** Ama bazen 25, bazen 55 dakika.

Şimdi iki farklı durum:

**Durum A — sıradan bir iş günü.** Ortalamaya göre planlarsınız: 30 dakika önce çıkarsınız. Bazen geç kalırsınız, önemli değil.

**Durum B — uçak yakalayacaksınız.** Ortalamaya göre planlamazsınız. **"En kötü %5'te ne olur?"** diye sorarsınız: 55 dakika. Ve ona göre çıkarsınız.

CVaR'ın yaptığı tam olarak bu. `α = 0,95` demek: *"En kötü %5'lik dilimin ortalamasına göre planla."*

Ve kritik nüans: CVaR, **en kötü tek senaryoya** göre değil, **en kötü dilimin ortalamasına** göre planlıyor. Yani felaket senaryosuna takılıp kalmıyor, ama kuyruğu ciddiye alıyor.

---

## Nasıl çalışıyor?

### Formül

Normal dağılım için kapalı formda:

```
CVaR_α(N(μ, σ²)) = μ + σ · φ(z_α) / (1 − α)

z_α = Φ⁻¹(α)          (normal dağılımın ters kümülatifi)
φ   = normal yoğunluk
```

Rockafellar & Uryasev (2000)'in kapalı formu.

**Önemli nokta:** `α = 0,5` **ortalama değildir.** `μ + 0,798σ` demektir. Ve bunu her API cevabı açıkça söylüyor — çünkü "0,5 = ortalama" sezgisi yanlış ve tehlikeli.

### α nereye giriyor?

Sadece **sıralama maliyetine**:

| Kriter | α ile ne oluyor |
|---|---|
| **Enerji kriteri** | Hücre `min(0,9, CVaR_α(slip))` ile fiyatlanıyor (ortalama slip yerine) |
| **Eğim kriteri** | Sigmoid `min(slope_max, slope + σ_slope · m_α)` okuyor |

Slip'in σ'sı, eğim σ'sını **delta yöntemiyle** içine alıyor:

```
σ_total² = σ_slip² + (k · s · σ_slope)²
```

(Log-lineer bir segmentte `ds/dslope = k·s` olduğu için.)

### α nereye GİRMİYOR? — kritik tasarım kararı

| Yer | Neden ortalamayı kullanmaya devam ediyor |
|---|---|
| **Geçilemezlik kapısı** | Nominal eğimde kalıyor → **geçilebilirlik asla α'ya bağlı değil** |
| Sürüş süresi | α'yı fiziğe koymak, nominal saati bir tercihe bağlar |
| Batarya | Aynı gerekçe |
| Formal marjlar | Aynı gerekçe |
| Koridor bütçeleri | Aynı gerekçe |
| Monte Carlo | B5'in kendi hız/güç dağılımlarını **iki kez sayardı** |

**Bu ayrım çok önemli:** Risk iştahı, geçilebilir hücreleri **yeniden sıralıyor** — hangi hücrelerin geçilebilir olduğunu asla değiştirmiyor.

Tasarım alternatifi (α'yı fiziğe koymak) değerlendirildi ve **reddedildi**.

### Geriye dönük uyumluluk

`risk_alpha` verilmezse grid **bit-eşit**: `COST_MODEL_ID` v4'te kalıyor ve Site11 grid'leri B2 öncesi SHA-256 değerlerine kilitli.

---

## Termal kuyruk kancası — çalışmayan ve neden

`risk.thermal_cvar_cold_c` diye bir kanca var ve **çalışmıyor**. İki sebep:

1. **Termal alanın yayınlanmış bir σ'sı yok.** Uydurmadık.
2. **Ölçüldü ve zaten faydasız:** `f_thermal`, LPR-1'in geçilebilir hücrelerinin **%72,7'sinde**, VIPER'ınkilerin **%54,2'sinde** zaten doyuyor (1,0'a çarpıyor).

α = 0,9'da soğuk kuyruk bunu %94,0 / %81,2'ye çıkarıyor → **daha çok doyma, daha iyi sıralama değil.**

Doymuş bir kriter hiçbir şey ayırt etmiyor. Bu, bir özelliği eklemeyip **neden eklenmediğini ölçmenin** iyi bir örneği.

---

## Site11'de ölçülen gerçek sayılar

### Eğim ve slip yayılımları

| Ölçüm | Değer |
|---|---|
| Eğim σ medyanı (100 klon) | 1,54° (p95: 1,99) |
| CVaR slip medyanı, α = 0,99 | 0,199 → **0,497** |
| 0,9 tavanında doyan geçilebilir hücre | %26,6 |
| α-sıralı maliyet ↔ nominal, Spearman | **0,985** (LPR-1) / 0,970 (VIPER) |

Spearman 0,985: risk iştahı sıralamayı **değiştiriyor ama alt üst etmiyor.**

### 2-B süpürme sonuçları

α = 0,99 rotası, nominal rotayla **%49–52 hücre örtüşüyor** — yani yarısı farklı.

Ama nominal fizikteki kazanç küçük:

| Rota | Nominal | α = 0,99 |
|---|---|---|
| LPR-1 gündüz | 597,2 Wh | 592,7 Wh |
| LPR-1 ay gecesi | 1 465,7 Wh | **1 439,5 Wh** (−%1,8), min SOC +0,39 puan |
| VIPER standart | 2 741,8 Wh | 2 713,0 Wh |

### Dürüst ve rahatsız edici bulgu

**Risk matrisi dört çiftin ikisinde NOMİNAL rotayı kuyrukta daha ucuz buluyor.**

Örnek: LPR-1 gündüz, α = 0,99 değerlendirmesinde nominal rota **3,375 saat**, α-planlı rota **3,696 saat**.

**Yani riski hesaba katarak planlanan rota, riskli senaryoda nominal rotadan daha kötü performans gösteriyor.**

**Sebebi:** Ağırlıklı kriterler **kuyruk süresini minimize etmiyor.** Maliyet fonksiyonu beş kriterin ağırlıklı toplamı; CVaR bunlardan ikisinin girdisini değiştiriyor. Ama optimize edilen şey hâlâ ağırlıklı toplam, doğrudan kuyruk süresi değil.

**Ve bu raporlanıyor.** Sonucu güzelleştirmek yerine "dürüst bir sonuç ve öyle raporlandı" deniyor.

### 4-B'de

LPR-1 **her α'da aynı 42 hamleli rotayı** seçiyor, varış 2,979 saat değişmiyor, ortalama slip 0,326 → 0,313.

---

## `POST /api/risk-sweep`

Aynı başlangıç/hedef çiftini nominal ve birkaç α'da yan yana planlıyor:

- Her rotayı **nominal fizikle** özetliyor (adil karşılaştırma için)
- Nominal rotayla hücre örtüşmesini veriyor
- Bir **risk matrisi** üretiyor: her rota, her α'da yeniden fiyatlanmış

Bu matris, yukarıdaki rahatsız edici bulguyu görünür kılan şey.

---

## İlham kaynağı

- **Rockafellar & Uryasev (2000)** — CVaR'ın kapalı formu ve optimizasyon teorisi
- **STEP** (Fan, Otsu, Kitahara, Zhang, Agha-mohammadi; RSS 2021) — JPL'in yaklaşımı: risk terimleri, planlayıcının maliyeti içinde bir geçilebilirlik dağılımının CVaR'ı olarak. DARPA SubT yarışmasında sahada kullanıldı.
- **Endo, Taniai, Ishigami (ICRA 2023)** — Keio Üniversitesi: `slip ~ p(slip | eğim, zemin)`, slip'in CVaR'ı süre ve enerji maliyetine, arama değişmeden.

---

## İddia sınırı

- ⚠️ `MODEL` etiketli dağılımların CVaR'ı, **ölçülmüş bir risk değil.**
  - Slip σ'sı: Yutu-2'nin aralığının ±2σ okunması + 0,5'lik aktarılmış göreli yayılım (varsayımlar, her çapanın kaynağında yazılı)
  - Eğim σ'sı: NASA klonlarından `DERIVED`
  - Termal σ: **yok**
- 📎 Endo vd.'nin *"%11 → %95 başarı"* sonucu **onların sentetik sonucu** — alıntılanıyor, tekrarlanmıyor.

---

## Kodda nerede?

```
backend/app/risk.py
  slip_cvar() / slip_cvar_array()
  slope_cvar() / slope_cvar_array()
  thermal_cvar_cold_c()      ← kanca, çalışmıyor (gerekçesiyle)
  RISK_MEASURE_ID

scripts/risk_sweep_report.py
docs/research/risk_sweep_report.md
```
74 yeni test.

---

## Jüri soruları

**S: "CVaR nedir, basitçe?"**
"En kötü senaryoların ortalaması." α = 0,95 dersek, dağılımın en kötü %5'ini alıp onun ortalamasını kullanıyoruz. Uçak yakalayacaksanız trafikte ortalamaya göre değil, kötü günlere göre çıkarsınız — aynı fikir.

**S: "Risk iştahı geçilebilirliği değiştiriyor mu?"**
Hayır, kesinlikle hayır. Geçilemezlik kapısı **nominal eğimde** kalıyor. Risk iştahı sadece geçilebilir hücreleri yeniden sıralıyor. Bunun sebebi: bir hücrenin fiziksel olarak geçilebilir olup olmaması, operatörün tercihine bağlı olamaz.

**S: "α = 0,5 ortalama demek değil mi?"**
Hayır ve bu yaygın bir yanılgı. α = 0,5, `μ + 0,798σ` demek — yani zaten ortalamanın üstünde. Her API cevabı bunu açıkça söylüyor, çünkü sezgi yanlış yönde çekiyor.

**S: "Sonuçlar iyi mi?"**
Karışık ve dürüstçe raporluyoruz. Ay gecesi rotasında %1,8 enerji kazancı ve batarya marjında iyileşme var. Ama risk matrisi dört çiftin ikisinde nominal rotayı kuyrukta **daha ucuz** buluyor. Sebebini de biliyoruz: ağırlıklı kriter toplamı kuyruk süresini doğrudan minimize etmiyor. Bunu güzelleştirmek yerine raporladık.

**S: "O zaman bu özellik işe yaramıyor mu?"**
İşe yarayan kısmı şu: operatöre bir seçenek ve bir görünürlük veriyor. `risk-sweep` ucu, aynı çifti farklı risk seviyelerinde planlayıp yan yana koyuyor ve her rotayı her α'da yeniden fiyatlıyor. Operatör böylece "risk almanın bana ne kazandırdığını/kaybettirdiğini" görebiliyor — bazen cevap "hiçbir şey" oluyor ve bunu görmek de değerli.

**S: "Termal riski neden eklemediniz?"**
Ölçtük ve faydasız olduğunu gördük. Termal kriter zaten LPR-1'in geçilebilir hücrelerinin %72,7'sinde doyuyor; kuyruk eklemek bunu %94'e çıkarıyor — daha çok doyma, daha iyi sıralama değil. Ayrıca termal alanın yayınlanmış bir standart sapması yok, uydurmadık.
