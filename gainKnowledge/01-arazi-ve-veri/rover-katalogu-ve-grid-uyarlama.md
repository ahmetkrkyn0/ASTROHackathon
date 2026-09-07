# Rover Katalogu ve Grid Uyarlama — "Aynı Arazi, Farklı Araç"

**Kodda:** `backend/app/constants.py` (katalog), `backend/app/rover_grids.py` (uyarlama)
**API:** `GET /api/rovers`

---

## Nedir?

**Rover katalogu**, sistemin planlayabildiği dört aracın teknik künyesi: kütle, hız, güç tüketimi, batarya kapasitesi, tırmanabildiği eğim, dayanabildiği gölge süresi, batarya sıcaklık aralığı.

**Grid uyarlama**, seçilen araca göre geçilebilirlik maskesini ve maliyet haritasını **yeniden hesaplayan** katman.

---

## Hangi problemi çözüyor?

Ay arazisi herkes için aynı. Ama "geçilebilir" herkes için aynı değil.

- VIPER 20 dereceye tırmanır, LPR-1 25 dereceye → aynı yamaç biri için duvar, öbürü için yol
- Yutu-2 sadece 2 saat gölgede kalabilir, VIPER 96 saat → aynı gölgeli vadi biri için ölüm, öbürü için sorun değil
- LUVMI-M 40 kg, VIPER 450 kg → aynı eğimde harcadıkları enerji çok farklı

Yani **grid'in kendisi rover'a bağımlı.** Yükleme anında hesaplanan maske sadece varsayılan rover için doğru.

---

## Analoji: Aynı dağ, farklı yürüyüşçüler

Bir dağ patikası düşünün. Aynı patika:

- Profesyonel tırmanıcı için: kolay bir gün yürüyüşü
- Ortalama biri için: zorlu ama yapılabilir
- Dizinde sorunu olan biri için: geçilemez

Patika değişmedi. **Değişen, patikayı okuyan kişi.**

Ve şu detay kritik: eğer bir rehber "bu patika geçilebilir" haritasını sadece profesyonel için hazırlayıp herkese aynı haritayı verirse, birileri ölür.

Grid uyarlama bu hatayı önler: her araç için harita yeniden çizilir.

---

## Katalog — dört araç

| | **LPR-1** (varsayılan) | **NASA VIPER** | **CNSA Yutu-2** | **LUVMI-M** |
|---|---|---|---|---|
| Kütle | 450 kg | 450 kg | 140 kg | 40 kg |
| Maks. hız | 0,20 m/s | 0,06 m/s | 0,05 m/s | 0,05 m/s |
| Sürüş gücü | 200 W | 250 W | 100 W | 80 W |
| Batarya | 5 420 Wh | 4 000 Wh | 1 500 Wh | 1 400 Wh |
| Güneş paneli | 410 W | 450 W | 300 W | 140 W |
| **Maks. eğim** | **25°** | **20°** | **20°** | **25°** |
| Maks. yanal eğim | 18° | 15° | 15° | 15° |
| **Maks. gölge dayanımı** | **50 sa** | **96 sa** | **2 sa** | **4 sa** |
| Min. batarya (SOC) | %20 | %20 | %30 | %20 |
| Batarya sıcaklık aralığı | 0 … +35 °C | 0 … +35 °C | −10 … +30 °C | −100 … 0 °C |

> **LPR-1** = "Lunar Path Rover 1", projenin kendi referans aracı. Diğer üçü gerçek misyonlardan.

### Katalogda hangi alan gerçekten kullanılıyor?

Bu, dürüstlük tasarımının bir başka örneği. Katalogda birçok alan var ama **hepsi modele girmiyor**. Kodda `MODELLED_FIELDS` diye bir küme var: bu kümedeki alanlar gerçekten hesaba giriyor, kümedekiler dışındakiler "referans için yayınlanmış" olarak etiketleniyor.

`GET /api/rovers` bunu açıkça söylüyor — böylece bir frontend "listelenen her sayı modellenmiştir" diye yanlış çıkarım yapamıyor.

> Bir dönem yedi alan katalogda duruyordu ve kodun hiçbir yerinde okunmuyordu. Dördü sonradan gerçekten bağlandı (`p_peak_w`, `p_shadow_w`, `p_hibernate_w`, `h_max_shadow_h`), kalanı etiketlendi. ("Round 3 review, M-8")

---

## Grid uyarlama nasıl çalışıyor?

`grids_for_rover(base_grids, rover_id, weights, risk_alpha)` fonksiyonu:

1. Talep edilen rover'ın kataloğunu okur
2. Rover'ın `slope_max_deg` değeri, grid'in varsayılan rover'ınınkinden farklıysa → **geçilebilirlik maskesini yeniden hesaplar**
3. Ağırlıklar farklıysa → **maliyet haritasını yeniden hesaplar**
4. Risk iştahı (`risk_alpha`) verilmişse → CVaR'lı maliyet haritası kurar ve metadata'ya damgalar
5. Yeni bir sözlük döner — **çağıranın grid'lerine dokunmaz**

### Neden ayrı bir modül?

Bu fonksiyon bir dönem `main.py`'nin (FastAPI kabuğunun) içindeydi. Sonuç: **ROS 2 kabuğu hiçbir zaman uyarlanmış grid görmedi.** Yani ROS üzerinden VIPER ile plan istediğinizde, LPR-1'in 25 derecelik maskesiyle planlanıyordu — VIPER'ın tırmanamayacağı yamaçlar geçilebilir sayılıyordu.

Bu, "Faz 4 final review bulgusu H1" olarak kayıtlı. Modül dışarı çıkarıldı; artık iki kabuk da aynı yerden çağırıyor.

**Bu, `saf çekirdek / ince kabuk` kuralının neden var olduğunun en net örneği.**

### Yan etkisizlik garantisi

Fonksiyon yeni bir sözlük ve **kopyalanmış** metadata döndürür. Çağıranın orijinal grid'leri değişmez.

Bu neden önemli: AI asistanının profil karşılaştırması yapmasına izin veriliyor (`compare_all_profiles`), çünkü o fonksiyon `grids_for_rover` üzerinden çalışıyor ve hiçbir uygulama durumunu değiştirmiyor. Ama AI'ın `/api/plan` çağırmasına izin **verilmiyor** — çünkü o, kullanıcının ekranındaki rotayı değiştirir.

---

## Önbellek anahtarlama

Aynı arazi için birden fazla maliyet haritası olabilir. Yanlış olanın kullanılmaması için metadata'da damga var:

| Damga | Ne ayırır |
|---|---|
| `COST_MODEL_ID` | Formül sürümü (şu an v5) |
| `risk_alpha` | Risk iştahıyla hesaplanmış grid, iştahsızdan ayrılır |
| `risk` | Eğim sigmasının nereden geldiği |
| `cost_criteria` | Hangi kriterlerin dâhil olduğu (pürüzlülük katmanı var mıydı?) |

`risk_alpha = None` olduğunda hiç damga konmuyor ve grid v4 formülünün **bit-bit aynısı** oluyor. Bu, geriye dönük uyumluluğun testlerle kanıtlanabilmesi için.

---

## İlham kaynağı

Rover verileri gerçek misyon yayınlarından:
- **NASA VIPER** — Shirley & Balaban 2022, Ennico-Smith vd. 2023
- **CNSA Yutu-2** — Chang'e-4 misyon yayınları; 2019'da indi, hâlâ çalışıyor (Ay'ın en uzun ömürlü rover'ı)
- **LUVMI-M** — Avrupa hafif rover konsepti
- **LPR-1** — bu projenin referans aracı

Çok-rover desteği fikri, gezegen rover planlayıcılarında standart: aynı planlayıcı farklı platformlara hizmet etmeli, ama platform parametreleri planlama matematiğine karışmamalı.

---

## Kodda nerede?

```
backend/app/constants.py
  ROVERS                ← dört aracın künyesi
  MODELLED_FIELDS       ← hangi alanların gerçekten okunduğu
  get_rover(id)         ← katalog erişimi
  rover_catalog()       ← API'ye yayınlanan hâli
  UnknownRoverError     ← geçersiz id

backend/app/rover_grids.py
  grids_for_rover()     ← uyarlama, tek doğruluk kaynağı
```

---

## Jüri soruları

**S: "Neden dört rover? Bir tane yetmez miydi?"**
Çünkü aynı planlayıcının farklı araçlarda çalıştığını göstermek, planlayıcının araçtan bağımsız olduğunun kanıtı. Ayrıca somut bir sonuç veriyor: Yutu-2 sadece 2 saat gölgeye dayanıyor, VIPER 96 saat. Aynı arazide biri geçebiliyor, biri geçemiyor — ve sistem bunu gösteriyor.

**S: "LPR-1 gerçek bir araç mı?"**
Hayır, projenin kendi referans aracı. Bunu saklamıyoruz. Diğer üçü gerçek misyon verileri. LPR-1'in varlığı, gerçek bir misyonun kısıtlarına bağlı kalmadan sistem davranışını gösterebilmek için.

**S: "Katalogdaki bütün sayılar modele giriyor mu?"**
Hayır ve bunu API açıkça söylüyor. `MODELLED_FIELDS` kümesindekiler giriyor, diğerleri referans amaçlı. Bir dönem yedi alan hiç okunmadan katalogda duruyordu; dördü bağlandı, kalanı etiketlendi.

**S: "Rover değiştirince ne oluyor?"**
Geçilebilirlik maskesi ve maliyet haritası **yeniden hesaplanıyor**. Yani plan sonucu değişiyor. Bu bir dönem sadece web API'sinde çalışıyordu, ROS tarafında çalışmıyordu — modül dışarı çıkarılarak düzeltildi.

**S: "Slip eğrisi neden rover'a özel?"**
Çünkü tekerlek tasarımı ve kütle kayma davranışını belirliyor. LPR-1'in slip eğrisi, Yutu-2 düz zemin ölçümü ve VIPER'ın 15 derece tasarım kısıtından **aktarılmış** — LPR-1 için yayınlanmış slip verisi yok, o yüzden kodda açıkça "her iki çapa da transfer" diye yazıyor. Detay: [slip modeli](../04-planlama-ve-maliyet/slip-modeli.md).
