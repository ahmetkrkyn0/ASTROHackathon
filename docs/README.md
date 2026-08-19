# LunaPath — Doküman Dizini

Bu klasör iki bölüme ayrılmıştır:

| Klasör | Kapsam |
|--------|--------|
| [`final/`](final/) | **Final versiyonun bağlamı.** TUA Astro Hackathon Ulusal Final (7–13 Eylül 2026) hazırlığı için üretilen araştırma ve mühendislik karar belgeleri. Hedeflenen sistemi tanımlar. |
| [`archive/`](archive/) | **Önceki versiyonun dokümanları.** Depodaki mevcut kodun yazıldığı dönemin referans belgeleri, çalışma planı ve ekip raporları. |

Ayrımın nedeni: `final/` altındaki belgeler ileriye dönüktür ve büyük ölçüde **henüz uygulanmamış** kararları içerir (zaman ekseni, ufuk-maskesi aydınlanma modeli, Diviner termal verisi, SPICE efemeris). `archive/` altındaki belgeler ise bugün depoda çalışan kodu tanımlar.

---

## final/ — final versiyon bağlamı

Aşağıdaki sıra, okuma sırasıdır. İlk dördü baştan sona okunmak üzere yazılmıştır; beşincisi bir başvuru kütüphanesidir.

| # | Belge | Tarih | İçerik |
|---|-------|-------|--------|
| 1 | [domain-research-and-decision-record.md](final/domain-research-and-decision-record.md) | 13 Ağu 2026 | Domain araştırması ve karar kaydı. Gerçek görev operasyonları (VIPER, Yutu-2, Perseverance), kapsam sınırları, kritiklik etiketli (`[K]`/`[O]`/`[B]`) bulgu tablosu. |
| 2 | [literature-review-and-methodological-assessment.md](final/literature-review-and-methodological-assessment.md) | — | Kapsamlı literatür taraması ve metodolojik değerlendirme. CMU TEMPEST/ISE soyağacı, terramekanik, AHP eleştirileri, kaynak künyeleriyle. |
| 3 | [literature-constraint-comparison.md](final/literature-constraint-comparison.md) | 12 Ağu 2026 | LunaPath'in sayısal kısıtlarının (eğim limiti, çözünürlük, enerji modeli, aydınlanma kaynağı) literatürdeki çalışmalarla satır satır karşılaştırması. |
| 4 | [frontend-and-simulation-decision-report.md](final/frontend-and-simulation-decision-report.md) | 13 Ağu 2026 | Frontend, görselleştirme ve simülasyon özellikleri için mühendislik karar raporu. Ekibin 5 özellik fikri için "gerçek / kısmen gerçek / mock" kararı ve yapılabilirlik analizi. |
| 5 | [backend-research-library.md](final/backend-research-library.md) | 10 Ağu 2026 | Backend araştırma kütüphanesi — 11 belgenin (BELGE 00–10) tek dosyada birleştirilmiş hâli. **Baştan sona okunmak için değil, sorgulanmak için yazılmıştır:** dosya içi "SORU → BELGE" yönlendirme tablosu ve terim indeksi ile ilgili bölüme gidilir. Referans kod tabanı: `main` @ `3e22809`. |

Belge 2 için dosyada açık bir tarih belirtilmemiştir.

Bu belgelerin ortak kuralı: **"bugün LunaPath'te var olan" ile "önerilen" ayrımı korunur.** Bir bulguyu aktarırken bu ayrımı bozmayın — belgeler mevcut kodu değiştirmez, dördü de (a) bugün ne var, (b) literatür ne yapıyor, (c) boşluk, (d) kapatma reçetesi yapısındadır.

---

## archive/ — önceki versiyonun dokümanları

| Belge | İçerik |
|-------|--------|
| [lunapath_referans_belgesi_2.md](archive/lunapath_referans_belgesi_2.md) | Formüller, sabitler, maliyet modeli ve görev profili tanımları. |
| [ay_termal_navigasyon_proje_dokumani.md](archive/ay_termal_navigasyon_proje_dokumani.md) | Proje dokümanı: modül yapısı, riskler, hedefler. |
| [lunar_data_thermal_team_docs.md](archive/lunar_data_thermal_team_docs.md) | Veri ve termal ekip notları. |
| [stitch_design_brief.md](archive/stitch_design_brief.md) | Arayüz tasarım notları. |
| [lunar_report_markdown/lunar_data_preprocessing_report.md](archive/lunar_report_markdown/lunar_data_preprocessing_report.md) | Veri ön işleme raporu (görsellerle). |
| `lunar_data_preprocessing_report.pdf` | Yukarıdaki raporun PDF sürümü. |
| `lunapath_calisma_plani.pdf` | Çalışma planı. |
| `2_kisi_teknik_rol_raporu.pdf` | Teknik rol raporu. |

**Önemli:** `archive/` "geçersiz" anlamına gelmez. Depodaki mevcut kod hâlâ `lunapath_referans_belgesi_2.md` içindeki formülleri uygular — `backend/app/cost_engine.py` ve `backend/app/scenarios.py` doğrudan bu belgeye atıf verir. Kodun bugünkü davranışını anlamak için başvurulacak belge budur; final versiyonda neyin değişmesi planlandığını anlamak için `final/` klasörü okunur.
