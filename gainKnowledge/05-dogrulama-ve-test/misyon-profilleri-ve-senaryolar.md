# Misyon Profilleri ve Senaryolar — "Bu Görevde Neye Öncelik Veriyoruz?"

**Kodda:** `backend/app/scenarios.py`, `backend/app/profile_comparison.py`
**API:** `GET /api/profiles`, `GET /api/scenarios`, `POST /api/scenarios/{id}/load`, `POST /api/compare`, `POST /api/plan-multi`

---

## Nedir?

**Misyon profili**, aynı araziyi farklı önceliklerle okuyan bir ayar paketi. Dört tane var, her biri iki şey taşıyor:

1. **Ağırlıklar** — maliyet kriterlerinin göreli önemi
2. **Kısıtlar** — o profilin kabul ettiği sınırlar

---

## Hangi problemi çözüyor?

"En iyi rota" görevin amacına bağlı:

- **Bilim keşfi** → yavaş ama güvenli git
- **Acil ulaşım** → hızlı git, risk al
- **Enerji kritik dönem** → bataryayı koru, uzun yolu kabul et
- **Gölge geçişi zorunlu** → termal güvenlik her şeyin üstünde

Profil sistemi bu ödünleşimi **açık ve karşılaştırılabilir** hâle getiriyor.

---

## Analoji: Navigasyon uygulamasındaki rota seçenekleri

Google Maps size üç seçenek sunar: "en hızlı", "en kısa", "otoyolsuz". Aynı başlangıç, aynı hedef, **üç farklı rota**.

Uygulama sizin adınıza karar vermiyor — **seçenekleri gösteriyor** ve farklarını sayısallaştırıyor: "bu 5 dakika daha uzun ama 12 km daha kısa."

LunaPath'in profil karşılaştırması da bu. Ama Ay için ödünleşimler daha ciddi: "bu rota 40 dakika daha uzun ama bataryayı %15 daha yüksek bırakıyor" — ve %15 batarya, iki hafta iletişimsiz kalmakla ölmek arasındaki fark olabilir.

---

## Dört profil

| Profil | Açıklama | Ağırlıklar (eğim/enerji/gölge/termal) | Kısıtlar |
|---|---|---|---|
| **Balanced Recon** | Standart mod; her riski eşit tartar | 0,409 / 0,259 / 0,142 / 0,190 | gölge ≤ 40 sa · eğim ≤ 25° · enerji ≤ 4000 Wh · SOC ≥ %20 |
| **Energy Saver** | Bataryayı korumak için daha uzun rotayı kabul eder | 0,250 / **0,450** / 0,150 / 0,150 | gölge ≤ 30 sa · eğim ≤ 20° · enerji ≤ **2500 Wh** · SOC ≥ **%35** |
| **Fast Recon** | Daha agresif; kısa rotayı tercih eder | **0,500** / 0,150 / 0,100 / 0,250 | gölge ≤ 50 sa · eğim ≤ 25° · enerji ≤ 5000 Wh · SOC ≥ **%10** |
| **Shadow Traverse** | Gölge geçişi kaçınılmaz; termal güvenlik kritik | 0,200 / 0,150 / **0,300** / **0,350** | gölge ≤ 45 sa · eğim ≤ 25° · enerji ≤ 4000 Wh · SOC ≥ %25 |

Ağırlıklar v3.2 spesifikasyonunda dondurulmuş.

**C4 notu:** Beşinci ağırlık (`w_roughness`) her profile katalog varsayılanında eklendi. Hiçbir profilin yayınlanmış bir pürüzlülük ağırlığı olmadığı için profil başına bir değer uydurulmadı. Ve dört donmuş ağırlık **yeniden ölçeklenmedi** — toplamlarının 1 olması bir konvansiyondu, planlayıcının okuduğu bir kısıt değil.

---

## Kısıtların ayrımı: aranabilir vs. sonradan kontrol edilebilir

Bu, kavramsal olarak en önemli kısım.

| Kısıt | Aramada uygulanabilir mi? | Neden |
|---|---|---|
| `max_slope_deg` | ✅ **Evet** | Hücrenin kendi özelliği — arama sırasında bilinir |
| `max_shadow_h` | ❌ Hayır | **Yol bağımlı** — toplam gölge, hangi yoldan gidildiğine bağlı |
| `max_energy_wh` | ❌ Hayır | Yol bağımlı |
| `min_soc` | ❌ Hayır | Yol bağımlı |

**Yol bağımlı** demek: değer, o ana kadarki bütün yolun fonksiyonu. A* hücre başına karar verirken bunu bilemez — çünkü aynı hücreye farklı yollardan farklı birikimlerle gelinebilir.

### Round 4'te düzelen eksiklik

Bu üç kısıt aramada uygulanamıyor **ama çıkan rotaya karşı KONTROL EDİLEBİLİR** — ve round 4'e kadar hiçbir şey bunu yapmıyordu.

Yani her misyon profilinin yayınladığı dört kısıttan **üçü kodun hiçbir yerinde görünmüyordu.**

`attach_constraint_check()` bunu düzeltti: profilin rotası simüle ediliyor ve hangi limitlerin karşılandığı kaydediliyor.

---

## `profile_comparison.py` — neden ayrı bir modül?

Bu modül, `/api/compare` ve `/api/plan-multi` rota gövdelerinden **çıkarıldı**.

**Sebebi:** AI araç katmanının **aynı aritmetiği** çalıştırması gerekiyor, ikinci bir uygulamasını değil.

> İki profil karşılaştırma uygulaması zamanla ayrışır ve asistanın alıntıladığı sayı, haritanın çizdiği rotayla eşleşmeyi bırakır.

### Yan etkisizlik — AI için kritik

Modülde hiçbir şey uygulama durumu yazmıyor. Her profil kendi uyarlanmış grid'lerini `grids_for_rover` üzerinden alıyor; o fonksiyon **yeni bir sözlük ve kopyalanmış metadata** döndürüyor.

**Sonucu:** Çağıranın grid'leri **dokunulmamış** geri geliyor.

**Ve bu yüzden:** AI asistanının bu fonksiyonu çalıştırmasına **izin var**, ama `/api/plan` çağırmasına **yok** — çünkü ikincisi kullanıcının ekranındaki rotayı değiştirir.

---

## Senaryolar

`scenarios.py` ayrıca kayıtlı senaryoları yönetiyor: önceden tanımlanmış başlangıç/hedef/epoch/rover kombinasyonları.

`POST /api/scenarios/{id}/load` ile bir senaryo yükleniyor — demo ve tekrarlanabilir test için.

---

## Kodda nerede?

```
backend/app/scenarios.py
  MISSION_PROFILES              ← dört profil, v3.2'de donmuş
  check_profile_constraints()
  get_profile()
  SEARCHABLE / POST_HOC kısıt ayrımı

backend/app/profile_comparison.py
  compare_all_profiles()        ← tek aritmetik, iki tüketici
  attach_constraint_check()     ← round 4'te eklendi
```

---

## Jüri soruları

**S: "Neden dört profil?"**
Çünkü "en iyi rota" görevin amacına bağlı. Bilim keşfi yavaş ve güvenli gitmek ister, acil ulaşım risk almayı göze alır, enerji kritik dönemde bataryayı korumak öncelikli olur. Profiller bu ödünleşimi açık hâle getiriyor: aynı başlangıç ve hedef için dört farklı rota ve dört farklı sonuç.

**S: "Ağırlıkları kullanıcı değiştirebiliyor mu?"**
Evet, istek üzerinden. `resolve_weights` rover'ın kendi varsayılanlarının üstüne istek ağırlıklarını yazıyor. Normalizasyon veya toplam kontrolü yok — toplamın 1 olması bir konvansiyondu, kısıt değil.

**S: "Kısıtlar gerçekten uygulanıyor mu?"**
Kısmen ve bu ayrımı yapıyoruz. Eğim kısıtı aramada uygulanabiliyor çünkü hücrenin kendi özelliği. Gölge, enerji ve SOC kısıtları **yol bağımlı** — aynı hücreye farklı yollardan farklı birikimlerle gelinebilir, o yüzden A* onları aramada bilemez. Ama çıkan rotaya karşı kontrol edilebilirler ve round 4'te bu eklendi. Öncesinde dört kısıttan üçü kodun hiçbir yerinde görünmüyordu.

**S: "Karşılaştırma neden ayrı bir modülde?"**
Çünkü AI asistanının aynı aritmetiği çalıştırması gerekiyor. İki ayrı uygulama zamanla ayrışır ve asistanın söylediği sayı ile haritadaki rota tutmaz. Ayrıca modül yan etkisiz — bu yüzden AI'ın onu çalıştırmasına izin var ama `/api/plan` çağırmasına yok.

**S: "Pürüzlülük ağırlığı profillere nasıl eklendi?"**
Katalog varsayılanıyla (0,15), profil başına uydurulmadan. Hiçbir profilin yayınlanmış bir pürüzlülük ağırlığı yok. Ve dört mevcut ağırlık yeniden ölçeklenmedi — toplamlarının 1 olması bir konvansiyondu, planlayıcı onu okumuyor.
