# LunaPath Nedir?

> Bu dosya diğer her şeyin çerçevesi. Bir feature dosyasını okumadan önce buraya bakmak, o feature'ın neden var olduğunu anlamayı çok kolaylaştırır.

---

## Tek cümlede

**LunaPath, Ay'ın güney kutbunda bir keşif aracının (rover) A noktasından B noktasına nasıl gitmesi gerektiğine karar veren ve bu kararın gerekçesini rakamla açıklayabilen bir rota planlama sistemidir.**

---

## Hangi problemi çözüyor?

Dünya'da bir navigasyon uygulaması açtığınızda sorun basittir: yollar bellidir, trafik verisi vardır, benzin istasyonu her yerdedir ve yanlış yola girerseniz U dönüşü yaparsınız.

Ay'ın güney kutbunda hiçbiri geçerli değil:

| Dünya'da | Ay güney kutbunda |
|---|---|
| Yol var | Yol yok — her yer ham arazi |
| GPS var | GPS yok, pusula yok (manyetik alan yok) |
| Gece 12 saat | Gölge kesintisiz **günlerce** sürebilir |
| Sıcaklık ±40 °C | Yüzey sıcaklığı **+80 °C ile −180 °C** arası |
| Yakıt her yerde | Enerji sadece **güneş panelinden** gelir |
| Anında yardım çağırırsın | Dünya ufkun altındayken **komut gönderilemez** |
| Yanlış giderseniz dönersiniz | Batarya biterse **araç ölür, geri gelmez** |

Yani Ay'da "en kısa yol" diye bir şey yoktur. **En kısa yol, aracı öldüren yol olabilir.** Çünkü kısa yol gölgeden geçiyorsa, araç güneş göremez; güneş göremezse şarj olamaz; şarj olamazsa ısıtıcısını çalıştıramaz; ısıtıcı durursa batarya donar ve araç bir daha açılmaz.

LunaPath'in çözdüğü problem tam olarak budur: **hayatta kalmayı da hesaba katan bir rota bulmak.**

---

## Analoji: Kutup yürüyüşü

LunaPath'i anlamanın en kolay yolu şu:

> Kutupta, kışın, sırtınızda sınırlı şarjı olan bir elektrikli battaniyeyle yürüyorsunuz. Battaniye ancak güneş gördüğünüzde şarj oluyor. Güneş gündüz bile ufkun hemen üstünde, o yüzden her tepe uzun gölgeler yapıyor. Telsiziniz sadece belli saatlerde merkezi görüyor; o saatlerin dışında kimseden yardım isteyemezsiniz. Ve şu kural var: **kesintisiz 50 saatten fazla gölgede kalırsanız donarsınız.**
>
> Şimdi size "şu tepenin arkasındaki vadiye git" desem, siz sadece haritaya bakıp en kısa çizgiyi çizmezsiniz. Şunları düşünürsünüz:
> - Bu yol ne kadar dik? Kayar mıyım?
> - Yolda ne kadar gölgede kalacağım?
> - Battaniyem yeter mi, yoksa yolda bir yerde durup güneş beklemem mi gerek?
> - Bir sorun çıkarsa en yakın kulübe (sığınak) kaç saat uzakta?
> - Telsizim kapanmadan önce güvenli bir yere varabilir miyim?

**LunaPath bu düşünme sürecinin tamamını sayısallaştırılmış hâlidir.** Bu kılavuzdaki her feature, yukarıdaki sorulardan birine cevap veren bir parçadır.

---

## Sistem üç katmandan oluşuyor

### 1. Veri katmanı — "Arazi neye benziyor?"

NASA'nın gerçek Ay verisi işlenip bir ızgaraya (grid) dönüştürülür. Her ızgara hücresi için şunlar bilinir: yükseklik, eğim, yüzey pürüzlülüğü, sıcaklık, güneş görme durumu, Dünya görme durumu.

Çalışma alanı: **Site11**, Ay güney kutbu, 500×500 hücre, hücre başına 5 metre. Yani yaklaşık 2,5 km × 2,5 km'lik bir alan.

### 2. Karar katmanı — "Hangi yoldan gitmeli?"

Veri katmanının ürettiği bilgiler bir **maliyet haritasına** çevrilir (her hücreye "buradan geçmek ne kadar kötü fikir" puanı verilir), sonra bir arama algoritması (A*) en düşük toplam maliyetli yolu bulur. Zaman boyutu da işin içine girince buna 4-D planlama denir: rover sadece nereye gideceğine değil, **ne zaman gideceğine** de karar verir.

### 3. Doğrulama katmanı — "Bu plan gerçekten güvenli mi?"

Bulunan yol simüle edilir, binlerce kez rastgele bozulmalarla test edilir, formal güvenlik kurallarına karşı denetlenir ve sonunda bir **GO / GO-WITH-RISK / NO-GO** kararı üretilir.

Üstüne bir de **AI asistanı** vardır: operatör "bu rota neden bu kadar uzun?" diye sorduğunda, sistemin kendi hesapladığı sayılara dayanarak Türkçe cevap verir — ve uyduramaz (bunun nasıl garanti altına alındığı [AI güvenlik dosyasında](../06-ai-asistani/ai-guvenlik-ve-grounding.md) anlatılıyor).

---

## LunaPath'in en ayırt edici özelliği: dürüstlük

Bu projede tekrar tekrar karşınıza çıkacak bir tasarım kararı var ve jüriye anlatırken en güçlü kozumuz bu:

**Sistem, bilmediği bir şeyi asla uydurmaz.**

Bir katman hesaplanamıyorsa (mesela gerekli veri dosyası yoksa), sistem sıfır dolu bir harita veya "her yer güvenli" gibi bir varsayılan üretmez. Bunun yerine `unavailable` etiketiyle **"bunu hesaplayamadım, sebebi şu"** der.

Ve hesaplayabildiği her katmana bir **güvenilirlik etiketi** iliştirir:

| Etiket | Anlamı |
|---|---|
| `MEASURED` | Bu gerçekten ölçülmüş NASA verisi |
| `MODEL` | Bu bir fizik modelinin çıktısı, ölçüm değil |
| `DERIVED` | Bu, başka verilerden türetilmiş |
| `SYNTHETIC` | Bu, demo amaçlı üretilmiş sahte veri |

Detayı: [Veri kaynakları ve güvenilirlik etiketleri](veri-kaynaklari-ve-etiketler.md)

---

## Jüri soruları

**S: "Bu bir simülasyon mu, gerçek bir sistem mi?"**
Gerçek NASA verisiyle çalışan gerçek bir planlama backend'i. Rover donanımı olmadığı için aracın kendisi simüle ediliyor, ama arazi verisi, güneş geometrisi, Dünya görünürlüğü — bunların hepsi gerçek ölçüm ve gerçek efemeris (gökcismi konum) verisi.

**S: "Neden Ay'ın güney kutbu?"**
Çünkü Artemis programı dâhil bütün güncel Ay misyonları oraya gidiyor. Sebebi kalıcı gölgeli krater tabanlarında su buzu olması. Ama aynı bölge navigasyon açısından en zor bölge: güneş ufka paralel geldiği için gölgeler kilometrelerce uzuyor.

**S: "Kaç tane özellik var?"**
Yaklaşık 30 alt sistem, 33 API ucu. Bunların 12 tanesi bir "özellik matrisi" kapsamında NASA/akademik kaynaklardan uyarlanmış ileri özellikler (A1, A2, A4, B1, B2, B3, B5, C3, C4, C6, D2, D3 kodlarıyla).

**S: "En zor kısım neydi?"**
Zaman boyutu. Statik bir planlayıcı "şu yoldan git" der. Ama Ay'da doğru cevap çoğu zaman **"burada dur, Güneş dönsün, sonra geç"**tir. Bunu ifade edebilmek için planlayıcının durumu (satır, sütun) değil (satır, sütun, **zaman dilimi**) olmak zorunda — bu da arama uzayını yüzlerce katına çıkarıyor.

**S: "Neyi iddia EDEMİYORSUNUZ?"**
Bunu bilmek çok önemli. Termal modelimiz kalibre edilmiş değil (`MODEL/UNCALIBRATED`). Kayma (slip) eğrimiz literatürden aktarılmış, kutup regolitinde ölçülmemiş. Pürüzlülük verisi gerçek ölçüm ama 50 m çözünürlükte, yani 5 m'lik hücrenin kendi pürüzlülüğü değil. Bu sınırlar kodda açıkça yazılı ve her API cevabıyla birlikte gidiyor.
