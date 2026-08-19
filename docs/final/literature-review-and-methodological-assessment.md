# Ay Yüzeyi Rover Görev Planlama ve Traverse Analizi — Kapsamlı Literatür Taraması (LunaPath / FEZA Ekibi İçin)
 
## TL;DR
- Literatür, LunaPath'in temel mimarisini (grid tabanlı, çok kriterli, kaynak-kısıtlı traverse planlama) doğruluyor; ancak "en yakın akraba" olan CMU TEMPEST/ISE soyu ve VIPER operasyon modeli, LunaPath'in gölge ve termal modellerinin vekil (proxy) olduğunu ve **zaman ekseninin planlama uzayına dahil edilmemesinin** en kritik metodolojik zayıflık olduğunu net biçimde gösteriyor.
- **Radyasyon (6.4) sorusuna net cevap: HAYIR** — kısa süreli robotik bir rover için radyasyon anlamlı bir rota kriteri değildir ve literatürde robotik rover rotasını radyasyona göre optimize eden tek bir çalışma bulunamadı; radyasyon bir *bileşen/görev-ömrü elektroniği* problemidir (rad-hard parça + ekranlama), rota problemi değildir. Radyasyonun rotaya girdiği tek bağlam **insanlı** görevlerdir (SPE sığınak yakınlığı/zamanlaması).
- En yüksek getirili düzeltmeler: (1) gölge modelini ufuk-maskesi/ray-tracing temeline oturtmak (Mazarico, Gläser), (2) termal modele zaman sabiti eklemek ve Diviner verisiyle beslemek (Paige/Williams), (3) haberleşme (DTE görünürlüğü) kriterini eklemek, (4) AHP'yi çoklu-uzman + tutarlılık + duyarlılık analiziyle savunmak, (5) NASA-STD-7009 kredibilite ölçeğiyle modelin kısıtlarını şeffaf raporlamak.
---
 
## Key Findings (Yönetici Özeti)
1. **Gerçek görevlerde planlama iki katmanlıdır:** küresel/stratejik (yer döngüsü, orbital DEM üzerinde) + yerel/taktik (onboard tehlike kaçınma). LunaPath küresel katmandır ve doğru bir soyağacına oturur (CMU Hyperion/TEMPEST → VIPER traverse planlama).
2. **Otonomiyi zorunlu kılan asıl faktör sinyal gecikmesi değildir.** Ay için ışık-zamanı ~2.56 s'dir; ancak NASA'nın kendi analizi (NTRS 20170009822) operasyonel komut gecikmesinin haberleşme yükü ve veri hızına bağlı olarak "altı saniyeden kırk saniyeden fazlasına kadar" değişebileceğini belirtir. Otonomiyi asıl zorlayan faktörler operasyon maliyeti, bant genişliği/haberleşme penceresi ve — kutupta — hızlı hareket eden gölgelerdir. Yutu-2 tamamen yer-döngüsü (teleoperasyon) ile sürülmüştür; Perseverance ise ilk Mars yılında 17.7 km'nin **%88'ini** AutoNav ile değerlendirmiştir.
3. **Eğim eşikleri iyi belgelenmiştir:** VIPER ~15° rutin / 25–30° istisnai; Curiosity mekanik olarak 45°'ye kadar dayanacak şekilde tasarlanmıştır ama tehlike-kaçınma yazılımı 30°'yi aşmasını engeller (operasyonel rekoru Sol 2696'da 31° tırmanış). Rocker-bogie pasif süspansiyon standarttır.
4. **Terramekanik olgun bir alandır:** Bekker basınç-batma + Wong-Reece gerilme modeli temeldir; Ishigami, Iagnemma & Dubowsky, Ding (değişken batma üsteli) slip-sinkage'ı modellemiştir. Spirit'in "Troy" batması bu alanın operasyonel önemini kanıtlar.
5. **Termal ve aydınlanma veri ürünleri açık erişimdir:** LOLA DEM (PDS), Diviner sıcaklık ürünleri (PDS 128 ppd), Mazarico/Gläser aydınlanma haritaları. LunaPath'in vekil formüllerini gerçek veriyle değiştirme imkânı vardır.
6. **AHP eleştirileri ciddiye alınmalı** (rank reversal — Belton & Gear, Dyer); bunlar çoklu-uzman toplama (AIJ/AIP), tutarlılık oranı ve duyarlılık analiziyle yönetilir.
---
 
## Details (Başlıklara Göre Kaynak Listesi)
 
### 1. GERÇEK GÖREV OPERASYONLARI (ConOps)
 
**1.1 / 1.2 / 1.3 — Traverse planlama, otonomi, katman ayrımı**
 
- **Verma, V., Maimone, M., Gaines, D., et al. (2023). "Autonomous robotics is driving Perseverance rover's progress on Mars." *Science Robotics*, 8(80), eadi3099.** DOI: 10.1126/scirobotics.adi3099. → Makalenin ifadesiyle "AutoNav ilk Mars yılında kat edilen 17.7 km'nin %88'ini değerlendirmek için kullanıldı"; sol 753 itibarıyla sürüşün %88.7'si otonom planlanmış/haritalanmıştır. İnsansız incelemesiz en uzun sürüş 699.9 m, tek-sol rekoru 347.7 m. Küresel rotayı insan planlar, ince navigasyonu rover yapar — LunaPath'in "küresel planlayıcı" konumunu doğrular. *(Kapalı; PubMed özeti açık: PMID 37494463)*
- **Rankin, A., Maimone, M., Biesiadecki, J., et al. "Enhanced Autonomous Navigation on the Perseverance Mars Rover" (ENav).** → AutoNav/ENav'ın RAD750 işlemcide çalışacak kadar hafif olması gerektiğini, seçim kriterlerinin "traverse yürütme süresi" modeline dayandığını anlatır. LunaPath'in onboard-hafiflik gerekçesini destekler. *(ResearchGate'te PDF)*
- **JPL/NASA (2023). "Autonomous Systems Help NASA's Perseverance Do More Science on Mars."** nasa.gov. → "Snowdrift Peak" taş tarlası vaka çalışması; küresel rotayı planlayıcılar, taş kaçınmayı AutoNav yaptı (520 m planlı → 759 m gerçek). *(Açık)*
- **NASA (NTRS 20170009822). "Key Differences in Operating a Rover on the Moon vs. Mars."** → "Ay varlığı için gidiş-dönüş ışık-zamanı yalnızca birkaç saniyeyle ölçülür, ancak mevcut haberleşme sistemleri gecikmeyi iki katından fazlaya çıkarabilir... toplam komut gecikmesi, haberleşme yükü ve veri hızlarına bağlı olarak altı saniyeden kırk saniyeden fazlasına kadar değişebilir." → Otonomi gerekçesini "salt gecikme" olmaktan çıkarır. *(Açık — NTRS)*
- **Wang, J., Di, K., et al. (2020). "Vision-Based Decision Support for Rover Path Planning in the Chang'e-4 Mission." *Remote Sensing*, 12(4), 624.** DOI: 10.3390/rs12040624. → Yutu-2 her waypoint'te Navcam/Hazcam stereo → 0.02 m DEM → eğim/aspect/roughness/görünürlük maliyet haritası → yol arama; **tamamen teleoperasyon (yer-döngüsü)**. 14. ay-gününde 367.25 m. LunaPath'in maliyet-haritası + grid arama yaklaşımının gerçek görevdeki doğrudan karşılığı. *(Açık — MDPI)*
- **Ding, L., Zhou, R., Yu, T., et al. (2022). "A 2-year locomotive exploration and scientific investigation of the lunar farside by the Yutu-2 rover." *Science Robotics*, 7(62), eabj6660.** DOI: 10.1126/scirobotics.abj6660. → Yutu-2'nin 2 yıllık mobilite verisi, regolit etkileşimi, patinaj yönetimi. *(Kapalı)*
- **Wan, W., Liu, Z., Di, K., et al. (2020). "Computer Vision in the Teleoperation of the Yutu-2 Rover." *ISPRS Annals*, V-3-2020, 595–602.** DOI: 10.5194/isprs-annals-V-3-2020-595-2020. → Teleoperasyon iş akışı; yol projeksiyonu ve uzman onayı süreci. *(Açık — Copernicus, DOAJ)*
**1.4 — Başarısızlıklar ve öğrenilen dersler**
 
- **NASA/JPL (2009). "Spirit Embedded in Soft Soil ('Free Spirit')" ve "NASA to Begin Attempts to Free Sand-Trapped Mars Rover."** nasa.gov / jpl.nasa.gov. → Spirit, "Troy"da (Nisan 2009) kabuğu kırıp altındaki gevşek kuma gömüldü; yer testleri (kil + diatomlu toprak, 10° eğimli kum havuzu) ile kurtarma denendi ama başarısız oldu (yalnız 4 çalışan tekerlekle). LunaPath için terramekanik/patinaj kriterinin görev-kritik olduğunun kanıtı. *(Açık)*
- **Yutu (Chang'e-3) mobilite arızası:** İlk ay-gecesinde mobilitesini kaybetti; ~31 ay hayatta kaldı ama hareket edemedi (night-survival literatüründe belgelenmiş). → Ay gecesi ve mekanik/termal survival kritiktir.
**1.5 — Ay günü/gecesi ve hibernasyon; kutup farkı**
- VIPER Lunar Operations (NASA Science): Güney kutbunda Güneş ufkun ~10° üzerine çıkar; uzun, hızlı hareket eden gölgeler oluşur; rover ~100 günlük görevde ay-gündüz döngüsüne göre planlanır. → Kutupta klasik 14.75 günlük gece yerine, arazi-kaynaklı hızlı gölge dinamiği baskındır (bkz. Bölüm 3).
**LunaPath için çıkarım (1):** Mimarimiz (grid + çok-kriter + fizik simülasyonu) gerçek küresel planlayıcıların doğrudan soyundandır — bunu raporda açıkça konumlandırın. Ancak gerçek görevler **iki katmanlıdır**; LunaPath'in yalnız küresel/stratejik katman olduğunu, taktik tehlike kaçınmayı modellemediğini bir sınır olarak belirtin. Yutu-2'nin tamamen yer-döngüsüyle sürülmesi, Ay kutbu için "supervised teleoperation + stratejik otonomi" karışımının gerçekçi ConOps olduğunu gösterir — otonomiyi "zorunlu" diye sunmayın.
 
---
 
### 2. FİZİKSEL KISITLAR VE EŞİK DEĞERLER
 
**2.1 — Eğim limitleri ve süspansiyon**
- **VIPER slope:** "VIPER can generally drive on a slope of up to 15 degrees" (NASA Science VIPER Lunar Operations); Smithsonian: rutin ~15°, gerektiğinde 25–30°. → Kutup rover'ı için operasyonel eğim eşiği ~15°, tasarım ~25–30°.
- **Curiosity/MSL:** NASA GSFC'ye göre "Curiosity 45°'ye kadar eğimlere dayanacak şekilde tasarlanmıştır, ancak tehlike-kaçınma yazılımı 30°'yi aşmasını engeller." Operasyonel rekoru Sol 2696'da 31° tırmanıştır. → **Statik stabilite (tasarım, 45°) ≠ operasyonel limit (30°);** operasyonel limit her zaman daha muhafazakârdır.
- **Rocker-bogie:** JPL Rocky IV (1990'lar), Sojourner'dan itibaren standart; yaylı olmayan pasif süspansiyon, teker çapının ~2 katı engel aşımı; devrilme merkezi kütle yüksekliğiyle sınırlı. → Kaynaklar: IJISRT "Design of Rocker-Bogie Mechanism"; RoverDevKit (arXiv:2606.21755).
- **VIPER Mobility (geoteknik):** "Investigating the Geotechnical Properties of the Lunar South Pole with NASA VIPER's Mobility System" *PSJ*. DOI: 10.3847/PSJ/add13f. → 7 farklı zemin koşulunda sürüş, sinkage/track gözlemi; teker-toprak modelini yerinde çıkarım. *(Açık — IOP)*
**2.2 — Batarya yönetimi / minimum SoC**
- VIPER, PSR'ye girip **güç bitmeden güneşli şarj noktasına dönmeyi** garanti edecek şekilde planlanır (VIPER Site Analysis / Relevance, IOP). → Minimum SoC rezervi = geri dönüş enerjisi + hibernasyon yükü. LunaPath'in SoC simülasyonu doğru fikir; ama "geri dönüş rezervi" kısıtı eklenmeli.
- **"Energy storage selection and operation for night-time survival of small lunar surface systems" *Acta Astronautica* (2021), DOI: 10.1016/j.actaastro.2021.04.032.** → Düşük sıcaklıkta Li-ion kapasite düşüşü; küçük rover'lar RHU'suz yalnız 2 hafta hayatta kalabilir. *(Kapalı)*
**2.3 — Termal tasarım / survival**
- **Park, S., et al. (2018). "Preliminary Thermal Design and Analysis of Lunar Lander for Night Survival." *Int. J. Aerospace Eng.***, DOI: 10.1155/2018/4236396. → RHU + shutter + MLI; Lunokhod'un RHU konsepti; gece minimum -95.9°C senaryosu. *(Açık — Hindawi/Wiley)*
- **"A Proposal for Long-Term Missions of Small Lunar Rovers Using an MLI Curtain System" (2019), Int. J. Aerospace Eng.** → Ay gecesi -190°C; küçük rover'lar RHU olmadan sağ kalamaz; 1 W ısıtıcı için +360 Wh batarya ≈ +2.5 kg. *(Açık)*
- **RoverDevKit (arXiv:2606.21755, 2026).** → Tek-düğüm hot/cold termal model **Pragyan'ın (RHU yok) gece sağ kalamadığını, Yutu-2'nin (RHU var) kaldığını** doğru öngörür. Termal survival flag'in görev sonucu belirlediğini gösterir. *(Açık — arXiv)*
- **NASA TFAWS23-PT-52 "Surviving Night at the Lunar South Pole"** ve **NTRS 20210019184 / 20210011101 (Battery/Power Hibernation).** → GPHS-RHU vs batarya-ısıtıcı trade'i, hibernasyon protokolü. *(Açık — NTRS)*
**2.4 — Terramekanik ve regolit mekaniği**
- **Bekker, M.G. (1956/1969). *Introduction to Terrain-Vehicle Systems*, Univ. of Michigan Press.** → Basınç-batma temel modeli: p(z) = (k_c/b + k_φ) z^n. *(Kitap)*
- **Wong, J.Y. & Reece, A.R. (1967). "Prediction of rigid wheel performance based on the analysis of soil-wheel stresses." *J. Terramechanics*, 4(1).** → Teker-toprak normal ve kayma gerilmesi dağılımı; terramekaniğin ikinci temel taşı.
- **Iagnemma, K. & Dubowsky, S. (2004). *Mobile Robots in Rough Terrain*, Springer (STAR 12).** → Drawbar pull, normal kuvvet, lineer gerilme dağılımı; slip'in rover üzerindeki etkisi.
- **Ishigami, G., Miwa, A., Nagatani, K., Yoshida, K. (2007). "Terramechanics-based model for steering maneuver of planetary exploration rovers on loose soil." *J. Field Robotics*, 24(3).** ve **Ishigami et al. (2009) "Slope traversal controls…" *JFR* 26(3):264–286.** → Ay/gezegen rover'ı için gevşek zeminde eğim geçişi kontrolü.
- **Ding, L., Gao, H., Deng, Z., et al. (2009/2011). Değişken batma üsteli (variable sinkage exponent) modeli.** → Wong-Reece'i slip'e bağlı batma üstel fonksiyonuyla geliştirir; slip-sinkage'ı yüksek doğrulukla öngörür. → Kaynak: "Wheel slip-sinkage and its prediction model of lunar rover."
- **Gonzalez, R. & Iagnemma, K. (2018). "Slippage estimation and compensation for planetary exploration rovers: State of the art and future challenges." *J. Field Robotics*, 35(4):564–577.** → Slip tahmin/telafi literatür özeti.
- **Ay simülantları:** JSC-1A, LHS-1 (Lunar Highlands Simulant, Exolith Lab), LMS-1 (Mare), GRC-1 (mekanik simülant), KLS-1 (Kore). Mekanik özellikler ve bevameter testleri: "Development of a New Pressure-Sinkage Model… based on Bevameter Tests" *J. Astron. Space Sci.* 38(4):237.
**2.5 — Ay tozu problemi**
- **Gaier, J.R. (2005). "The Effects of Lunar Dust on EVA Systems During the Apollo Missions." NASA/TM-2005-213610.** → Apollo'da toz: görüş engeli, yanlış okuma, conta arızası, mekanizma tıkanması, termal kontrol bozulması, abrazyon. *(Açık — NTRS)*
- **NASA TM-20240003496 "Lunar Dust Considerations for Vertical Solar Arrays" (2024).** → Elektrostatik yüklenme, panel ve mekanizmaya yapışma, LTV/PR bağlamı. *(Açık — NTRS)*
- **TFAWS 2024 PT-4 "Thermal Impacts of Lunar Dust for Rovers."** → Toz termal radyatörleri bozar; VIPER için VDA/Kapton degradasyonu. *(Açık)*
- **Stubbs, T.J., et al. — elektrostatik toz kaldırma/horizon glow.** → Terminatör bölgesinde toz-plazma aktivitesi.
**2.6 — Güneş paneli güç üretimi (kutup)**
- Gläser et al. (bkz. 3.1): 2 m yükseğe panel kaldırmanın Connecting Ridge'de aydınlanmayı %80'e kadar artırması. → Düşük güneş açısında (kutup) verim, panel yüksekliği ve horizon-mask'a çok duyarlıdır; kosinüs kaybı + toz kaybı birlikte modellenmeli.
**LunaPath için çıkarım (2):** Eğim kriterinizde **statik devrilme limitini (tasarım, 45°) operasyonel limitten (~15–30°) ayırın** ve operasyonel limiti kullanın. Enerji kriterine terramekanik **slip** terimi ekleyin: slip yalnız enerji kaybı değil, batma/gömülme riskidir (Spirit-Troy). Termal modeliniz sabit +60°C ofset yerine en azından Pragyan/Yutu-2 ikili ("RHU var/yok → sağ kalır/kalmaz") mantığını yansıtmalı. Batarya kriterine **"eve dönüş + hibernasyon rezervi" minimum SoC kısıtı** ekleyin.
 
---
 
### 3. AYDINLANMA VE GÖLGE MODELLEME
 
- **Mazarico, E., Neumann, G.A., Smith, D.E., Zuber, M.T., Torrence, M.H. (2011). "Illumination conditions of the lunar polar regions using LOLA topography." *Icarus*, 211(2):1066–1081.** DOI: 10.1016/j.icarus.2010.10.030. → **Horizon (ufuk-maskesi) yöntemi**: her piksel için azimut-bazlı maksimum yükseklik açıları veritabanı, sonra Güneş elevasyonu karşılaştırması. 240 m DEM, 18.6 yıllık presesyon döngüsü. Shackleton krater kenarında ~8 km arayla iki nokta birbirini gölgeleyerek birlikte ~%94 yıllık aydınlanma sağlayabilir. LunaPath'in gölge modeli için **doğrudan yerine konması gereken referans**. *(Kapalı; ResearchGate PDF açık)*
- **Gläser, P., Scholten, F., De Rosa, D., et al. (2014). "Illumination conditions at the lunar south pole using high resolution Digital Terrain Models from LOLA." *Icarus*, 243:78–90.** DOI: 10.1016/j.icarus.2014.08.013. → **20 m/piksel** DTM (LunaPath'inkiyle aynı çözünürlük!), Connecting Ridge (CR1) ve Shackleton Rim; 2 m panel yüksekliğiyle CR1 %80 aydınlanma. *(Kapalı; RG PDF açık)*
- **Bussey, D.B.J., et al. (2005/2010).** → Clementine ve Kaguya doğrulaması: güney kutbunda "ebedi ışık zirvesi (peak of eternal light) yoktur"; yalnızca "ay-gününün %70'inden fazla aydınlanan küçük alanlar" vardır ve güney kutbunda >%70 aydınlanan toplam alan "yalnızca birkaç yüz metrekare" mertebesindedir (arXiv:1608.01989). → Kutupta "sürekli güneş" idealinin ne kadar dar bir alan olduğunu gösterir.
- **Noda, H., et al. (2008) (Kaguya/LALT ray-tracing).** → Kuzey/güney kutbunda ebedi ışık zirvesi yok; en fazla sürekli aydınlanan yüzeyler kuzeyde %89, güneyde %86 mertebesinde.
- **De Rosa, D., et al. (2012). ESA iniş bölgeleri için 40 m/piksel horizon yöntemi.** → Belirli bölgeler için yüksek çözünürlük.
- **Mazarico, E., Barker, M.K., et al. (2023). "Sunlit pathways between south pole sites of interest for lunar exploration." *Acta Astronautica*, 204:49–57.** DOI: 10.1016/j.actaastro.2022.12.037. → **Doğrudan LunaPath'in problemi:** kutup bölgesinde güneşli yollar/traverse'ler. Mutlaka okunmalı. *(Kapalı)*
- **PSR tanımı ve çift gölge:** Diviner + LOLA ile PSR haritaları (bkz. 4.1). PSR = presesyon döngüsü boyunca hiç doğrudan güneş almayan bölge; "double shadow" = ne doğrudan Güneş ne de sıcak krater duvarından ikincil ısınma.
**Yayınlanmış aydınlanma veri ürünleri (açık):**
- LOLA DEM'leri: PDS Geosciences Node (pds-geosciences.wustl.edu), 5/10/20/240 m kutup ürünleri.
- JPL "lunar south pole solar illumination dataset" (VIPER için kullanıldı — Lamarre et al. arXiv:2401.08558 teşekkür bölümü).
**LunaPath için çıkarım (3):** Gölge modelinizin "yükseklik tabanlı vekil formül" olması en zayıf noktanızdır ve düzeltilebilir: aynı LOLA DEM'den **ufuk-maskesi (horizon-mask)** hesaplayın (Mazarico 2011 yöntemi). Bu, ekstra veri gerektirmez, yalnız DEM'den azimut-yükseklik veritabanı üretmeyi gerektirir ve modelinizin kredibilitesini kategorik olarak yükseltir. En azından "vekil formül vs. horizon-mask" karşılaştırması yaparak farkı raporlayın. Ayrıca kutupta "sürekli güneş" alanlarının birkaç yüz metrekareyle sınırlı olduğunu bilmek, gerçekçi başlangıç/hedef noktası seçimine yardımcı olur.
 
---
 
### 4. TERMAL ORTAM VERİLERİ
 
- **Paige, D.A., Foote, M.C., Greenhagen, B.T., et al. (2010). "The Lunar Reconnaissance Orbiter Diviner Lunar Radiometer Experiment." *Space Science Reviews*, 150:125–160.** DOI: 10.1007/s11214-009-9529-2. → Cihaz tanımı; 9 kanal, 0.3–400 µm; ~250 m çözünürlük (50 km yörünge). *(Kapalı; NTRS'de olabilir)*
- **Paige, D.A., Siegler, M.A., Zhang, J.A., et al. (2010). "Diviner Lunar Radiometer Observations of Cold Traps in the Moon's South Polar Region." *Science*, 330(6003):479–482.** DOI: 10.1126/science.1187726. → PSR'lerde <50 K, hatta <30 K sıcaklıklar; su buzu tuzakları. *(Kapalı)*
- **Williams, J.-P., Paige, D.A., Greenhagen, B.T., Sefton-Nash, E. (2017). "The global surface temperatures of the Moon as measured by the Diviner Lunar Radiometer Experiment." *Icarus*, 283:300–325.** DOI: 10.1016/j.icarus.2016.08.012. → Diurnal döngü, global sıcaklık; ekvatorda >400 K, kutupta <50 K. *(arXiv:1711.00977 açık)*
- **Sefton-Nash, E., Williams, J.-P., et al. (2017). "Diviner lunar radiometer gridded brightness temperatures from geodesic binning." *Icarus*, 298.** → 128 ppd (~250 m) gridleme metodolojisi. *(Kapalı)*
- **Vasavada, A.R., et al. (2012). "Lunar equatorial surface temperatures and regolith properties from Diviner." *JGR Planets*, 117(E12).** → Termal atalet, regolit termal özellikleri, diurnal model.
- **Veri erişimi (açık):** PDS Geosciences Node, LRO-L-DLRE-4/5-RDR-V1.0; Level-2 gridded 128 ppd ürünler; kutup kümülatif ürünler (Williams et al. Polar Mapping, LPSC/Ices 2023, hou.usra.edu/meetings).
**LunaPath için çıkarım (4):** Termal modeliniz "sabit +60°C ofset" yerine, **Diviner 128 ppd sıcaklık gridini** girdi olarak kullanabilir (aynı bölge için indirilebilir, açık erişim). En kritik eksik olan **termal zaman sabiti (thermal inertia)** — regolit düşük termal atalete sahiptir, yani sıcaklık gölgeye girince hızla düşer; bu, LunaPath'in "iç sıcaklık" simülasyonuna birinci-derece bir RC (τ) modeli olarak eklenebilir. Bu iki değişiklik termal kriteri "uydurma"dan "veri-temelli"ye taşır.
 
---
 
### 5. HABERLEŞME KISITLARI
 
- **Otten, N.D., Jones, H.L., Wettergreen, D.S., Whittaker, W.L. — "Planning routes of continuous illumination and traversable slope using connected component analysis" (ICRA/FSR).** ve **Otten, N., Wettergreen, D., Whittaker, W. (2018). "Strategic Autonomy for Reducing Risk of Sun-Synchronous Lunar Polar Exploration." (FSR 2017).** DOI: 10.1007/978-3-319-67361-5_30. → **Sürekli güneş ışığı + sürekli Dünya haberleşmesi (DTE) kısıtını aynı anda** rotaya dahil eder. Haberleşmeyi rota kriterine katmanın kanonik referansı. *(Açık — publications.ri.cmu.edu PDF)*
- **Tompkins, P. (2005). "Mission-Directed Path Planning for Planetary Rover Exploration." PhD Thesis, CMU-RI-TR-05-20.** → TEMPEST/ISE'nin tam tezi; uzay-zaman-enerji dört boyutlu arama; DTE görünürlük kısıtı. *(Açık — ri.cmu.edu PDF)*
- **VIPER DTE:** "The rover must stay out of DTE communication shadows during active operations" (VIPER Relevance to Artemis, PSJ, DOI:10.3847/PSJ/ae4232). Kutupta Dünya ufkun hemen üzerinde → arazi gölgelemesi hem Güneş'i hem Dünya'yı aynı anda kesebilir. *(Açık — IOP)*
- **Röle mimarileri:**
  - **Queqiao (Chang'e-4):** Wu, W., et al. "Technical characteristics of the relay communication satellite 'Queqiao'." *Sci. Sin. Tech.* DOI: 10.1360/N092018-00375. Earth-Moon L2 Halo yörünge, 4.2 m anten, X-band (rover/lander), S-band (Dünya). → Yutu-2'nin farside'da çalışabilmesinin nedeni.
  - **Zhang, L., et al. (2021). "Development and Prospect of Chinese Lunar Relay Communication Satellite." *Space: Science & Technology*.** DOI: 10.34133/2021/3471608. → Queqiao + güney kutbu için Queqiao-2 planı. *(Açık)*
  - **LunaNet / Artemis:** NASA LunaNet Interoperability Specification; ESA Moonlight. → Kutup ve farside için röle altyapısı.
- **Otonomi modları:** Wettergreen et al. (2005, bkz. 9.1) "supervised teleoperation vs strategic autonomy" ayrımı; Otten (2018) stratejik otonomiyi risk azaltma olarak konumlar.
**LunaPath için çıkarım (5):** "Haberleşme modellenmiyor" zayıflığınız, kutup senaryosunda **en ciddi eksiklerden biridir** çünkü Otten ve VIPER literatürü DTE görünürlüğünü Güneş görünürlüğü kadar önemli sayar. Minimum düzeltme: DEM + Dünya efemeris geometrisinden bir **DTE görünürlük (line-of-sight) maskesi** üretip beşinci bir kriter/kısıt olarak ekleyin, ya da en azından "DTE gölgesinde geçirilen süre" metriğini rota değerlendirmesine katın. Bu, gölge modeliyle **aynı ufuk-maskesi altyapısını** kullanır (ekonomik).
 
---
 
### 6. RADYASYON ORTAMI
 
**6.1 / 6.2 — Ölçüm verileri**
- **Zhang, S., Wimmer-Schweingruber, R.F., Yu, J., et al. (2020). "First measurements of the radiation dose on the lunar surface." *Science Advances*, 6(39):eaaz1334.** DOI: 10.1126/sciadv.aaz1334. → Chang'e-4 LND: **toplam soğurulan doz hızı 13.2 ± 1 µGy/saat (Si), nötral parçacık 3.1 ± 0.5 µGy/saat; yüklü parçacık doz eşdeğeri ~57.1 µSv/saat (~500 mSv/yıl)**. Ay yüzeyi radyasyonunun ilk doğrudan ölçümü. *(Açık — PMC7518862)*
- **Wimmer-Schweingruber, R.F., et al. (2020). "The Lunar Lander Neutron and Dosimetry (LND) Experiment on Chang'E 4." *Space Sci. Rev.*, 216:104.** DOI: 10.1007/s11214-020-00725-3. → LND cihaz tanımı. *(arXiv:2001.11028 açık)*
- **Schwadron, N.A., et al. (2012). "Lunar radiation environment and space weathering from CRaTER." *JGR Planets*, 117:E00H13.** DOI: 10.1029/2011JE003978. → LRO/CRaTER GCR + SPE LET spektrumları; 7 Haziran 2011 SPE. *(Kapalı)*
- **Mazur, J.E., et al. (2011). "New measurements of total ionizing dose in the lunar environment." *Space Weather*, 9.** DOI: 10.1029/2010SW000641. → LRO ilk yıl TID yalnız **12.2 rad** (GCR-baskın, solar minimum), spec'in (~4.6 krad/yıl) iki mertebe altında. *(Kapalı)*
- **Schwadron, N.A., et al. (2014). "Does the worsening galactic cosmic radiation environment observed by CRaTER preclude future manned deep space exploration?" *Space Weather*, 12:622–632.** → GCR'nin solar minimumda tarihsel zirvede olması. *(Kapalı)*
**6.3 — Ekranlama:** LND ölçümleri regolit etkileşimiyle üçüncü bir bileşen (nötron+gama albedo) gösterir; nötron akısı ~150 g/cm²'ye kadar artar. Regolit/krater/lav tüpü sığınma insanlı görevler için ilgili (Townsend, NASA RadWorks — aşağıda).
 
**6.4 — KRİTİK SORU: Radyasyon robotik rover için rota kriteri olarak anlamlı mı?**
 
**NET CEVAP: HAYIR.** Alt-ajan araştırması ve taranan tüm rota-planlama literatürü bunu doğruluyor:
 
- **Robotik rover rotasını radyasyona göre optimize eden hiçbir yayın bulunamadı.** Taranan planlayıcılar (CMU TEMPEST/Otten; Lamarre et al. arXiv:2401.08558; "Deep Learning… RCSP" *Sensors* 24(3):844, DOI:10.3390/s24030844; "Comprehensive Review of Path-Planning Algorithms" *Remote Sensing* 17(11):1924) kriter olarak **eğim, aydınlanma, enerji, termal, haberleşme, traversability** kullanır — **radyasyon hiçbirinde maliyet terimi değildir.**
- **Fiziksel gerekçe:** GCR yüzey doz hızı ~13.2 µGy/saat (LND). 1–2 haftalık bir traverse'te birikimi ~0.1–1 krad(Si) mertebesindedir. **MoonRanger (CMU, MR-AVI-0068)** kısa görevde (~14 gün) yüzey TID'ini **6.8 cGy(Si)/gün → ~95 rad(Si) (<1 krad)** olarak verir; bileşenleri 5–45+ krad'a dayanıklıdır. Yani birkaç günlük/haftalık traverse'te TID rota seçimini **değiştirmez.**
- **MoonRanger açıkça belirtir:** radyasyon viabilitesi "bileşen seçimi, ekranlama, kısa görev süresi, test, hata düzeltme ve izleme ile" sağlanır — **rota seçimiyle DEĞİL.** Bu, robotik radyasyonun bir *elektronik tasarım* problemi olduğunun doğrudan ifadesidir. *(Açık — labs.ri.cmu.edu PDF)*
- **Tek istisna — SPE (solar particle event):** Bir SPE dozu mertebelerce artırabilir. Ancak SPE'ye robotik yanıt yine ekranlama/görev-zamanlaması/güvenli-moddur, uzamsal rota optimizasyonu değil.
- **İnsanlı bağlam farklıdır:** Radyasyon rotaya/traverse'e yalnız **insanlı** görevlerde girer ve orada bile *SPE sığınak yakınlığı/zamanlaması* olarak (nereye kadar uzaklaşabilirim), GCR-optimize pathfinding olarak değil:
  - **Townsend, L.W., et al. (2018). "Solar particle event storm shelter requirements for missions beyond low Earth orbit." *Life Sciences in Space Research*, 17.** DOI: 10.1016/j.lssr.2017.12.001. → 250 mGy-Eq BFO limiti; sığınağa olay başlangıcından **30 dk içinde** ulaşma gereksinimi.
  - **Mertens, C.J. & Slaba, T.C. (2019). "Characterization of Solar Energetic Particle Radiation Dose to Astronaut Crew…" *Space Weather*, 17.** DOI: 10.1029/2019SW002363.
  - **NASA RadWorks Storm Shelter (NTRS 20170002287).** *(Açık — NTRS)*
  - **Guo, J., et al. (2025). "Nowcasting Solar Energetic Particle Events for Mars Missions." arXiv:2502.02469.** → SPE "lead time" ile astronotun sığınaktan ne kadar uzaklaşabileceğini hesaplar — radyasyonun *excursion range/timing* kısıtı olduğu, uzamsal rota kriteri OLMADIĞI en yakın örnek. *(Açık — arXiv)*
**6.5 — Rad-hard elektronik ve onboard işlem gücü**
- **RAD750** (BAE Systems) Perseverance/MSL'de kullanılır; ~200 MHz, ~100+ krad(Si) TID toleransı. → ENav literatürü (Rankin et al.) algoritmaların "RAD750 işlemcide çalışacak kadar hafif" olması gerektiğini vurgular. → Bu, LunaPath gibi ağır (Monte Carlo, çok-kriterli) planlamaların **onboard değil, yerde (küresel planlayıcı)** çalışması gerektiğini destekler.
**LunaPath için çıkarım (6):** **Radyasyonu bir rota kriteri olarak EKLEMEYİN** — bu, literatürle çelişir ve fiziksel olarak gereksizdir. Bunun yerine raporda bunu bir **bilinçli tasarım kararı** olarak sunun: "Kısa süreli robotik bir traverse'te TID birikimi (<1 krad) bileşen toleransının (5–45 krad) çok altındadır (MoonRanger; Mazur); radyasyon rota değil, bileşen/görev-ömrü problemidir. SPE anlık tehlikesi rota optimizasyonuyla değil güvenli-mod/ekranlama ile yönetilir." Bu, jüriye **olgunluk** gösterir: her fiziği modele katmak değil, hangi fiziğin rota-ilgili olduğunu ayırt etmek. AHP'de radyasyonu kriter yapmamanız güçlü ve savunulabilir bir tercihtir.
 
---
 
### 7. STANDARTLAR, GEREKSİNİM VE DOĞRULAMA
 
**7.1 — ECSS**
- **ECSS-E-ST-40C (2009). Space engineering — Software.** → Yazılım mühendisliği süreç standardı; gereksinim, tasarım, doğrulama.
- **ECSS-Q-ST-80C Rev.1 (2017). Software product assurance.** → Yazılım ürün güvencesi; kritiklik kategorileri (A–D), bağımsız doğrulama.
- **ECSS-E-ST-10C Rev.1 (2017). System engineering general requirements.** → Sistem mühendisliği; gereksinim yönetimi, tailoring.
- → ECSS'nin "criticality categories" ve "tailoring" kavramları öğrenci projesi için de uygulanabilir: kritik olmayan bir demonstratörde standardı kırpın (tailor) ama izlenebilirliği koruyun.
**7.2 — NASA**
- **NASA-STD-7009A/B. Standard for Models and Simulations.** standards.nasa.gov. → **En kritik standart** (aşağı bakınız). *(Açık)*
- **NPR 7150.2D. NASA Software Engineering Requirements.** → Yazılım sınıflandırması (Class A–H), süreç gereksinimleri.
- **NASA/SP-2016-6105 Rev2. NASA Systems Engineering Handbook.** → SE süreçleri, V-model, doğrulama/geçerleme.
**7.3 — TRL**
- **Mankins, J.C. (1995/2009). "Technology Readiness Levels: A White Paper" ve "Technology readiness assessments: A retrospective." *Acta Astronautica*, 65.** DOI: 10.1016/j.actaastro.2009.03.058. → TRL 1–9 tanımları. ISO 16290 uzay için TRL'yi standartlaştırır. LunaPath gibi bir simülasyon aracı muhtemelen TRL 3–4 (analitik/laboratuvar doğrulama).
**7.4 — Model/Simülasyon V&V ve kredibilite**
- **NASA-STD-7009A. Standard for Models and Simulations.** → **Credibility Assessment Scale (CAS):** 8 faktör — verification, validation, input pedigree, uncertainty, robustness, use history, M&S management, people. → LunaPath'in **tam olarak ihtiyaç duyduğu çerçeve:** modelinizin zayıflıklarını (vekil gölge, sabit termal ofset vb.) CAS faktörleri altında şeffaf raporlayın. *(Açık — standards.nasa.gov PDF)*
- **NASA-HDBK-7009A. Handbook for Models and Simulations.** → 7009'un uygulama kılavuzu; pathfinder örnekleri (Orion, MSL Powered Descent). *(Açık — NTRS)*
- **Ahn, J. & de Weck, O. (2011). "Credibility Assessment of Models and Simulations Based on NASA's Standard Using the Delphi Method." *Systems Engineering*.** DOI: 10.1002/sys.21266. → Çoklu-uzmanla kredibilite değerlendirme; SpaceNet vaka çalışması.
- **NTRS 20200002832 "Applying NASA-STD-7009 to Surrogate and Other Statistical Models."** → Vekil modellere 7009 uygulaması — LunaPath'in vekil gölge/termal formülleri için doğrudan ilgili. *(Açık — NTRS)*
**7.5 — RTM (Requirements Traceability Matrix):** NASA SE Handbook ve ECSS-E-ST-10 gereksinim izlenebilirliğini zorunlu tutar; her gereksinim → tasarım → test eşlemesi.
 
**LunaPath için çıkarım (7):** **NASA-STD-7009 CAS'ı raporunuzun omurgası yapın.** Modelin bilinen zayıflıkları (vekil gölge, sabit +60°C, τ yok, haberleşme yok, radyasyon yok, zaman ekseni yok) birer "kusur" değil, CAS'ın "validation" ve "uncertainty" faktörleri altında **dürüstçe raporlanmış kredibilite sınırlarıdır.** Bu çerçeve, jüriye modelin ne için geçerli (fizibilite/eğitim/trade-study) ne için geçerli olmadığını (uçuş-kalitesi operasyon planı) net söyler. Küçük bir RTM (5–10 gereksinim) ve TRL öz-değerlendirmesi (muhtemelen TRL 3) ekleyin.
 
---
 
### 8. ÇOK KRİTERLİ KARAR VERME (MCDM)
 
**8.1 — AHP temelleri**
- **Saaty, T.L. (1980). *The Analytic Hierarchy Process*. McGraw-Hill.** ve **Saaty, T.L. (1987). "The analytic hierarchy process—what it is and how it is used." *Math. Modelling*, 9(3–5).** → AHP'nin kaynağı; 1–9 ölçeği, eigenvector öncelik, **tutarlılık oranı CR = CI/RI**; CR < 0.10 kabul eşiği.
- **Saaty, T.L. (2008). "Decision making with the analytic hierarchy process." *Int. J. Services Sciences*, 1(1).** → Modern özet.
**8.2 — Çoklu-uzman AHP**
- **Forman, E. & Peniwati, K. (1998). "Aggregating individual judgments and priorities with the AHP." *European J. Operational Research*, 108(1):165–169.** DOI: 10.1016/S0377-2217(97)00244-0. → **AIJ (Aggregation of Individual Judgments — geometrik ortalama) vs AIP (Aggregation of Individual Priorities)** ayrımı. Çoklu-uzman ağırlıklandırmanın kanonik referansı. → LunaPath'in AHP ağırlıkları birden çok ekip üyesinden geliyorsa **geometrik ortalama (AIJ)** kullanın.
- **Aczél, J. & Saaty, T.L. (1983). "Procedures for synthesizing ratio judgments." *J. Math. Psychology*, 27.** → Geometrik ortalamanın neden matematiksel olarak doğru toplama olduğu (yalnız geometrik ortalama karşılıklılığı korur).
**8.3 — AHP eleştirileri (rank reversal)**
- **Belton, V. & Gear, T. (1983). "On a shortcoming of Saaty's method of analytic hierarchies." *Omega*, 11(3):228–230.** → Rank reversal'ı ilk gösteren çalışma; normalizasyon kaynaklı. *(Kanonik eleştiri)*
- **Dyer, J.S. (1990). "Remarks on the Analytic Hierarchy Process." *Management Science*, 36(3):249–258.** → IIA (bağımsız alternatiflerden bağımsızlık) ihlali eleştirisi; en sert teorik eleştiri.
- **Belton, V. & Gear, T. (1985). "The legitimacy of rank reversal — a comment." *Omega*, 13(3):143–144.**
- **Saaty, T.L. & Vargas, L.G. (1984) ve Saaty (1990)** → Saaty ekolünün karşı-argümanı: rank reversal bazı durumlarda meşrudur. → LunaPath için: rank reversal'ı bilin ve **ideal-mode AHP** (Belton-Gear normalizasyonu) kullanarak azaltın.
**8.4 — Alternatif MCDM**
- **Hwang & Yoon (1981). TOPSIS.** → İdeal çözüme yakınlık; sürekli/kantitatif kriterler için AHP'den daha uygun olabilir.
- **ELECTRE (Roy, 1968), PROMETHEE (Brans & Vincke, 1985), VIKOR (Opricovic, 1998).** → Outranking yöntemleri; eşik/tercih fonksiyonları.
- **Entropi ağırlıklandırma (Shannon).** → Veri-temelli objektif ağırlık; AHP'nin subjektif ağırlıklarını tamamlayabilir.
- Uzay/robotikte kullanım: iniş bölgesi seçimi ve rover trade-study'lerinde AHP ve TOPSIS yaygındır; PROMETHEE/ELECTRE daha az.
**8.5 — Duyarlılık analizi**
- **Triantaphyllou, E. & Sánchez, A. (1997). "A sensitivity analysis approach for MCDM methods." *Decision Sciences*, 28(1).** → Kriter ağırlığında en küçük değişimin sıralamayı bozması (kritik kriter). → LunaPath için **zorunlu**: AHP ağırlıklarını ±%10–20 pertürbe edip rota sıralamasının stabilitesini gösterin.
- **One-at-a-time (OAT) vs global (Sobol) duyarlılık:** Saltelli, A., et al. (2008). *Global Sensitivity Analysis: The Primer*. Wiley. → OAT hızlı ama etkileşimleri kaçırır; Sobol daha kapsamlı.
**8.6 — Normalizasyon**
- Farklı birimli kriterler (eğim °, enerji Wh, gölge %, sıcaklık °C) normalize edilmeli: min-max, vektör (TOPSIS), z-score. Normalizasyon seçimi sonucu etkiler (rank reversal'ın bir kaynağı — Belton-Gear).
**LunaPath için çıkarım (8):** AHP kullanımınızı üç ekle savunun: (1) **CR < 0.10 raporlayın**; (2) çoklu-uzman varsa **geometrik ortalama (AIJ, Forman-Peniwati)**; (3) **ağırlık duyarlılık analizi** (Triantaphyllou) — bu, jürinin "ağırlıkları neden böyle seçtiniz?" sorusuna en güçlü yanıttır. Rank reversal'ı bir sınır olarak kabul edin ve mümkünse ideal-mode normalizasyon kullanın. Radyasyonu kriter yapmama kararınız (Bölüm 6) AHP hiyerarşisinde bilinçli bir kapsam kararı olarak yer almalı.
 
---
 
### 9. YOL PLANLAMA ALGORİTMALARININ DEĞERLENDİRİLMESİ
 
**9.1 / 9.4 — Kaynak-kısıtlı ve zaman-bağımlı planlama**
- **Tompkins, P., Stentz, A., Wettergreen, D. (2006). "Mission-level path planning and re-planning for rover exploration." *Robotics and Autonomous Systems*, 54(2):174–183.** DOI: 10.1016/j.robot.2005.10.001. → TEMPEST: uzay-zaman-enerji-güneş dört boyutlu planlama; ISE (Incremental Search Engine, D* benzeri). → **LunaPath'in olması gereken hedef mimarisi:** zaman planlama ekseninde.
- **Wettergreen, D., Tompkins, P., Urmson, C., Wagner, M., Whittaker, W. (2005). "Sun-Synchronous Robotic Exploration: Technical Description and Field Experimentation." *Int. J. Robotics Research*, 24(1):3–30.** DOI: 10.1177/0278364904046632. → Hyperion; güneş-senkron navigasyon; saha deneyi; supervised teleoperation vs strategic autonomy ayrımı.
- **Whittaker, W.L., Kantor, G., Shamah, B., Wettergreen, D. (2000). "Sun-Synchronous Planetary Exploration." AIAA Space 2000, 5300.** → Kavramın kaynağı.
- **CSA* (Constraints Satisfying A*): "Shortest Path Planning for Energy-Constrained Mobile Platforms Navigating on Uneven Terrains." *IEEE T-ITS* (2018).** DOI: 10.1109/TITS.2018.2790405. → **Admissible heuristic korunarak** enerji-kısıtlı RCSP çözümü; A*'ın optimalitesini korur. → LunaPath'in A*'ını RCSP'ye genişletmek için doğrudan yöntem.
- **RCSP genel:** RCSP NP-zordur (tek kaynakta bile); çözümler: etiketleme (labeling), battery-expanded/time-expanded grid, FPTAS. → time-expanded graph = grid'e zaman katmanı eklemek; LunaPath'in zaman eksenini eklemesinin standart yolu.
- **"A Deep Learning Approach to Lunar Rover Global Path Planning… Internal Resource Status." *Sensors* 24(3):844 (2024).** DOI: 10.3390/s24030844. → Statik + zaman-değişken + yol-bağımlı kısıtları (termal, güç) tek grafikte; RCSP'yi RL ile çözer. Oikawa et al.'nin termal/güç kısıtlarını Dijkstra ile zaman-sabit yaklaştırdığını eleştirir. *(Açık — PMC10857624)*
**9.2 / 9.3 — Monte Carlo doğrulama ve başarı oranı**
- **Lamarre, O., Malhotra, S., Kelly, J. (2024). "Safe Mission-Level Path Planning for Exploration of Lunar Shadowed Regions by a Solar-Powered Rover." (IEEE Aerospace).** arXiv:2401.08558. → **Chance-constrained** planlama: rastgele arızalar (sabit ortalama oranla), **Monte Carlo simülasyonuyla** görev-başarısızlık olasılığı üst sınırı; risk-agnostic vs risk-bounded plan karşılaştırması; LCROSS yakını gerçek senaryo. → **LunaPath'in "mission success rate" metriği için doğrudan şablon.** *(Açık — arXiv)*
- **"A Comprehensive Review of Path-Planning Algorithms for Planetary Rover Exploration." *Remote Sensing* 17(11):1924 (2025).** DOI: 10.3390/rs17111924. → Gezegen rover planlama algoritmalarının benchmark/metrik özeti. *(Açık — MDPI)*
**LunaPath için çıkarım (9):** **En yüksek değerli tek geliştirme: zamanı planlama eksenine almak** (time-expanded grid). Şu an gölge/termal zamanla değişirken planlayıcınız zamanı görmüyorsa, "gölgeden kaçış" fiziksel olarak yanlış olabilir. TEMPEST (Tompkins) ve Sensors-2024 bunun nasıl yapıldığını gösterir. Değerlendirme için Lamarre et al.'yi taklit edin: **Monte Carlo ile mission success rate** hesaplayın, baseline olarak "naif en-kısa-yol" ve "eğim-only" planlayıcıları kullanın. A*'ı RCSP'ye genişletirken **admissible heuristic'i koruyun** (CSA*) — aksi halde optimalite garantisini kaybedersiniz.
 
---
 
### 10. TÜRKİYE BAĞLAMI
 
**10.1 — AYAP ve Milli Uzay Programı**
- **TUA (2022). *Milli Uzay Programı Strateji Belgesi*.** cdn.tua.gov.tr/62988f09d2a2e.pdf. → 10 hedef; **AYAP-1**: Ay yörüngesinden keşif + yüzeyle ilk temas (sert iniş), ilk aşama hedefi 2023 (Cumhuriyet 100. yıl); **AYAP-2**: milli fırlatma aracıyla yumuşak iniş + **gezici araç (rover)**, hedef 2028. *(Açık — TUA PDF)*
- **AA (2021). "Türkiye'nin ilk uzay aracı 2026'da Ay yolculuğuna çıkacak."** aa.com.tr. → AYAP-1/AYAP-2 aşama tanımları; AYAP-2'de rover yumuşak iniş.
- **Güncel takvim kayması:** Bakan Kacır açıklaması (2025) — AYAP-1 sert iniş 2027 başına kaydı (cioupdate.com.tr; ahaber.com.tr). → Rover içeren AYAP-2 daha sonrasında.
**10.2 — TÜBİTAK UZAY**
- **TÜBİTAK UZAY — AYAP-1 Bilimsel Çalışma Grubu (2024).** uzay.tubitak.gov.tr. → AYAP-1 Proje Yöneticisi Dr. Burak Yağlıoğlu; bilimsel çıktılar Dr. Fahri Öztürk. → LunaPath'i Türkiye bağlamına bağlamak için: AYAP-2 rover'ı gelecekte kutup/traverse planlaması gerektirecektir; LunaPath bu yeteneğin öğrenci-seviyesi öncülüdür.
- **Görüntü destekli seyrüsefer:** TÜBİTAK UZAY görüntü-tabanlı navigasyon ve uydu görüntü işleme çalışmaları (kamuya açık yayın envanteri sınırlı).
**10.3 — Türkiye akademik yayınları:** Ay rover navigasyonu/uzay robotiği alanında Türkiye-merkezli hakemli yayın **görece azdır** (bu bir bulgudur). Terramekanik, rocker-bogie ve gezegen robotiği üzerine üniversite tezleri mevcuttur ama Ay-kutbu traverse planlaması özelinde ulusal literatür zayıftır. → LunaPath bu boşlukta özgün konumlanabilir.
 
**LunaPath için çıkarım (10):** Projeyi **AYAP-2 rover hedefinin öncülü** olarak konumlandırın — ulusal program açıkça bir yüzey gezicisi hedefliyor ve traverse planlama bu görevin çekirdek yeteneğidir. Türkiye'de bu alanda literatürün zayıf olması, LunaPath'in özgünlük argümanını güçlendirir; raporda bunu açıkça belirtin.
 
---
 
## Recommendations (Öncelik Sırasıyla, Eşiklerle)
 
**Aşama 1 — Hemen yapılabilir, en yüksek getiri (jüriden önce):**
1. **Gölge modelini ufuk-maskesine çevirin** (Mazarico 2011 yöntemi, aynı LOLA DEM'den). Yapılamıyorsa en azından "vekil formül vs. horizon-mask" küçük karşılaştırması yapıp farkı raporlayın. *Değişim eşiği: horizon-mask ile vekil formül arasında anlamlı (>%10) gölge-alan farkı çıkarsa vekil formül terk edilmeli.*
2. **NASA-STD-7009 CAS'ı raporun omurgası yapın**: her bilinen zayıflığı CAS faktörü altında dürüstçe listeleyin. Bu, zayıflıkları güce çevirir.
3. **Radyasyonu kriter yapMAyın**; bunu Bölüm 6'daki gerekçeyle (TID <1 krad << tolerans; MoonRanger, Mazur) bilinçli kapsam kararı olarak savunun.
**Aşama 2 — Orta vadeli (mümkünse finalden önce):**
4. **Zamanı planlama eksenine ekleyin** (time-expanded grid). Bu mümkün değilse, planın hangi "zaman epoch"u için geçerli olduğunu ve gölgelerin hareket ettiğini açıkça belirtin.
5. **Termal modele τ (zaman sabiti) + Diviner girdisi** ekleyin; sabit +60°C ofseti terk edin.
6. **DTE haberleşme görünürlük maskesi** ekleyin (aynı horizon-mask altyapısı). En azından "DTE-gölgesinde süre" metriğini raporlayın.
7. **AHP'yi savunun:** CR<0.10, geometrik ortalama (çoklu-uzmansa), ağırlık duyarlılık analizi (±%10–20 pertürbasyon → rota stabilitesi).
 
**Aşama 3 — Değerlendirme metodolojisi:**
8. **Monte Carlo mission-success-rate** (Lamarre et al. şablonu); baseline = naif en-kısa-yol + eğim-only. *Eşik: risk-bounded plan, baseline'a göre başarı oranını ölçülebilir biçimde artırmalı.*
9. **RCSP genişletmesinde admissible heuristic'i koruyun** (CSA*).
10. **Küçük RTM + TRL öz-değerlendirmesi** (muhtemelen TRL 3–4) ekleyin.
 
---
 
## Caveats (Sınırlar ve Belirsizlikler)
- **Erişim:** Icarus/JGR/Science makalelerinin çoğu paywall'dur; ancak ADS, ResearchGate ve arXiv preprint'leri genellikle açık kopya sunar. LOLA (PDS), Diviner (PDS), CRaTER (PDS), NTRS ve arXiv **tam açık erişimdir**.
- **Radyasyon negatif sonucu çıkarımsaldır:** "Robotik rover rotasını radyasyona göre optimize eden çalışma yok" bulgusu, literatürde radyasyonun *yokluğundan* + açık tasarım ifadelerinden (MoonRanger, patent) çıkarılmıştır; "radyasyon rota kriteri olmamalı" diyen tek bir tez makalesi yoktur. Bu gerçek bir boşluktur ve tezinizi destekler.
- **LND doz değerleri solar-minimum GCR'dir** (SPE yakalanmadı); bir SPE dozu mertebelerce artırır — ama bu bile robotik için ekranlama/zamanlama problemidir, rota değil.
- **VIPER iptal edildi (Temmuz 2024)** ama traverse planlama literatürü ve veri ürünleri geçerliliğini korur; VIPER hâlâ en iyi belgelenmiş kutup-rover ConOps'udur.
- **Türkiye akademik literatürü zayıf:** Ay-kutbu traverse planlaması özelinde ulusal hakemli yayın azlığı bir bulgudur, arama eksikliği değil.
- **Simülant mekanik özellikleri** (JSC-1A, LHS-1, GRC-1) simülanttan simülanta ve parti-partiye değişir; tek bir "Ay regoliti" parametre seti yoktur — LunaPath terramekanik parametrelerini seçerken belirsizlik aralığı raporlamalı.
- **Aydınlanma yüzdeleri kaynak ve çözünürlüğe göre değişir:** Kaguya (Noda) güney kutbu için ~%86, Clementine (Bussey) >%70 alanları "birkaç yüz metrekare" olarak verir, Gläser 20 m DTM ile CR1'de %80 (2 m panelle) bulur. Çözünürlük arttıkça "en aydınlık" alanlar küçülür — LunaPath bu duyarlılığı hesaba katmalıdır.