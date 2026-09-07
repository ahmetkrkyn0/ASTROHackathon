# 2-D A* Planlayıcı — En Ucuz Yolu Bulmak

**Kodda:** `backend/app/pathfinder.py`
**API:** `POST /api/plan`, `POST /api/plan-multi`, `POST /api/compare`

---

## Nedir?

A* (A-star), bilgisayar biliminin en bilinen yol bulma algoritması. LunaPath'in 2-D planlayıcısı, maliyet haritası üzerinde başlangıçtan hedefe **en düşük toplam maliyetli** yolu buluyor.

"2-D" demek: durum sadece **(satır, sütun)**. Zaman boyutu yok — rover hiç durmuyor, hep ilerliyor.

---

## Hangi problemi çözüyor?

Maliyet haritası her hücreye bir puan veriyor. Ama 250 000 hücre arasından hangi hücre dizisinin toplam puanı en düşük?

Kaba kuvvetle denemek imkânsız: iki nokta arasında astronomik sayıda olası yol var. A*, bunu akıllıca budayarak yapıyor.

---

## Analoji: Yağmurda su birikintileri

Bir yağmur sonrası caddeyi karşıdan karşıya geçeceksiniz. Her yerde birikinti var, bazıları derin bazıları sığ.

Beyniniz otomatik olarak şunu yapıyor: **"toplam ıslaklığı en aza indiren yol."** Bu, düz çizgi değil — sığ birikintilerden dolaşan bir zikzak.

Ve şu sezgiyi kullanıyorsunuz: *"Karşı kaldırıma yaklaşan bir yön seçeyim, ters yöne gitmenin anlamı yok."* Bu sezgi, A*'ın **heuristiği**.

Kritik nokta: bu sezgi asla **abartmamalı**. "Şuraya gitmek en az 20 metre sürer" diyebilirsiniz (doğru), ama "en az 200 metre sürer" derseniz (abartı), aslında iyi olan bir yolu erkenden eleyip daha kötü bir yola razı olursunuz.

---

## Nasıl çalışıyor?

### İki aşamalı tasarım

**Aşama 1 — Ön hesaplama:** `cost_engine.compute_cost_grid()` ile hücre başına maliyet grid'i hesaplanıyor (beş kriter + AHP ağırlıkları).

**Aşama 2 — Arama:** A*, bu grid üzerinde yamuk (trapezoidal) kenar interpolasyonuyla çalışıyor.

### Kenar maliyet formülü

```
maliyet(u→v) = mesafe(u,v) × (1 + (maliyet_grid[u] + maliyet_grid[v]) / 2)
```

Yani: iki hücre arasındaki geometrik mesafe, iki ucun ortalama maliyetiyle ölçeklendiriliyor. "Yamuk" adı buradan — kenar boyunca maliyetin doğrusal değiştiği varsayılıyor ve integrali ortalama.

### Heuristik ve neden önemli

**Octile mesafesi**, `(1 + MIN_COST)` ile ölçeklendirilmiş.

Octile mesafesi, 8 komşulu bir grid'de iki nokta arası minimum adım maliyeti (düz adımlar 1, çapraz adımlar √2 sayılarak).

**Bu heuristik iki özelliği sağlıyor:**

| Özellik | Anlamı | Sonucu |
|---|---|---|
| **Kabul edilebilir** (admissible) | Gerçek maliyeti asla abartmıyor | Bulunan yol gerçekten optimal |
| **Tutarlı** (consistent) | Üçgen eşitsizliğine uyuyor | Bir hücre bir kez kapandıktan sonra tekrar açılmıyor |

Bu, "A* kullandık" demekle "A*'ı doğru kullandık" demek arasındaki farkı oluşturuyor.

---

## Optimizasyonlar — neden hızlı?

| Teknik | Ne yapıyor |
|---|---|
| **NumPy tipli diziler** | `g_score` float32, `closed` bool, `came_from` int32 — Python nesnesi yerine ham bellek |
| **Tembel yinelenen (lazy duplicate)** | Yığında bir düğümün eski kaydını silmek yerine (pahalı `decrease-key`), yeni kayıt ekleyip eskisini geldiğinde atlıyor |
| **Ön hesaplanmış 8 yön tablosu** | Komşu hesabı döngü içinde değil, hazır tabloda |
| **Erken çıkış** | Hedef genişletildiği anda duruyor |
| **Eşitlik bozma** `(f, h, sayaç)` | Aynı `f` skorlu düğümler arasında hedefe yakın olanı tercih ediyor — daha az düğüm açıyor |

### Köşe kesme güvenliği

Çapraz hareket, iki komşu hücrenin **ikisi de** geçilebilir değilse yasak.

**Neden:** İki kayanın arasından çapraz geçmek, gerçek dünyada mümkün değil. Grid'de çapraz adım "meşru" görünür ama rover fiziksel olarak sıkışır.

Bu kural, [MoonPlanBench benchmark'ında](../05-dogrulama-ve-test/benchmark-moonplanbench.md) referans planlayıcılardan ayrıştığımız noktalardan biri — onlar köşe kesmeye izin veriyor, biz vermiyoruz.

---

## Sonuç metrikleri

`astar_metrics` bloğu şunları raporluyor: açılan düğüm sayısı, arama süresi, yol uzunluğu, toplam maliyet.

⚠️ **Önemli bir dürüstlük detayı:** `astar_metrics.total_energy_wh` ve `total_shadow_hours` **her zaman `None`.** Bu bilinçli bir hızlı-mod tasarım kararı — A* bu toplamları tutmuyor.

Gerçek toplamlar aynı cevabın içindeki **simülasyon** bloğunda. AI asistanının kanıt katmanı (`ai_evidence.py`) bu iki alanı özellikle "tuzak" olarak işaretliyor: sayı gibi görünen ama `None` olan alanlar.

---

## Slip'in etkisi (C3 sonrası)

Slip modeli devreye girince maliyet yüzeyi değişti ve arama zorlaştı:

| Rover | Açılan düğüm (slip öncesi → sonrası) |
|---|---|
| LPR-1 | 8 799 → **23 177** (×2,6) |

Yani slip'li maliyet yüzeyi 2,6–2,8 kat daha fazla düğüm açtırıyor. Sebebi: slip, maliyet farklarını keskinleştiriyor ve heuristiğin rehberliği zayıflıyor.

Enerji sonuçları:

| Rota | Slip öncesi | Slip sonrası |
|---|---|---|
| LPR-1 gündüz | 469 Wh | **597 Wh** (×1,27) |
| LPR-1 ay gecesi | 1 288 Wh | 1 466 Wh |
| VIPER standart | 2 156 Wh | **2 742 Wh** (×1,27) |

---

## Ne zaman 2-D, ne zaman 4-D?

| | 2-D A* | [4-D A*](planlayici-4d.md) |
|---|---|---|
| Durum | (satır, sütun) | (satır, sütun, zaman dilimi) |
| "Bekle" kararı | ❌ Yok | ✅ Var |
| Hız | Hızlı (~yüz ms) | Yavaş (~saniye) |
| Kullanım | Hızlı karşılaştırma, profil süpürme, çok-rota | Gerçek misyon planı |

2-D planlayıcı **dokunulmadı** — 4-D bir yerine geçiş değil, ek bir planlayıcı.

---

## Kodda nerede?

```
backend/app/pathfinder.py
  astar()                    ← ana arama
  astar_metrics              ← sonuç metrikleri
  octile heuristiği
  köşe kesme kontrolü
```

---

## Jüri soruları

**S: "Neden A*? Dijkstra veya RRT değil?"**
A*, Dijkstra'nın heuristikli hâli — hedefe doğru yönlendiği için çok daha az düğüm açıyor ve heuristik kabul edilebilir olduğu sürece **aynı optimal sonucu** veriyor. RRT örnekleme tabanlı ve optimallik garantisi yok; grid tabanlı bir problemde A* daha uygun.

**S: "Sonucun optimal olduğunu nasıl biliyorsunuz?"**
Heuristiğin kabul edilebilir ve tutarlı olması sayesinde. Octile mesafesini `(1 + MIN_COST)` ile ölçekliyoruz — bu, gerçek maliyeti asla abartmayan bir alt sınır. A*'ın optimallik teoremi bu şartla geçerli.

**S: "Ne kadar hızlı?"**
500×500 grid'de tipik olarak yüz milisaniye mertebesinde. Slip modeli devreye girdikten sonra 2,6 kat daha fazla düğüm açıyoruz (LPR-1'de 8 799 → 23 177) çünkü maliyet yüzeyi keskinleşti.

**S: "Çapraz hareketlerde köşe kesmeye izin veriyor musunuz?"**
Hayır. İki kayanın arasından çapraz geçmek gerçek dünyada mümkün değil. Bu bizi bazı literatür planlayıcılarından ayırıyor — MoonPlanBench'teki referans planlayıcılar (PythonRobotics Dijkstra/A*/Theta*) köşe kesmeye izin veriyor. Benchmark'ta her iki hareket modelini de yan yana çalıştırdık.

**S: "`total_energy_wh` neden `None`?"**
A* bu toplamları tutmuyor, bu bilinçli bir hızlı-mod kararı. Gerçek enerji toplamı aynı cevabın simülasyon bloğunda. Bu tuzağı biliyoruz ve AI kanıt katmanında özellikle işaretledik — asistanın "enerji `None`" diye bir cümle kurması engellendi.
