> **HCI Review** — LunaPath
> Üretildi: 2026-09-05
> Üretici: SevgiAI v1.1.0 · `/sevgi-ai:hci-review`
> Standart/Kaynak: SENG 477 (ISO 13407, Alan Dix Usability Principles, Colours in HCI), WCAG 2.1 AA

---

## 1. Bağlam

**Değerlendirilen ürün.** LunaPath Mission Workstation — Ay güney kutbunda rover
rotası planlayan tam ekran kokpit arayüzü. React 18 + TypeScript + Vite,
canvas tabanlı harita (500×500 ızgara), FastAPI arka uç.

**Değerlendirilen akış.** Uçtan uca birincil görev:
`Landing → Kokpite gir → Rover seç → Başlangıç koy → Hedef koy → Rota üret →
Oynatmayı izle → Görev raporunu oku`.

**İncelenen kaynak.** Kod tabanının kendisi (tahmin değil):

| Kaynak | Rol |
|--------|-----|
| `docs/archive/stitch_design_brief.md` | Hedef kitle ve tasarım yönü |
| `frontend/src/App.tsx`, `MapCanvas.tsx`, `TerrainCanvas3D.tsx` | Kabuk ve harita |
| `frontend/src/features/**` (17 feature) | Panel ve etkileşim katmanı |
| `frontend/src/App.css` + 11 feature CSS (7.138 satır) | Tasarım sistemi |
| Canlı oturum: 1600×1000 ve 860×900 ekran görüntüleri | Gerçek render |
| Hesaplanmış WCAG kontrast oranları (tarayıcıda ölçüldü) | Bölüm 4, F2 |

**Kullanıcı sınıfları.** Brief ikisini birden adlandırıyor: *"Target Audience:
Hackathon judges, space engineers."* Bu iki sınıfın bilişsel profili ve görev
süresi farklı olduğu için **her bulgu iki sınıf için ayrı etkilendirilmiştir**.

| Sınıf | Kod | Bilgisayar okuryazarlığı | Alan bilgisi | Maruz kalma |
|-------|-----|--------------------------|--------------|-------------|
| Jüri üyesi | **J** | Sufficient | Partial | Tek seferlik, ~5 dakika, gözetimsiz |
| Misyon operatörü | **O** | Sufficient | Sufficient | Tekrarlı, uzun oturum, günlük |

---

## 2. Kullanıcı Modeli

### 2.1 Perseptüel kısıtlar

- **Ekran koşulu.** Jüri demosu tipik olarak projeksiyon ya da yansımalı bir
  dizüstü ekranında izlenir. Arayüz koyu zemin (`--bg-card: #0c1018`) üzerine
  düşük parlaklıkta metin kullanıyor; bu koşulda etkin kontrast, ölçülen
  laboratuvar değerinin altına düşer. Bölüm 4/F2 bu yüzden J için de yüksek
  etkili işaretlenmiştir.
- **Versal metin yükü.** Kod tabanında **47 ayrı `text-transform: uppercase`
  kuralı** var. Büyük harf, sözcüğün üst-alt çıkıntı siluetini yok ederek
  okuma hızını düşürür; etiket olarak doğru, gövde metni olarak maliyetlidir.

### 2.2 Bilişsel kısıtlar

- **J için alan modeli yok.** "Traversability", "corridor", "SoC", "barrier
  share", "lateral slope" terimleri J'nin zihinsel modelinde karşılıksızdır.
  Sistem-gerçek dünya eşleşmesi (Nielsen 2) bu sınıf için zayıftır.
- **Çalışma belleği.** Birincil görev dört adımlıdır ve sıra bağımlıdır
  (rover → başlangıç → hedef → rota). `MISSION SEQUENCE` bloğu bu yükü
  dışsallaştırdığı için doğru bir karardır (bkz. Bölüm 5/P1).
- **O için tersi geçerli.** O, terminolojiyi tanır; onun kısıtı bilgi
  yoğunluğu değil, **tekrar maliyetidir** — aynı işlemi günde onlarca kez
  yapar, dolayısıyla kısayol ve geri alma eksikliği doğrudan verim kaybıdır.

### 2.3 Ergonomik / motor kısıtlar

- Birincil görevin iki adımı (başlangıç ve hedef koyma) **yalnızca fare ile**
  yapılabilir. Klavye, ekran okuyucu veya alternatif giriş yolu yoktur
  (F1). Bu, ISO 13407'nin "appropriate allocation of function" ilkesinin
  ihlalidir: sistem, girdi biçimini tek bir modaliteye sabitlemiştir.

---

## 3. Sezgisel İnceleme — Alan Dix Üç Çatısı

### 3.1 Learnability (Öğrenilebilirlik)

| Prensip | Değerlendirme | Kanıt |
|---------|---------------|-------|
| **Predictability** | Yeterli. Aynı hücreye aynı ağırlıklarla iki kez plan yapmak aynı rotayı verir; planlayıcı deterministiktir. | `backend/app/pathfinder.py` (A*, rastgelelik yok) |
| **Synthesizability** | **Zayıf.** Ağırlık kaydırıcıları (`ROUTE PRIORITIES`) değiştirildiğinde mevcut rota güncellenmez ve bunun söylendiği bir gösterge yoktur; kullanıcı değişikliğin etkisini göremez. | `MissionSetupPanel.tsx` — kaydırıcı `setWeights` çağırır, `planRoute` çağırmaz |
| **Familiarity** | Karma. Harita üzerine tıklayarak pin koyma yaygın bir kalıptır (aktarılabilir). Ancak "Select Start" düğmesine önce basıp sonra haritaya tıklama iki adımlı silahlanma modeli, harita uygulamalarının çoğunda yoktur. | `MissionSetupPanel.tsx:202`, `MapCanvas.tsx:275` |
| **Generalizability** | Yeterli. Panel başlığı, ölçüm değeri ve etiket kalıbı 17 feature boyunca aynıdır. | Tek tasarım sistemi: `App.css` token bloğu |
| **Consistency** | **Zayıf — dil.** Kokpit İngilizce, AI asistanı tamamen Türkçedir (F8). |

### 3.2 Flexibility (Esneklik)

| Prensip | Değerlendirme |
|---------|---------------|
| **Dialog initiative** | Dengesiz. Görev raporu, oynatma bittiğinde ekranı **sistem inisiyatifiyle** tamamen devralır (F6). |
| **Multithreading** | Sınırlı. Asistan penceresi haritayla eş zamanlı açık kalabilir (olumlu); ancak rapor modali açıkken hiçbir şey yapılamaz. |
| **Task migratability** | Yeterli. Ağırlık seçimi hazır profillere (Balanced Recon, Energy Saver…) devredilebilir; kullanıcı isterse elle ayarlar. |
| **Substitutivity** | **Yok.** Başlangıç/hedef yalnızca tek yolla girilebilir: haritaya tıklama. Koordinat yazarak girme yolu yoktur (F1). |
| **Customizability** | Zayıf. Raylar katlanabilir ve Systems çekmecesi ayrılmıştır (olumlu); ancak panel sırası, birim ya da dil seçilemez. |

### 3.3 Robustness (Sağlamlık)

| Prensip | Değerlendirme |
|---------|---------------|
| **Observability** | İyi. Batarya, eğim, sıcaklık, risk her adımda okunabilir; `MISSION SEQUENCE` sistemin hangi adımda olduğunu söyler. |
| **Recoverability** | **Zayıf.** Geri alma yoktur; `Clear` her iki uç noktayı birden siler (F4). |
| **Responsiveness** | Karma. Görsel geri bildirim güçlüdür (`RouteSolvingOverlay`), ancak bu overlay bir canlı bölge değildir; ekran okuyucu kullanıcıya 2–10 saniyelik hesaplama hiç duyurulmaz (F9). |
| **Task conformance** | İyi. Sistem, görevin doğasına uygun çıktılar üretir (koridor, enerji bütçesi, risk dağılımı) ve kapsamı dışındakini açıkça reddeder. |

---

## 4. Bulgular

Etki ölçeği: **Critical** (görevi engelliyor / standart ihlali) · **High** ·
**Medium** · **Low**. `J` = jüri üyesi, `O` = misyon operatörü.

| # | Bulgu | Etki (J / O) | Önerilen Aksiyon | Referans |
|---|-------|--------------|------------------|----------|
| **F1** | **Birincil görev klavyeyle yapılamıyor.** `<canvas>` öğesinde `tabIndex`, `role`, `aria-label` ve `onKeyDown` yok; yalnızca `onClick` ve `onMouseMove` var. Başlangıç/hedef koymak — uygulamanın var oluş nedeni — fare dışında hiçbir yolla mümkün değil. WCAG 2.1.1 Keyboard (Seviye **A**) ihlali. | Critical / Critical | `tabIndex={0}` + `role="application"` + `aria-label` ekle; ok tuşlarıyla hücre imleci, `Enter` ile yerleştirme. Ayrıca **substitutivity** için sol raya "satır, sütun" sayısal girişi koy — bu aynı zamanda O'nun bilinen koordinata gitmesini hızlandırır. | Alan Dix — Substitutivity; WCAG 2.1.1 |
| **F2** | **Üç metin token'ı WCAG AA kontrastını geçmiyor.** Tarayıcıda ölçüldü, `--bg-card` (#0c1018) üzerinde: `--text-dim-2` (#5d677c) = **3.35:1**, `--text-dim` (#6d7789) = **4.22:1**, `--text-dimmest` (#4c5566) = **2.54:1**. AA eşiği normal metin için 4.5:1'dir ve bu token'lar 11px'te kullanılıyor, yani "large text" istisnası geçerli değil. `--text-dim-2` tek başına **51 yerde** kullanılıyor; grafik eksen etiketleri de aynı rengi kullanıyor (`charts.tsx:35`, `AXIS_TEXT = '#5d677c'`). | High / High | `--text-dim-2` değerini en az `#7b8497` (5.07:1) seviyesine çek; `--text-dimmest`'i metinden tamamen kaldır, yalnızca dekoratif çizgi/ikon için sakla. Token merkezi olduğu için düzeltme tek noktadan 51 kullanımı birden düzeltir. | Colours in HCI — Contrast; WCAG 1.4.3 |
| **F3** | **Devre dışı düğmenin gerekçesi yalnızca fareyle görülebiliyor.** `Generate Route` düğmesi `disabled` iken sebebini `title` niteliğiyle veriyor (`MissionSetupPanel.tsx:203`). Devre dışı öğeler odaklanabilir değildir ve `title` çoğu ekran okuyucuda seslendirilmez; ipucu yalnızca fareyle üzerine gelen kullanıcıya ulaşır. Gerekçeye en çok ihtiyacı olan kullanıcı onu göremiyor. | High / Low | Gerekçeyi görünür metne çevir. `MISSION SEQUENCE` bloğu bu bilgiyi zaten doğru biçimde gösteriyor (`02 Start — SELECT`, `03 Goal — WAITING`); düğmenin altına aynı kalıpta tek satırlık bir durum metni koy. | Nielsen 1 — Visibility of system status; Feedforward |
| **F4** | **Geri alma yok.** Yanlış konulan bir hedefi geri almanın yolu yok; tek kurtarma aracı `Clear`, o da **iki** uç noktayı birden siliyor. Kullanıcı tek hatalı tıklama için doğru olan adımı da kaybediyor. | Medium / High | `Ctrl+Z` ile son yerleştirmeyi geri al. En düşük maliyetli ara çözüm: `Clear` yerine uç nokta düğmelerinin kendisini yeniden tıklanabilir yapıp tekil sıfırlama sun. | Alan Dix — Recoverability; Nielsen 3 |
| **F5** | **Hata mesajı, izlenemeyen bir aksiyon öneriyor.** Geçilemez hücre seçildiğinde çıkan uyarı *"Select an adjacent terrain cell with manageable slope"* diyor (`App.tsx:850-857`). Ancak varsayılan `Surface` katmanında hangi hücrenin geçilebilir olduğu görünmez; bu bilgiyi taşıyan `Traversability` katmanı var, fakat mesaj kullanıcıyı oraya yönlendirmiyor. Doğru yazılmış bir mesaj, uygulanamayan bir talimatla bitiyor. | High / Medium | Toast'a "Show traversable cells" eylem düğmesi ekle; tıklandığında `viewMode`'u `traversability`'ye çevirsin. Böylece mesaj kendi çözümünü icra edilebilir hale getirir. | Nielsen 9 — Hata mesajları çözüm önermeli |
| **F6** | **Rapor ekranı sistem inisiyatifiyle devralıyor.** Oynatma son waypoint'e ulaştığında tam ekran rapor kendiliğinden açılıyor (`useMissionReport.ts`). J için bu yönlendiricidir; O için, animasyonu belirli bir segment için izlerken kesintiye uğramak demektir. Diyalog inisiyatifi tamamen sistemdedir. | Low (olumlu) / Medium | İlk tamamlamada otomatik aç; sonraki çalıştırmalarda modal yerine durum şeridinde "Report ready" göstergesi bırak. Mevcut launcher düğmesi zaten bu rolü üstlenebilir. | Alan Dix — Dialog initiative |
| **F7** | **Klavye odağı büyük ölçüde görünmez.** 7.138 satırlık CSS'te yalnızca **5 adet** `:focus` / `:focus-visible` kuralı var; 42 düğmenin çoğunda odak halkası tarayıcı varsayılanına bırakılmış ve koyu zeminde ayırt edilmiyor. WCAG 2.4.7 Focus Visible (Seviye AA). | Medium / High | Tek bir genel kural yeter: `:focus-visible { outline: 2px solid var(--lavender); outline-offset: 2px; }`. Tasarım sistemi token'lı olduğu için tek ekleme tüm bileşenleri kapsar. | WCAG 2.4.7 |
| **F8** | **Arayüz dili tutarsız.** Kokpit, harita, paneller ve görev raporu İngilizce; AI asistanı tamamen Türkçe (`features/assistant/ChatPanel.tsx` — 74 Türkçe satır: "Analiz Asistanı", "Görev karar desteği", "Rotayı özetle"). Aynı ekranda iki dil, tutarlılık ilkesinin doğrudan ihlalidir. | High / Medium | Asistanın dili **etiket değil mantıktır**: `backend/app/ai_grounding.py` Türkçe morfolojiyle çalışır (`_SUFFIX` eki eşleştirir, `_NUMERAL_WORDS` Türkçe sayı sözcüklerini tutar, `_LEFTOVER_PERCENT` `\byüzde\b` arar) ve 182 test satırı bu davranışı sabitler. Yarım çeviri, halüsinasyon korumasını sessizce devre dışı bırakır. Ayrı ve tam bir iş kalemi olarak planla; ara çözüm olarak panel başlığına dil etiketi koy. | Alan Dix — Consistency; Nielsen 4 |
| **F9** | **Uzun süren işlem ekran okuyucuya duyurulmuyor.** Rota hesaplama 2–10 saniye sürüyor ve güçlü bir görsel overlay ile gösteriliyor (`RouteSolvingOverlay.tsx`), ancak bu overlay canlı bölge değil. Projede yalnızca **iki** `aria-live` var (toast yığını ve asistan) ve hiçbiri çözüm durumunu kapsamıyor. | Low / Medium | Overlay köküne `role="status" aria-live="polite"` ekle ve içine "Computing route" metnini koy. Toast yığını bu kalıbı zaten doğru uyguluyor (`App.tsx:771`), aynısını tekrarla. | Nielsen 1; WCAG 4.1.3 |
| **F10** | **Ağırlık değişikliği sonuçsuz kalıyor.** `ROUTE PRIORITIES` kaydırıcıları değiştirildiğinde ekrandaki rota olduğu gibi kalır ve bunun yeniden planlama gerektirdiği söylenmez. Kullanıcı, yaptığı değişikliğin etkisini sentezleyemez. | Medium / High | Kaydırıcı hareket ettiğinde rotayı "stale" olarak işaretle (soluklaştır) ve `Generate Route` düğmesini "Re-plan with new weights" olarak etiketle. | Alan Dix — Synthesizability |
| **F11** | **Tooltip'ler yalnızca `title` niteliğiyle veriliyor.** 27 kullanım var; örneğin görev profili çipleri açıklamalarını yalnızca `title` ile taşıyor (`MissionSetupPanel.tsx:238`). `title` dokunmatik cihazda hiç görünmez, klavye odağında açılmaz ve gecikmesi kullanıcı tarafından ayarlanamaz. J, profiller arasındaki farkı bu yüzden okuyamaz. | Medium / Low | Profil açıklamasını, seçili çipin altında kalıcı tek satır olarak göster. Veri arka uçta zaten mevcut (`scenarios.py` → `description`). | Nielsen 6 — Tanıma > hatırlama |
| **F12** | **Kalıcı uyarı hiç çözülmüyor.** Zaman ekseninde *"No time series — this cube does not vary with time, so it is not animated. real illumination unavailable."* metni sarı renkte, sürekli görünür duruyor (`TimeAxisPanel.tsx:80`). Kullanıcının bu konuda alabileceği bir aksiyon yok; kalıcı uyarı, bir süre sonra tüm uyarıların göz ardı edilmesini öğretir. | Medium / Low | Uyarı tonundan nötr bilgi tonuna indir ve zaman ekseni kontrollerini bu durumda gizle. Kullanıcı, kullanamayacağı bir kontrolün yanında gerekçe okumak zorunda kalmasın. | Nielsen 8 — Estetik ve minimal tasarım |

**Dağılım:** Critical 1 · High 4 · Medium 6 · Low 1 (etki, iki sınıfın en
yükseğine göre sayılmıştır).

### 4.1 Çözüm Durumu

Bulguların tamamı aynı gün uygulandı ve tarayıcıda doğrulandı. "Doğrulama"
sütunu, kodun varlığını değil gözlenen davranışı bildirir.

| # | Durum | Ne yapıldı | Doğrulama |
|---|-------|-----------|-----------|
| F1 | Kapatıldı | `MapCanvas.tsx`: `tabIndex=0`, `role="application"`, durum bildiren `aria-label`, ok tuşlarıyla imleç (Shift = 10 hücre), Enter/Space ile yerleştirme. İmleç `hoverCell`'e bağlandı, böylece nişangah ve LAT/LON okuması da klavyeyi izliyor. Gizli `aria-live` bölgesi imleç konumunu duyuruyor. | Yalnızca klavyeyle: START (252, 262) ve GOAL (332, 292) yerleştirildi, rota üretildi |
| F2 | Kapatıldı | `--text-dim` → `#808a9d`, `--text-dim-2` → `#7b8497`, `--text-dimmest` → `#737d90`. Grafik eksen rengi (`charts.tsx`) aynı değere çekildi. | Ölçüldü: en kötü oran **4.59:1** (önce 2.54:1); üçü de AA'yı geçiyor |
| F3 | Kapatıldı | `title` kaldırıldı; gerekçe `.lp-panel-hint` olarak görünür metne çevrildi | "Select a Start point on the terrain first." panelde görünüyor |
| F4 | Kapatıldı | Tek yuvalı geri alma: `undoPlacement` eylemi, `Ctrl/Cmd+Z` kısayolu (metin alanlarında devre dışı) ve Clear'ın yanında görünür `Undo` düğmesi | Ctrl+Z hedefi geri aldı, başlangıcı korudu, seçiciyi yeniden silahlandırdı |
| F5 | Kapatıldı | Toast'a `actionId` alanı eklendi; geçilemez hücre uyarısı artık "Show traversable cells" düğmesi taşıyor ve katmanı değiştiriyor | Düğmeye basınca katman `Surface` → `Traverse` oldu |
| F6 | Kapatıldı | Otomatik açılma modül düzeyinde bir bayrakla oturumda bir kereye indirildi; sonrasında launcher yeterli | İkinci oynatmada modal açılmadı, launcher görünür kaldı |
| F7 | Kapatıldı | Tek genel kural: `:focus-visible { outline: 2px solid var(--lavender) }` | Tab ile gezildi: `outlineWidth 2px`, `rgb(179,165,255)`, `:focus-visible` eşleşiyor |
| F8 | **Kısmî** | Tam çeviri yapılmadı; gerekçesi aşağıda. Panel başlığına `TR` rozeti ve launcher'a "Turkish-language assistant" etiketi eklendi | Rozet görünüyor, `title` açıklaması mevcut |
| F9 | Kapatıldı | Overlay'in tamamı yerine tek cümlelik gizli canlı bölge (`role="status"`) — kicker, başlık, detay ve üç etiketi seslendirmek bir bilgi için üç saniye konuşma olurdu | Markup doğrulandı; paylaşılan `.lp-visually-hidden` sınıfı |
| F10 | Kapatıldı | Rotanın çözüldüğü ağırlıklar `plannedWeightsRef` ile saklanıyor; ayrışınca uyarı çıkıyor ve düğme "Re-plan with new weights" oluyor | Kaydırıcı oynatıldı: uyarı ve yeni etiket göründü |
| F11 | Kapatıldı | Profil açıklaması `title` yerine kalıcı metin (`.lp-profile-desc`) | "Standard mode; weighs every risk evenly." panelde görünüyor |
| F12 | Kapatıldı | Kalıcı uyarı, uyarı tonundan nötr bilgi tonuna indirildi | `lp-time-warn` sınıfı kaldırıldı |

**F8 neden kısmî.** Asistanın dili etiket değil, mantıktır.
`backend/app/ai_grounding.py`, modelin uydurduğu sayıları yakalayan koruma
katmanıdır ve Türkçe morfolojiyle çalışır: `_SUFFIX` Türkçe ekleri eşleştirir,
`_NUMERAL_WORDS` yazıyla yazılmış Türkçe sayıları tutar, `_LEFTOVER_PERCENT`
`\byüzde\b` arar. `ai_prompt.py` 152 satırlık Türkçe sistem promptu taşır ve
182 test satırı bu davranışı sabitler. Yalnızca yüzeyi çevirmek, korumayı
artık konuşulmayan bir dili eşleştirir halde bırakır ve **sessizce açık
konuma düşürür**. Tam dönüşüm ayrı bir iş kalemidir: guard'ın İngilizce
morfoloji için yeniden yazılması, promptun çevrilmesi, test paketinin
yenilenmesi.

### 4.2 Yeni Yerleşim Düzeltmeleri

F4'ün getirdiği `Undo` düğmesi, aksiyon satırını üç kontrole çıkardı ve
250px'lik rayda "Generate Route" kırpıldı. Kurtarma kontrolleri (Undo, Clear)
bir satırda, birincil eylem tam genişlikte kendi satırında toplandı; bu aynı
zamanda daha doğru hiyerarşidir. 1600px ve 860px'te konteynerini taşan
element yok.

---

## 5. Olumlu Noktalar

| # | Tespit | Neden doğru |
|---|--------|-------------|
| **P1** | **`MISSION SEQUENCE` görev durumunu dışsallaştırıyor.** Dört adım numaralı olarak listeleniyor ve her biri kendi durumunu taşıyor (`01 Rover — LPR_1`, `02 Start — SELECT`, `03 Goal — WAITING`, `04 Route — NOT GENERATED`). | Sıra bağımlı bir görevde çalışma belleği yükünü ekrana aktarır. Nielsen 1 ve 6'yı aynı anda karşılar; J'nin gözetimsiz ilerleyebilmesinin asıl nedeni budur. |
| **P2** | **Hata mesajları üç katmanlı yazılmış.** `buildToastNotice` (`App.tsx:846`) her hata için başlık, sade dilde açıklama ve önerilen aksiyon üretiyor; ham arka uç metnini `detail` alanında ayrı tutuyor. | Nielsen 9'un tam karşılığı. J sade açıklamayı, O ham detayı okur — tek mesaj iki sınıfa birden hizmet eder. F5'teki eksik yalnızca aksiyonun icra edilebilir olmaması. |
| **P3** | **Bilgi mimarisi ikiye ayrılmış.** Dokuz panelin altısı "Systems & Evidence" çekmecesine taşınmış (`features/registry.ts`, `group: 'systems'`); varsayılan kokpitte yalnızca görev ve bağlam kalıyor. | Progressive disclosure. J varsayılan görünümde boğulmaz, O kanıt panellerine tek tıkla ulaşır. Aynı ekranın iki sınıfa hizmet etmesini sağlayan karar budur. |
| **P4** | **Renk tek anlam taşıyor ve yalnız bırakılmıyor.** Risk rampası (`--risk-low/med/high/crit`) harita, panel, grafik ve tabloda aynı dört değeri kodluyor; risk seviyesi ayrıca metinle de yazılıyor (`LOW`, `CRITICAL`). | Colours in HCI: bilgi yalnızca renkle taşınmıyor. Renk körlüğü olan kullanıcı için WCAG 1.4.1 karşılanıyor. |
| **P5** | **`prefers-reduced-motion` destekleniyor.** Hem `App.css` hem `assistant.css` bu medya sorgusunu tanımlıyor. | Vestibüler rahatsızlığı olan kullanıcılar gözetilmiş. Bu ölçekte bir prototipte sık atlanan bir ayrıntıdır. |
| **P6** | **Tip ve renk artık token'lı tek ölçek.** Yedi basamaklı tip ölçeği ve beş basamaklı harf aralığı ölçeği merkezi token olarak tanımlı; 11px taban olarak sabitlenmiş. | F2 ve F7'nin düzeltmesini tek noktadan mümkün kılan altyapı budur. |

---

## 6. Sonraki Adım Önerileri

| Sıra | Aksiyon | Gerekçe |
|------|---------|---------|
| 1 | **F1 ve F2'yi jüri demosundan önce kapat.** İkisi de standart ihlali, ikisi de sınırlı dokunuşla çözülüyor (bir canvas erişilebilirlik katmanı + bir token değeri). | Critical/High ve düşük maliyet. |
| 2 | `/sevgi-ai:color-audit` | F2'yi palet düzeyinde tamamlar: 60-30-10 dengesi ve dark mode kontrast taraması bu incelemenin kapsamı dışında bırakıldı. |
| 3 | `/sevgi-ai:heuristic-eval` | Bu inceleme bütünsel; Nielsen 10 üzerinden severity (0-4) puanlı ayrıntılı kural denetimi ayrıca yapılmalı. |
| 4 | `/sevgi-ai:usability-eval-plan` | F3, F5 ve F11 varsayıma değil gözleme muhtaç: J sınıfından 3-5 kişiyle görev tabanlı test, bu üç bulgunun gerçek etkisini ölçer. |

---

## Bilinen Boşluklar

| # | Boşluk | Neden açık | Önerilen çözüm |
|---|--------|------------|----------------|
| 1 | 3D mod (`TerrainCanvas3D.tsx`) etkileşim açısından değerlendirilmedi | Bu oturumun tarayıcı ortamında WebGL kullanılamıyor; sahne render edilemediği için gözleme dayalı bulgu üretilemedi | Gerçek donanımda ayrı bir geçiş yapılmalı |
| 2 | Asistanın konuşma akışı (turn-taking, hata kurtarma) incelenmedi | Değerlendirme sırasında canlı bir LLM yanıtı alınmadı; yalnızca boş durum gözlendi | Asistanla gerçek bir oturum kaydı üzerinden ayrı inceleme |
| 3 | Mobil / dokunmatik bağlam kapsam dışı | Brief arayüzü açıkça "full-screen immersive cockpit" olarak tanımlıyor (`stitch_design_brief.md`); dokunmatik hedef boyutu bu yüzden ölçülmedi | Ürünleşme kararı alınırsa WCAG 2.5.5 (Target Size) ayrıca denetlenmeli |
| 4 | Gerçek kullanıcıyla test yapılmadı | Bu bir uzman incelemesidir (expert review), kullanıcı testi değil; ISO 13407'nin "değerlendirme" aktivitesi yalnızca kısmen karşılanır | Madde 4 / `/sevgi-ai:usability-eval-plan` |
| 5 | Ekran okuyucu ile fiili doğrulama yapılmadı | Düzeltmeler DOM, hesaplanmış stil ve gözlenen davranış üzerinden doğrulandı; VoiceOver/NVDA ile teyit edilmedi | VoiceOver ile birincil akış bir kez yürütülmeli |
| 6 | Geliştirme ortamında bir kez `Cannot update a component (App) while rendering a different component (PlaybackBar)` uyarısı görüldü | Dosyalar canlı düzenlenirken Vite HMR modülleri değiştiriyordu. Temiz tamponla yeniden koşulan hiçbir akış — ilk plan, yeniden oynatma, bayat ağırlık yolu — uyarıyı üretmedi; değişiklikler geri alınmış baseline de üretmedi | Üretim derlemesinde izlenmeli; şu an dev-only HMR yan etkisi olarak değerlendiriliyor |
