# Kaynak / Attribution

Bu klasördeki pipeline, MIT lisanslı açık kaynak projeden uyarlanmıştır:

- Orijinal: **FreeFaceless** — https://github.com/nils44344/FreeFaceless
- Lisans: **MIT** (kullanmaya, çatallamaya, değiştirmeye izin verir)
- Altyazı fontu (orijinal): **Anton**, SIL Open Font License

Türkçe uyarlamada değişenler (orijinal mantık aynı):

1. `config.yaml` — Türkçe 10 niş, `tr-TR-EmelNeural` ses (`+10%` hız),
   hedef süre 35 sn, caption `words_per_caption: 1`, font `DejaVu Sans`
   (Türkçe karakter desteği; ubuntu runner'da hazır).
2. `src/script.py` — system prompt Türkçe; konuşma metni Türkçe,
   `visual_query` alanları Pexels için İngilizce kalır.
3. `src/upload.py` — yerelde tarayıcı-OAuth akışı aynen durur;
   ek olarak CI için `YOUTUBE_REFRESH_TOKEN` + `CLIENT_SECRETS_JSON`
   ortam değişkenleri desteklenir (bu repodaki `main.py` ile aynı yöntem).
4. `src/assemble.py` — `assets/fonts` klasörü yoksa `fontsdir` parametresi
   atlanır (orijinalde klasörün varlığı varsayılırdı).
5. `src/pipeline.py` — `--niche "..."` argümanı: 10 nişten birine zorlamak için.
6. `src/comments.py` — moderasyon yanıtları Türkçe, tek kısa cümle.
