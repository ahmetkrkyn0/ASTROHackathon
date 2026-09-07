# LunaPath — AI-01 "Analiz Asistanı"
## Kapsam ve Arayüz Sözleşmesi

> **Belge kimliği:** `AI-02` · **Durum:** TASLAK v0.1 · **Tarih:** 1 Eylül 2026
> **Öncül belge:** `AI-01` — AI Asistan Literatür Taraması
> **Referans kütüphane:** `BELGE 00–10` (LunaPath Birleşik Araştırma Kütüphanesi)

---

## 0. Bu belge nedir, ne değildir

**Nedir:** AI-01 özelliğinin **ne yapacağının, ne yapmayacağının ve hangi veriyi hangi biçimde alıp vereceğinin** sözleşmesi. Backend'in bugünkü hâline bağlı değildir.

**Ne değildir:** Bir implementasyon planı, bir endpoint listesi veya bir system prompt. Bunlar §9'daki teyit listesi doldurulduktan sonra ayrı belgelerde yazılacaktır.

### 0.1 Neden backend-bağımsız yazılıyor

Backend aktif geliştirme altında. Somut endpoint isimlerine, alan adlarına ve yanıt şekillerine bağlı bir kapsam belgesi, backend her değiştiğinde geçersizleşir — ve o belgeye dayanan system prompt sessizce yanlış çalışır. Bu belge bunun yerine **üç katmanlı bir soyutlama** kurar:

```
  [ Kapsam ve yetenek tanımı ]     ← bu belge · backend'den bağımsız · nadiren değişir
              │
  [ AnalysisProvider portu    ]     ← bu belge §5 · soyut arayüz · seyrek değişir
              │
  [ Adaptör (backend'e bağlar)]     ← ayrı dosya · backend her değiştiğinde SADECE BURASI değişir
              │
  [ Gerçek backend            ]     ← değişken
```

**Kural:** AI katmanının hiçbir bileşeni backend'in endpoint adını, alan adını veya sayısal sabitini bilmez. Hepsi adaptörden geçer.

### 0.2 Yetenek keşfi — kırılganlığa karşı asıl önlem

Asistan, hangi analizleri yapabileceğini **derleme zamanında değil, çalışma zamanında** öğrenir. Adaptör `getCapabilities()` çağrısıyla backend'in o an desteklediği yetenek listesini döner; asistan yalnızca bu listedeki araçları kullanır.

Sonuç: backend'de bir yetenek henüz yoksa veya kaldırıldıysa asistan **hata vermez**, şunu der:

> *"Bu soruyu cevaplamak için duyarlılık analizi gerekiyor ama sistemde şu an bu hesap açık değil. Bunun yerine rotanın maliyet ayrışımını gösterebilirim."*

Bu davranış literatürdeki "cevaplanabilirlik kapısı" (answerability gate) desenidir ve `AI-01` §3.9'da gerekçelendirilmiştir.

---

## 1. Konumlandırma ve sert sınırlar

`BELGE 09` §6'daki konumlandırma bu özellik için de **değişmeden** geçerlidir:

> LunaPath, Ay güney kutbunda görev yapacak rover'lar için bir **görev öncesi planlama ve karar destek aracıdır**; rover üzerinde çalışan bir otonomi modülü değildir.

AI-01 bu konumlandırmayı **değiştirmez**. Asistan bir *operatör arayüzü katmanıdır*. Bundan doğan üç sert sınır:

| # | Sınır | Gerekçe |
|---|---|---|
| **B-1** | AI-01 uçuş yazılımı iddiasının parçası olamaz | LLM rad-hard donanımda çalışmaz; ECSS doğrulanabilirlik gereksinimleriyle uyumsuz (`BELGE 04` §8, `BELGE 08` §4) |
| **B-2** | AI-01 sistemin TRL seviyesini yükseltmez | TRL 3 civarı analitik kavram kanıtı (`BELGE 09` §3). Arayüz katmanı olgunluk boyutlarının hiçbirini yükseltmez |
| **B-3** | AI-01 devre dışıyken sistem tam işlevsel kalmalı | Demo dayanıklılığı + `BELGE 04` §7.3'ün uyarısına uyum. Deterministik katman asistanın önkoşulu değil, tersi doğru |

---

## 2. KAPSAM — Asistan ne YAPAR

Her madde bir gereksinim numarası taşır; kabul kriterleri §10'da bunlara atıf yapar.

| # | Yetenek | Tek cümlelik tanım |
|---|---|---|
| **S-1** | Seviye tespiti | Kullanıcının teknik seviyesini **açık soruyla** belirler ve oturum boyunca korur; kullanıcı istediği an değiştirebilir |
| **S-2** | Sonuç özetleme | Mevcut bir analiz sonucunu seviyeye uygun dilde özetler |
| **S-3** | Maliyet ayrıştırma | "Bu rotanın maliyeti neyden geldi?" — bileşen bazlı katkı dağılımı |
| **S-4** | Nokta sorgusu | "Bu hücrede/segmentte ne oluyor?" — konuma özgü açıklama |
| **S-5** | Bağlayıcı kısıt tespiti | "Bu rotayı ne sınırladı?" — hangi kısıt kritik, nerede |
| **S-6** | Karşıtsal açıklama | "Neden bu rota, şu değil?" — kullanıcının önerdiği alternatifi maliyetleyip farkı ayrıştırır |
| **S-7** | Duyarlılık sorgusu | "X parametresini şu kadar değiştirirsem ne olur?" — perturbe et, yeniden koş, delta raporla |
| **S-8** | Fizibilitesizlik açıklaması | "Neden rota bulunamadı?" — hangi kısıt kapattı, hangi gevşetme açar |
| **S-9** | Hedef odaklı öneri *(faz 2)* | "Enerjiyi %10 iyileştirmek istiyorum" — ulaşılabilir mi, hangi bedelle |
| **S-10** | Kaynak gösterme | Ürettiği her sayı için hangi analizden ve hangi veri katmanından geldiğini söyler |
| **S-11** | Belirsizlik beyanı | Sentetik/modellenmiş veriye dayanan sonuçları bu etiketle sunar |
| **S-12** | Yetenek dışı beyanı | Cevaplayamadığı soruyu **açıkça reddeder**, uydurmaz |

---

## 3. KAPSAM DIŞI — Asistan ne YAPMAZ

Bu bölüm §2'den **daha önemlidir.** System prompt yazılırken yasak listesi, izin listesinden daha belirleyicidir.

### 3.1 Hesaplama yasakları

| # | Yasak | Gerekçe |
|---|---|---|
| **N-1** | **Asistan hiçbir sayıyı kendisi hesaplamaz.** Toplama, yüzde, birim çevirme dahil | Tek sayı kaynağı deterministik çekirdektir. Bir kez "kendi kendine %" hesaplarsa doğrulama zinciri kopar |
| **N-2** | Asistan yanıtında, aldığı analiz çıktısında bulunmayan hiçbir sayı geçemez | §8.3 sayı-eşleme kontrolünün önkoşulu |
| **N-3** | Asistan rota **üretmez**, waypoint önermez, koordinat uydurmaz | `BELGE 04` §7.3: LLM ile rota üretimi reddedilmiştir |
| **N-4** | Asistan maliyet fonksiyonunu, ağırlıkları veya fizik modelini **değiştirmez** | Matematik dondurulmuştur (`BELGE 00`). Asistan yalnızca *sorgular* |
| **N-5** | Asistan veri katmanı üretmez, doldurmaz, tahmin etmez | Eksik veri → `E-NODATA`, tahmin değil |

### 3.2 İddia yasakları

`BELGE 09` §2.3'teki iddia denetimi asistan çıktısına **birebir** uygulanır. Asistan şu cümleleri **hiçbir seviyede kuramaz**:

| # | Yasak ifade | Doğru ifade |
|---|---|---|
| **N-6** | "Otonom navigasyon" / "engel kaçınma yapıyoruz" | "Global rota planlama; yerel engel kaçınma kapsam dışı" |
| **N-7** | "Gerçek NASA verisiyle çalışıyoruz" *(termal/gölge sentetikken)* | Katmanın provenance etiketini olduğu gibi söyler |
| **N-8** | "Bu rota güvenlidir" / "bu rota rover'ı korur" | "Bu rota, tanımlı kısıtları ihlal etmiyor" |
| **N-9** | "Bu alanda ilk/özgün" | Karşılaştırmalı iddia kurmaz |
| **N-10** | "Rover üzerinde çalışabilir" | Sınır B-1 |
| **N-11** | Kesinlik ifadeleri: "kesinlikle", "garanti", "%100" | Belirsizlik bandı varsa birlikte verilir |

### 3.3 Davranış yasakları

| # | Yasak |
|---|---|
| **N-12** | Asistan kullanıcıyı bir rotaya **ikna etmeye çalışmaz**. Trade-off'ları sunar, seçimi kullanıcıya bırakır |
| **N-13** | Seviye ayarı **sonucu değiştirmez** — yalnızca anlatımı değiştirir (§7.2) |
| **N-14** | Asistan güvenlik uyarılarını, kısıt ihlallerini veya belirsizlik beyanlarını hiçbir seviyede **atlamaz veya yumuşatmaz** |
| **N-15** | Asistan fiziksel gerçekliği (arazi, sıcaklık, DEM) "değiştirilebilir parametre" gibi sunmaz. Öneri yalnızca **eyleme geçirilebilir** değişkenler üzerinden verilir (`AI-01` §3.6) |
| **N-16** | Asistan kısıt gevşetmeyi **tavsiye etmez**; yalnızca *sonucunu gösterir*. "Eğim limitini 30°'ye çıkar" ≠ "eğim limiti 30° olsaydı yol açılırdı" |
| **N-17** | Asistan LunaPath dışı konularda (genel Ay bilimi trivia, kod yazma, ödev) yardım etmez → `E-SCOPE` |

### 3.4 Bilinçli olarak faz-1 dışı bırakılanlar

Bunlar "yapılamaz" değil, "şimdi yapılmayacak". Belgede kayıtlı olmaları kapsam kaymasını önler.

| Konu | Neden ertelendi |
|---|---|
| S-9 hedef odaklı öneri (recourse) | En yüksek zorluk; ağırlık uzayında arama gerekir. Onsuz özellik ayakta durur |
| Çok turlu plan düzenleme (asistan üzerinden senaryo kurma) | Yazma yetkisi genişledikçe safeguard yükü artar |
| Sesli arayüz | Değer/emek oranı düşük |
| Oturumlar arası hafıza | Gizlilik ve determinizm sorusu doğurur; demo için gereksiz |
| Türkçe dışı dil desteği | Faz 2; system prompt çoğullanır |
| Kullanıcı geri bildiriminden ağırlık öğrenme | `BELGE 04` §7.3: operatör tercih verisi yok, "yapmayın" |

---

## 4. Yetenek kataloğu

Her yetenek için: hangi soruya cevap verir, ne alır, ne döner, hangi backend hesabına muhtaç.

| Kod | Yetenek | Örnek kullanıcı sorusu | Backend'den ihtiyaç | Faz |
|---|---|---|---|---|
| `C-SUMMARY` | Sonuç özeti | "Bu sonucu bana anlat" | Mevcut plan sonucu | 1 |
| `C-DECOMPOSE` | Maliyet ayrıştırma | "Maliyetin çoğu neden geldi?" | Bileşen bazlı maliyet katkıları | 1 |
| `C-POINT` | Nokta sorgusu | "300. metrede ne oldu?" | Konuma özgü katman değerleri | 1 |
| `C-BINDING` | Bağlayıcı kısıt | "Bu rotayı ne kısıtladı?" | Kısıt yakınlık/slack değerleri | 1 |
| `C-CONTRAST` | Karşıtsal | "Neden düz gitmedi?" | Alternatif yolun maliyetlenmesi | 1 |
| `C-SENSITIVITY` | Duyarlılık | "Enerji ağırlığını artırsam?" | Perturbe edilmiş yeniden koşum | 1 |
| `C-INFEASIBLE` | Fizibilitesizlik | "Neden yol bulamadı?" | Kısıt bazlı başarısızlık analizi | 1 |
| `C-COMPARE` | Profil/rover kıyası | "VIPER ile farkı ne?" | Çoklu koşum karşılaştırması | 1 |
| `C-RECOURSE` | Hedef odaklı öneri | "Enerjiyi %10 azalt" | Parametre uzayında arama | **2** |

**Kural:** Bu tablodaki hiçbir kod, backend'de karşılığı olduğu **doğrulanmadan** system prompt'a girmez. Doğrulama mekanizması `getCapabilities()`.

---

## 5. Veri sözleşmesi (backend-bağımsız)

### 5.1 Ortak tipler

Tüm yetenekler bu tipleri paylaşır. Backend'in iç temsili ne olursa olsun, **adaptör çıktıyı bu tiplere çevirmekle yükümlüdür.**

```ts
/** Birimi zorunlu büyüklük. Birimsiz sayı sözleşme ihlalidir. */
type Quantity = {
  value: number;
  unit: string;          // "Wh" | "m" | "h" | "deg" | "C" | "pct" | "s" | "dimensionless"
  precision?: number;    // gösterimde kullanılacak ondalık basamak
};

/** Bir sayının nereden geldiği. AI katmanı bunu ASLA uydurmaz. */
type Provenance = {
  source: "MEASURED" | "DERIVED" | "MODEL" | "SYNTHETIC";
  layer?: string;        // ör. "elevation", "thermal"
  dataset?: string;      // ör. "LDEM_80S_80MPP_ADJ"
  version?: string;
  note?: string;         // ör. "elevasyon proxy'sinden türetildi"
};

type Metric = {
  key: string;           // makine adı, ör. "total_energy_wh"
  label: string;         // insan adı, ör. "Toplam enerji tüketimi"
  quantity: Quantity;
  provenance: Provenance;
  uncertainty?: { lower: number; upper: number; basis: string };
};

/** Asistanın kullanmasına izin verilen TÜM sayıların düz listesi.
 *  §8.3 sayı-eşleme kontrolü bu listeye bakar. */
type NumericRegistry = Metric[];

type Warning = {
  code: string;          // ör. "SYNTHETIC_LAYER", "NEAR_CONSTRAINT"
  severity: "info" | "caution" | "critical";
  message: string;
  suppressible: false;   // N-14: hiçbir seviyede gizlenemez
};

/** Her yanıtın zarfı. */
type AnalysisEnvelope<T> = {
  capability: string;            // "C-DECOMPOSE" vb.
  request_echo: object;          // ne sorulduğunun kaydı
  ok: boolean;
  payload?: T;
  error?: ErrorInfo;
  numeric_registry: NumericRegistry;
  warnings: Warning[];
  provenance_summary: Provenance[];
  compute_ms: number;
  backend_version: string;       // adaptörün bildirdiği sürüm etiketi
};
```

### 5.2 `AnalysisProvider` portu

AI katmanının backend hakkında bildiği **tek şey** budur.

```ts
interface AnalysisProvider {
  /** Backend'in o an desteklediği yetenekler. Asistan başlangıçta bir kez çağırır. */
  getCapabilities(): Promise<CapabilityDescriptor[]>;

  /** Üzerinde konuşulacak analiz bağlamını getirir. */
  getContext(contextId: string): Promise<AnalysisContext>;

  /** Tek giriş noktası. Yetenek kodu + parametre → zarflı sonuç. */
  invoke(
    capability: string,
    params: object,
    budget: ComputeBudget
  ): Promise<AnalysisEnvelope<unknown>>;
}

type CapabilityDescriptor = {
  code: string;                 // "C-SENSITIVITY"
  available: boolean;
  params_schema: object;        // JSON Schema — safeguard bunu kullanır
  writes: boolean;              // yeni hesap tetikliyor mu?
  typical_ms: number;           // bütçe planlaması için
  notes?: string;
};

type ComputeBudget = {
  max_reruns: number;           // varsayılan 3 (§8.2)
  max_ms: number;
};
```

**Tasarım gerekçesi:** `invoke()` tek giriş noktası olduğu için safeguard tek yerde uygulanır; yeni yetenek eklemek AI katmanında kod değişikliği gerektirmez, yalnızca `getCapabilities()` çıktısı büyür.

### 5.3 `AnalysisContext` — konuşmanın konusu

```ts
type AnalysisContext = {
  context_id: string;
  kind: "plan" | "comparison" | "failed_plan";

  /** Kullanıcının seçtiği girdiler — asistan bunları DEĞİŞTİREMEZ, sadece okur. */
  inputs: {
    start: PointRef;
    goal: PointRef;
    vehicle: { id: string; label: string };
    profile: { id: string; label: string };
    weights: Record<string, number>;      // anahtar adları backend'e bırakıldı
    constraints: Record<string, Quantity>;
    region: { label: string; resolution_m: number; extent_px: [number, number] };
  };

  /** Sonuç metrikleri. */
  metrics: Metric[];

  /** Yol geometrisi — asistan bunu OKUR, üretmez (N-3). */
  path?: { node_count: number; available: boolean };

  status: "success" | "infeasible" | "partial";
  warnings: Warning[];
};

type PointRef = {
  kind: "pixel" | "geo";
  a: number;    // row | lat
  b: number;    // col | lon
  label?: string;
};
```

**Not:** `weights` ve `constraints` bilinçli olarak `Record<string, ...>` — anahtar isimleri backend'e bırakıldı. Asistan anahtar adını *ezberlemez*, `CapabilityDescriptor.params_schema` içinden okur. Backend `w_energy`'yi `weight_energy` yaparsa AI katmanı etkilenmez.

### 5.4 Yetenek bazlı girdi/çıktı

Aşağıda her yetenek için **anlamsal** sözleşme verilmiştir. Alan adları önerilerdir; bağlayıcı olan yapıdır.

#### `C-DECOMPOSE` — maliyet ayrıştırma

```ts
// Girdi
{ context_id: string; granularity: "total" | "per_segment"; }

// Çıktı payload
{
  total: Quantity;
  components: Array<{
    key: string;              // "slope" | "energy" | "shadow" | "thermal" | "barrier"
    label: string;
    weight: number;           // uygulanmış ağırlık
    raw_contribution: Quantity;
    weighted_contribution: Quantity;
    share_pct: Quantity;      // toplam maliyetteki payı
    provenance: Provenance;
  }>;
  dominant_component: string;
  segments?: Array<{ from_idx: number; to_idx: number; components: ... }>;
}
```

**Asistanın bu çıktıyla kurabileceği cümle (L2):**
> *"Maliyetin %52'si eğim cezasından, %23'ü termal cezadan geldi. Enerji terimi toplamın yalnızca %9'u — bu beklenen davranış, çünkü tek adımın enerji maliyeti batarya kapasitesine göre çok küçük."*

#### `C-BINDING` — bağlayıcı kısıt

```ts
// Girdi
{ context_id: string; }

// Çıktı payload
{
  constraints: Array<{
    key: string;                    // "slope" | "lateral_slope" | "soc" | "temp_low" | "temp_high"
    label: string;
    limit: Quantity;
    worst_observed: Quantity;
    margin: Quantity;               // limit - gözlenen
    margin_pct: Quantity;
    location?: PointRef;            // en kritik nokta
    status: "binding" | "near" | "comfortable";
  }>;
  most_binding: string;
}
```

**Kritik tasarım kararı:** `status` eşikleri **backend'de** tanımlanır, asistanda değil. Asistan "near" ile "binding" arasındaki farkı kendi kararıyla belirlemez (N-1).

#### `C-CONTRAST` — karşıtsal açıklama

```ts
// Girdi
{
  context_id: string;
  foil: {
    kind: "user_path" | "profile" | "vehicle" | "straight_line" | "shortest_distance";
    path?: PointRef[];              // kind === "user_path" ise
    profile_id?: string;
    vehicle_id?: string;
  };
}

// Çıktı payload
{
  reference: { label: string; metrics: Metric[] };
  foil: {
    label: string;
    feasible: boolean;
    metrics?: Metric[];
    violated_constraints?: Array<{ key: string; at: PointRef; observed: Quantity; limit: Quantity }>;
  };
  deltas: Array<{ key: string; label: string; delta: Quantity; direction: "better" | "worse" | "neutral" }>;
  verdict: "foil_infeasible" | "foil_dominated" | "foil_tradeoff";
  divergence_points?: PointRef[];   // iki rotanın ayrıldığı yerler
}
```

`verdict` üç hâli ayırır ve bu ayrım anlatı için kritik:
- `foil_infeasible` — alternatif bir kısıtı ihlal ediyor → *"o yol 27.4° eğim içeriyor, limit 25°"*
- `foil_dominated` — alternatif her kriterde kötü → *"o yol hem daha uzun hem daha çok enerji harcıyor"*
- `foil_tradeoff` — gerçek bir ödünleşim var → *"o yol 400 m kısa ama 3.1 saat fazla gölge"*

#### `C-SENSITIVITY` — duyarlılık

```ts
// Girdi
{
  context_id: string;
  perturbations: Array<{
    target: "weight" | "constraint";
    key: string;                    // params_schema'dan doğrulanır
    mode: "absolute" | "relative";
    value: number;
  }>;
  compare_to_baseline: true;
}

// Çıktı payload
{
  baseline: { metrics: Metric[] };
  perturbed: { applied: object; metrics: Metric[]; feasible: boolean };
  deltas: Array<{ key: string; label: string; delta: Quantity; delta_pct: Quantity }>;
  path_changed: boolean;
  path_overlap_pct?: Quantity;      // rota ne kadar aynı kaldı
  validity_note: string;            // "tek nokta perturbasyonu; aralık geçerliliği test edilmedi"
}
```

**`validity_note` zorunludur** ve asistan bunu **atlayamaz**. Gerekçe (`AI-01` §3.4): klasik duyarlılık analizinde gölge fiyat yorumu yalnızca belirli bir aralık içinde geçerlidir; A* kombinatoryal olduğu için LunaPath'te bu garanti daha da zayıftır. Asistan "%X artırırsan tam olarak %Y olur" **diyemez**; "bu tek koşumda %Y çıktı" der.

#### `C-INFEASIBLE` — fizibilitesizlik

```ts
// Girdi
{ context_id: string; }   // status === "infeasible" olan bağlam

// Çıktı payload
{
  reason: "no_traversable_corridor" | "budget_exhausted" | "start_blocked" | "goal_blocked" | "unknown";
  blocking_constraints: Array<{
    key: string;
    limit: Quantity;
    bottleneck: { location: PointRef; observed: Quantity };
  }>;
  relaxation_analysis?: Array<{
    constraint_key: string;
    required_value: Quantity;         // bu değere gevşetilirse yol açılır
    delta_from_current: Quantity;
    consequence_note: string;         // "bu değer LPR-1 devrilme limitinin üzerindedir"
  }>;
  alternative_goals?: Array<{ point: PointRef; distance_from_original: Quantity }>;
}
```

**N-16 hatırlatması:** `relaxation_analysis` bir *tavsiye* değil, bir *hesap*tır. Asistan bunu sunarken `consequence_note` alanını **zorunlu olarak** birlikte verir.

---

## 6. Katman mimarisi ve sorumluluk sınırları

| Katman | Ne yapar | Ne YAPAMAZ | LLM? |
|---|---|---|---|
| **K1 — Analiz çekirdeği** | Tüm hesaplar; tüm sayıların tek kaynağı | Metin üretmek, seviye bilmek | ❌ |
| **K2 — Yönlendirici** | Serbest metni yetenek kodu + parametreye çevirir | Sayı üretmek, cevap yazmak | ✅ |
| **K3 — Safeguard** | Şema, aralık, bütçe, izin listesi denetimi | Yorum yapmak | ❌ |
| **K4 — Sözelleştirici** | K1 zarfını seviyeye göre anlatır | Hesap yapmak, kayıt dışı sayı kullanmak | ✅ |
| **K5 — Çıkış denetimi** | Sayı-eşleme + yasak ifade taraması | Metni "düzeltmek" | ❌ |

**K2 çıktı kısıtı:** K2 asla serbest metin üretmez. Çıktısı yalnızca şu biçimdedir:

```ts
type RouterOutput =
  | { action: "invoke"; capability: string; params: object; rationale_key: string }
  | { action: "clarify"; missing: string[] }
  | { action: "refuse"; code: ErrorCode }
  | { action: "answer_from_context" };   // ek hesap gerekmiyorsa
```

**K5 davranışı:** İhlal bulursa metni düzenlemez — **bloklar** ve kullanıcıya ham analiz özetini gösterir. Sessiz düzeltme, hatanın görünmez hâle gelmesi demektir.

---

## 7. Seviye modeli

### 7.1 Seviye tespiti

**Yöntem:** Açık seçim. Oturum başında tek soru, üç seçenek. Davranıştan gizli çıkarım **yapılmaz** (`AI-01` §3.7 gerekçesi: yanlış sınıflandırma riski, kullanıcı kontrolü, jüriye anlatılabilirlik).

| Seviye | Kullanıcı tanımı | Varsayılan |
|---|---|---|
| **L1** | "Konuya yeniyim, genel hatlarıyla anlamak istiyorum" | — |
| **L2** | "Mühendislik geçmişim var, sayıları ve gerekçeleri görmek istiyorum" | ✅ varsayılan |
| **L3** | "Alan uzmanıyım, ham veri ve formül istiyorum" | — |

Her yanıtın altında **"daha teknik / daha basit anlat"** düğmeleri; seviye oturum boyunca kalıcı, istendiğinde anında değişir.

### 7.2 Seviye neyi değiştirir, neyi değiştirmez

| Değişir | **Değişmez (N-13, N-14)** |
|---|---|
| Terminoloji derinliği | Sayısal sonuçlar |
| Yanıt uzunluğu ve katman sayısı | Hangi rotanın/sonucun raporlandığı |
| Formülün gösterilip gösterilmediği | Kısıt ihlali uyarıları |
| Analoji ve örnek kullanımı | Belirsizlik ve provenance beyanları |
| Ham JSON'a erişim | `validity_note` gibi zorunlu notlar |

### 7.3 Seviye bazlı çıktı şablonu

| | **L1** | **L2** | **L3** |
|---|---|---|---|
| Uzunluk | 3–4 cümle | 1 paragraf + tablo | Kısa + veri yoğun |
| Metrik sayısı | En fazla 3 | Tam ayrışım | Tam ayrışım + ham kayıt |
| Birim | Günlük ("yaklaşık bir saatlik sürüş") | Zorunlu SI/mühendislik birimi | Zorunlu + hassasiyet |
| Formül | Yok | Talep üzerine | Varsayılan görünür |
| Provenance | "Bu bir model tahmini" | Kaynak katman adı | Tam `Provenance` nesnesi |
| Belirsizlik | Nitel | Nicel band | Band + dayanak |

---

## 8. Safeguard ve red kuralları

### 8.1 Hata kodları

| Kod | Anlamı | Kullanıcıya söylenen |
|---|---|---|
| `E-SCOPE` | Soru LunaPath kapsamı dışında | "Bu konuda yardımcı olamam; ben yalnızca bu analizle ilgili soruları cevaplıyorum" |
| `E-UNSUPPORTED` | Yetenek `getCapabilities()` içinde yok/kapalı | "Bu hesap sistemde şu an açık değil. Bunun yerine şunu yapabilirim: …" |
| `E-SCHEMA` | Parametre `params_schema`'ya uymuyor | "İsteğini anladım ama parametreyi çıkaramadım — şunu netleştirir misin?" |
| `E-RANGE` | Parametre izinli aralık dışında | "Bu değer sistemin kabul ettiği aralığın dışında (izinli aralık: …)" |
| `E-BUDGET` | Hesap bütçesi aşıldı | "Bu soru birden fazla yeniden hesaplama gerektiriyor; parçalara bölelim mi?" |
| `E-NODATA` | Gerekli veri katmanı yok | "Bu bilgi mevcut veri setinde yok" |
| `E-CONTEXT` | Analiz bağlamı yok/geçersiz | "Önce bir analiz çalıştırman gerekiyor" |
| `E-GROUNDING` | K5 çıkış denetimi başarısız | "Yanıtı doğrulayamadım; ham sonucu gösteriyorum" + zarf özeti |

**Kural:** Her red **gerekçeli** olur. "Yapamam" tek başına yetersizdir; hangi kod, hangi alternatif — ikisi de verilir.

### 8.2 Bütçe

| Sınır | Varsayılan | Gerekçe |
|---|---|---|
| Tek kullanıcı sorusu başına yeniden hesaplama | **3** | Kullanıcı "tüm ağırlıkları tara" derse sistem kilitlenmesin |
| Tek soru toplam hesap süresi | 15 s | Demo akıcılığı |
| Oturum başına toplam yeniden hesaplama | 50 | Kaynak koruması |
| K2 yönlendirici deneme sayısı | 2 | Şema tutmazsa `E-SCHEMA` |

### 8.3 Çıkış denetimi (K5)

Bu, `BELGE 04` §7.3'ün hallucination endişesine verilen **somut** cevaptır.

1. Asistan yanıtındaki tüm sayılar regex ile çıkarılır.
2. Her sayı, `numeric_registry` içindeki bir `Quantity.value` ile **tolerans dahilinde** eşleşmeli.
   - Tolerans: gösterim yuvarlaması kadar (`precision`), fazlası değil.
   - Türetilmiş sayı (yüzde, oran) yasak (N-1) → kayıtta yoksa ihlal.
3. Sıra sayıları, tarih ve yetenek kodları beyaz listede.
4. §3.2'deki yasak ifadeler için kelime/kalıp taraması.
5. İhlal → `E-GROUNDING`, yanıt bloklanır, ham zarf özeti gösterilir.

**Neden bu yöntem, NLI tabanlı dayanak kontrolünden iyi:** Literatürdeki dayanak doğrulayıcıları zamansal ifadeler, olumsuzlama ve niceleyicilerde zorlanır (`AI-01` §3.9). Sayı-eşleme bu üç zayıflığın hiçbirinden etkilenmez, deterministiktir ve maliyeti sıfıra yakındır. Sembolik guardrail, sinirsel guardrail'den daha güçlü garanti verir.

---

## 9. Backend teyit listesi

**Bu bölüm bilinçli olarak boştur.** Backend dondurulduğunda doldurulacak; system prompt bundan **önce yazılmayacak.**

| # | Teyit edilecek | Durum | Notlar |
|---|---|---|---|
| T-1 | Hangi yetenekler (`C-*`) backend'de gerçekten var? | ⬜ | `getCapabilities()` çıktısıyla doğrulanır |
| T-2 | Maliyet bileşenlerinin anahtar adları ve sayısı | ⬜ | `w_slope` vb. hâlâ geçerli mi? |
| T-3 | Ağırlık izinli aralığı | ⬜ | Eski değer `[0, 2]` — teyit gerekli |
| T-4 | Kısıt anahtarları ve limit değerleri | ⬜ | Eğim 25°, SoC min, gölge H_max |
| T-5 | Rover/profil katalog kimlikleri | ⬜ | `BELGE 00`: 4 rover · değişmiş olabilir |
| T-6 | Koordinat girdi biçimi (piksel/geo) | ⬜ | |
| T-7 | Provenance/`physical_validity` alanı var mı? | ⬜ | Yoksa S-11 kısıtlanır |
| T-8 | Kısıt slack değerleri dışa açılıyor mu? | ⬜ | `C-BINDING`'in önkoşulu |
| T-9 | Rota metrik anahtarları ve birimleri | ⬜ | |
| T-10 | Tipik yeniden hesaplama süresi | ⬜ | Bütçe ayarı için |
| T-11 | Fizibilitesizlik durumunda dönen bilgi | ⬜ | `C-INFEASIBLE` bundan besleniyor |
| T-12 | Sürüm etiketi mekanizması | ⬜ | `backend_version` alanı |

**Sıralama:** T-1 → T-2 → T-8 → T-11 en kritik dördü. Bunlar netleşmeden K2 yönlendiricisi tasarlanamaz.

---

## 10. Kabul kriterleri

### 10.1 İşlevsel

- [ ] **A-1** Asistan, backend'de olmayan bir yetenek istendiğinde `E-UNSUPPORTED` döner ve **alternatif önerir** — hata fırlatmaz *(S-12, §0.2)*
- [ ] **A-2** Yanıtlardaki her sayı `numeric_registry`'de bulunur; sentetik ihlal testi yanıtı bloklar *(N-1, N-2, §8.3)*
- [ ] **A-3** Aynı soru L1/L2/L3'te sorulduğunda **sayısal sonuçlar birebir aynıdır**, yalnızca anlatım değişir *(N-13)*
- [ ] **A-4** Kısıt ihlali uyarısı üç seviyede de görünür *(N-14)*
- [ ] **A-5** §3.2'deki 6 yasak ifade için negatif test seti yazılmış ve geçiyor
- [ ] **A-6** Kapsam dışı 10 soruluk test setinde `E-SCOPE` doğruluğu ≥ %90
- [ ] **A-7** AI katmanı tamamen devre dışıyken uygulama tam işlevsel *(B-3)*
- [ ] **A-8** Adaptör dışındaki hiçbir AI dosyasında backend endpoint adı veya sayısal sabit geçmiyor — statik tarama ile doğrulanır *(§0.1)*

### 10.2 Test seti (yazılacak)

| Set | İçerik | Adet |
|---|---|---|
| **TS-1** | Yetenek yönlendirme: soru → beklenen `capability` | ≥ 40 |
| **TS-2** | Kapsam dışı sorular → `E-SCOPE` | ≥ 15 |
| **TS-3** | Sayı uydurma tuzakları (kayıtta olmayan hesap istenmesi) | ≥ 10 |
| **TS-4** | Yasak iddia tuzakları ("bu rota güvenli mi?", "otonom mu?") | ≥ 10 |
| **TS-5** | Seviye tutarlılığı: aynı soru × 3 seviye, sayı karşılaştırması | ≥ 10 |
| **TS-6** | Bütçe/aralık ihlalleri → doğru hata kodu | ≥ 10 |
| **TS-7** | Yetenek yokluğu simülasyonu (`available: false`) | ≥ 5 |

**Not:** OptiGuide makalesinin de bir değerlendirme benchmark'ı geliştirdiğini hatırlayın (`AI-01` §3.4) — bu test setleri aynı işlevi görür ve raporda "değerlendirme protokolü" olarak sunulabilir.

---

## 11. Faz planı

| Faz | Kapsam | Önkoşul |
|---|---|---|
| **F-0** | §9 teyit listesi doldurulur; adaptör yazılır; `getCapabilities()` çalışır | Backend dondurulur |
| **F-1** | K1 yetenekleri: `C-SUMMARY`, `C-DECOMPOSE`, `C-POINT`, `C-BINDING` — **LLM olmadan**, panel olarak | F-0 |
| **F-2** | K2+K3+K4+K5 kurulur; F-1 yetenekleri sohbetten erişilebilir; seviye modeli | F-1 |
| **F-3** | `C-CONTRAST`, `C-SENSITIVITY`, `C-INFEASIBLE`, `C-COMPARE` | F-2 |
| **F-4** *(ops.)* | `C-RECOURSE` (S-9) | F-3 |

**Kritik sıralama kuralı:** F-1 bitmeden F-2'ye geçilmez. Sohbet katmanı, açıklama çekirdeğinin arayüzüdür; çekirdek yokken sohbet, anlatacak şeyi olmayan bir anlatıcı olur (`AI-01` §4).

---

## 12. Açık kararlar

Bu belgede **varsayılan** olarak yazıldı; ekip onayı gerekiyor.

| # | Karar | Belgedeki varsayılan | Değiştirilirse etkisi |
|---|---|---|---|
| D-1 | Asistan yeni hesap tetikleyebilir mi? | ✅ Evet, 3 koşum bütçesiyle | Hayır ise `C-SENSITIVITY`/`C-CONTRAST` düşer, kapsam yarıya iner |
| D-2 | `C-RECOURSE` faz-1'de mi? | ❌ Hayır, F-4 opsiyonel | Evet ise F-3 süresi ~2 katına çıkar |
| D-3 | Seviye tespiti | Açık seçim, 3 kademe | Gizli çıkarım: yanlış sınıflandırma riski + savunma yükü |
| D-4 | LLM konumu | Bulut API; K1 LLM'siz çalışır | Yerel model: kurulum yükü, demo makinesi kısıtı |
| D-5 | Dil | Yalnızca Türkçe (faz 1) | Çok dil: system prompt ve test seti çoğullanır |
| D-6 | Oturum hafızası | Yok (tek oturum) | Var ise gizlilik + determinizm sorusu |

---

## 13. İzlenebilirlik

| Bu belgedeki madde | Dayanak |
|---|---|
| N-1, N-2, N-3, §8.3 | `BELGE 04` §7.3 (LLM ile açıklama üretme yasağı — daraltılmış hâliyle) |
| B-1, B-2 | `BELGE 04` §8, `BELGE 08` §4, `BELGE 09` §3 |
| N-6…N-11 | `BELGE 09` §2.3 iddia denetimi |
| S-3, S-4, C-DECOMPOSE, C-POINT | `BELGE 04` §5.1 `CostMap.explain()` |
| S-5, S-8, C-BINDING, C-INFEASIBLE | `AI-01` §3.3 (JPL Crosscheck) |
| S-6, C-CONTRAST | `AI-01` §3.1, §3.2 (XAIP karşıtsal açıklama) |
| S-7, C-SENSITIVITY | `AI-01` §3.4, §3.5 |
| S-9, C-RECOURSE | `AI-01` §3.6 (recourse), §3.5 (R-XIMO) |
| §6 katman mimarisi | `AI-01` §3.4 (OptiGuide deseni) |
| §7 seviye modeli | `AI-01` §3.7 (ProfileXAI, ExPerT) |
| §8 safeguard | `AI-01` §3.9 |
| §0.2 yetenek keşfi | `AI-01` §3.9 cevaplanabilirlik kapısı |
