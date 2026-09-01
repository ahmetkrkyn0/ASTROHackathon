# nac-site11-2048.jpg — kaynak ve kapsam

**Ne:** LROC NAC Güney Kutup Mozaiği'nden, projenin şu anki grid penceresine
birebir denk gelen 2.5 × 2.5 km'lik kırpım. 2048×2048'e indirilmiş
(kaynak 2500×2500 @ 1 m/px).

**Kaynak karo:** `NAC_POLE_P892S3150.TIF` (2.07 GB, 45488×45489 @ 1 m/px)
https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/EXTRAS/BROWSE/NAC_POLE/NAC_POLE_SOUTH/

**Kırpım penceresi:** ham karo içinde row=34488, col=12988, 2500×2500 —
`lunapath/data/processed/metadata.json`'daki origin (−32500, 11000),
5 m/px, 500×500 penceresiyle aynı zemin. Aynı projeksiyon (Ay güney kutup
stereografik, MOON_ME), yeniden projeksiyon yapılmadı; grid'e piksel piksel
hizalı, o yüzden `PlaneGeometry`'nin varsayılan UV'leri doğrudan çalışır.

**Atıf:** Wagner, R. V., Speyerer, E. J., Robinson, M. S., & LROC Team (2015).
*New Mosaicked Data Products from the LROC Team.* LPSC 46, abstract #1473.

## Bilinmesi gereken sınır

Mozaik 2010 güney gündönümünde (2010-07-23 – 2010-12-11), kutbun **en iyi
aydınlandığı** dönemde çekilmiş görüntülerden oluşuyor. Buna rağmen 88.9°S'de
Güneş en fazla ~1.5° yükseldiği için **bu kırpımın %52'si derin gölgede**
(DN < 20) ve yalnızca %44'ünde kullanılabilir sinyal var.

Daha önemlisi: görüntünün gölgeleri **2010'daki çekim geometrisine** ait,
uygulamanın simüle ettiği epoğa değil. İkisi ölçüldü ve uyuşmuyor
(IoU ≈ %51). Bu yüzden bu doku, zaman-değişimli gölge maskesiyle
**çarpılmaz** — çarpılırsa gölgeler iki kez sayılır ve hiçbiri doğru olmaz.

Uygulamadaki karşılığı: "Foto" modu bu dokuyu albedo olarak giydirir ve
gölge maskesini devre dışı bırakır (görüntü kendi gölgesini zaten taşır);
diğer modlar düz regolit albedosu + gerçek zaman-değişimli gölge kullanır.
İkisi ayrı iddialar, karıştırılmıyor.

---

# nac-site11-detail-2048.jpg — zamansız detay dokusu

**Neden var:** `nac-site11-2048.jpg` tek bir andır; gün ekseniyle değişmez.
"1. gün ile 5. günün gerçek görüntüsü aynıysa ne işe yarar" sorusunun cevabı
bu dosya: aynı NAC karesinden, **çekim zamanına bağlı olmayan** kısım
ayrıştırıldı, böylece `surface` görünümü hem gerçek krater dokusunu taşıyor
hem de simüle edilen Güneş'e cevap vermeye devam ediyor.

**Nasıl üretildi:** NAC karesi kendi 125 m'lik lokal ortalamasına bölündü.
Bölme, fotoğrafı oluşturan büyük ölçekli aydınlanma gradyanını kaldırıp
küçük ölçekli varyasyonu bırakıyor; kalan oran (0.45–1.55'e kırpıldı) düz
regolit albedosunu modüle ediyor. Sonuç dokunun kanal ortalamaları
(120, 114, 106), düz tondan (122, 116, 108) iki birim uzakta — yani zemin
tonunu kaydırmadan doku ekliyor.

**Kapsam:** kaynağın bölünemeyecek kadar karanlık olduğu yerde (DN ≤ 25, bu
enlemde karenin ~%47'si) oran 1'e sabitlendi ve yüzey düz albedoya düşüyor.
Fotoğrafın sinyal taşımadığı yerde detay uydurulmuyor.

**Dürüst sınır:** bölmeden geriye kalan şey, saf albedo varyasyonu **değil** —
gerçek albedo ile, LOLA DEM'in tutamayacağı kadar küçük yapıların 2010'daki
gölgelendirmesinin karışımı. Bu yüzden küçük bir kraterin kendi aydınlık-karanlık
çifti dokuya pişmiş durumda ve simüle edilen Güneş döndüğünde onunla birlikte
dönmüyor. Bu bir **detay dokusudur, geri kazanılmış albedo değildir.**

Yalnızca `surface` görünümüne uygulanıyor; eğim/maliyet/termal gibi veri
görünümleri modülasyonsuz kalıyor, çünkü bir veri rampasının fotoğrafla
dokulandırılması onu okunamaz hale getirir.
