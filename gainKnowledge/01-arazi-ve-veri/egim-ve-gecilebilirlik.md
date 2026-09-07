# Eğim ve Geçilebilirlik — "Buradan Geçebilir miyim?"

**Kodda:** `backend/app/traversability.py`
**Kullanan:** maliyet motoru, her iki planlayıcı, safe haven, aydınlık koridoru

---

## Nedir?

Geçilebilirlik (traversability), her ızgara hücresi için tek bir evet/hayır cevabıdır: **bu rover bu hücreye girebilir mi?**

Sonuç bir maske: 250 000 hücrenin her biri ya `True` (geçilebilir) ya `False` (geçilemez). Planlayıcı `False` olan hücreleri hiç düşünmez — onlar duvar gibidir.

---

## Hangi problemi çözüyor?

Planlayıcının arama uzayını daraltır ve **mutlak kırmızı çizgileri** koyar.

Maliyet sistemi "bu hücre kötü ama geçilebilir" der. Geçilebilirlik "bu hücre imkânsız" der. İkisi farklı şeydir ve karıştırılmamalıdır: 24 derecelik bir yamaç pahalıdır ama geçilebilir; 30 derecelik bir yamaç LPR-1 için imkânsızdır, ne kadar acil olursa olsun.

---

## Analoji: Araç yükseklik levhası

Bir köprünün altında "2,5 m" yazan levha vardır. Aracınız 2,6 m ise, ne kadar acele ederseniz edin, ne kadar para verirseniz verin, o köprünün altından geçemezsiniz. Bu bir maliyet değil, bir **kısıttır**.

Geçilebilirlik maskesi Ay yüzeyindeki bütün "2,5 m levhalarının" haritasıdır.

Ve şu detay önemli: **aynı köprü farklı araçlar için farklı levhadır.** LPR-1 25 dereceye kadar tırmanabiliyor, NASA VIPER 20 dereceye kadar. Aynı arazi, iki farklı harita.

---

## Nasıl çalışıyor?

Bir hücre şu **beş** şartın hepsini sağlıyorsa geçilebilir:

```
geçilebilir =  eğim ≤ rover.slope_max_deg
            ∧  soğuk_uç_sıcaklığı ≥ −150 °C
            ∧  eğim NaN değil
            ∧  sıcaklık NaN değil
            ∧  yükseklik NaN değil        (yükseklik verilmişse)
```

### Kural 1: Eğim tavanı

Rover'a göre değişir:

| Rover | Maks. eğim |
|---|---|
| LPR-1 (varsayılan) | 25° |
| NASA VIPER | 20° |
| CNSA Yutu-2 | 20° |
| LUVMI-M | (katalogda) |

### Kural 2: Termal alt sınır (−150 °C)

Hücrenin **en soğuk sürdürülebilir sıcaklığı** −150 °C'nin altındaysa geçilemez.

Buradaki incelik önemli ve bir hata düzeltmesinden geliyor: hangi sıcaklığa bakılmalı?

- **Yıllık tepe sıcaklık** (annual peak) — hücrenin gördüğü en sıcak an
- **Soğuk uç denge sıcaklığı** (cold-end equilibrium) — hücre sürekli gölgede kalırsa ulaşacağı sıcaklık

Hayatta kalma bir **soğuk uç sorusudur**. Bir hücre günde bir saat −50 °C'ye çıksa bile, kalan 23 saat −190 °C ise rover orada donar. O yüzden kapı soğuk uca bakar.

> Bu bir dönem yanlıştı: kod tepe sıcaklığa bakıyordu. "Round 4 review, H-3" olarak düzeltildi. Tepe sıcaklığa bakmak sadece hep aydınlık olan bir hücre için doğru olurdu.

### Kural 3: NaN kontrolü (veri boşluğu)

DEM'de veri olmayan yerler var (uydunun ölçemediği noktalar). Bunlar `NaN` (Not a Number) ile işaretli. NaN'lı bir hücre geçilemez sayılır.

**Neden ayrı kural:** Çünkü `NaN ≤ 25` karşılaştırması Python'da `False` verir — yani NaN eğim zaten kapıyı geçemez. Ama `NaN` yükseklik kimse kontrol etmezse sessizce geçer, sonra planlayıcı orada sonsuz maliyetle karşılaşır. Açık kontrol daha dürüst.

### Tek kural, iki çıktı biçimi

Fonksiyonun iki hâli var — biri `float` maske (1.0 / 0.0), biri `bool` maske. **İkisi de aynı iç fonksiyonu (`_passable`) çağırıyor.**

> Bu da bir hata düzeltmesi: eskiden iki ayrı kopya vardı ve ayrışmışlardı — sadece boolean olan NaN yükseklik kontrolü yapıyordu, ama modülün dokümanı tek kural olduğunu iddia ediyordu. ("Round 4 review, L-8")

---

## Neye göre çalışıyor?

- **Girdi:** eğim haritası, soğuk uç sıcaklık haritası, yükseklik haritası, rover katalog kaydı
- **Sabit:** `THERMAL_MIN_TRAVERSABLE_C = −150.0`
- **Çıktı:** (500, 500) boyutunda maske

Şu anki Site11 grid'inde yaklaşık **60 000 hücre geçilemez** — yani alanın dörtte birine yakını.

---

## İlham kaynağı

Eğim tavanı ve termal alt sınır, gezegen rover'ı mobilite literatürünün standart iki kısıtı. VIPER'ın 20 derece limiti NASA'nın yayınlanmış mobilite tasarım gereksiniminden geliyor. −150 °C eşiği batarya ve elektronik çalışma zarflarından türetilmiş bir mühendislik sınırı.

Özgün olan taraf, bu kuralın **tek bir modülde toplanması** ve hem veri hattının hem API'nin hem ROS düğümlerinin aynı yerden okuması.

---

## Kodda nerede?

```
backend/app/traversability.py
  _passable()                   ← paylaşılan tek kural
  compute_traversability()      ← float maske
  compute_traversability_bool() ← bool maske
  weakest_validity()            ← en zayıf halka etiketi
  THERMAL_MIN_TRAVERSABLE_C     ← −150 °C
```

---

## Jüri soruları

**S: "Neden 25 derece? Bu sayı nereden geliyor?"**
Rover katalogundan; her aracın kendi yayınlanmış mobilite limiti. LPR-1 bizim varsayılan aracımız için 25°, NASA VIPER için 20°. Aynı arazi farklı araç seçilince farklı geçilebilirlik haritası veriyor — bu `rover_grids.py` ile otomatik yeniden hesaplanıyor.

**S: "Eğim tek başına yeterli mi? Kaya, çukur, krater duvarı?"**
Hayır, yeterli değil ve biz de öyle davranmıyoruz. Pürüzlülük ayrı bir kriter olarak maliyete giriyor (NASA'nın ölçülmüş LDRM verisi). Ama pürüzlülük bir **maliyet**, geçilebilirlik değil — çünkü hiçbir rover kataloğunda "şu pürüzlülüğün üstünde geçemem" diye yayınlanmış bir eşik yok, biz de uydurmadık.

**S: "Yanal eğim (cross-slope) neden burada yok?"**
Çünkü yanal eğim hücrenin değil, **hareketin** özelliği. Aynı hücreden yamaca paralel geçerseniz devrilme riski var, dik çıkarsanız yok. O yüzden yanal eğim kontrolü planlayıcının kenar (edge) kontrolünde, `cost_engine.lateral_slope_tan` ile yapılıyor.

**S: "−150 °C'de rover neden ölüyor?"**
Batarya. Lityum bataryalar donduğunda hem kapasite kaybediyor hem de kalıcı hasar görüyor. Katalogda her rover'ın batarya çalışma aralığı var (LPR-1: 0 °C ile +35 °C iç sıcaklık). −150 °C yüzey sıcaklığı, ısıtıcı ve yalıtım hesaba katıldıktan sonra bile iç sıcaklığın kurtarılamayacağı eşik.

**S: "Geçilemez hücre sayısını nereden biliyorsunuz?"**
Grid yüklenirken sayılıyor ve metadata'da raporlanıyor. Şu anki Site11 penceresinde yaklaşık 60 000 hücre (250 000 içinden).
