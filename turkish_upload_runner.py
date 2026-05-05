#!/usr/bin/env python3
"""Turkish general viral Shorts upload runner.

Generates one Turkish general viral Short, saves outputs, writes metadata before
upload, then tries YouTube upload. If upload limit is reached, the video and
metadata still stay saved in the repo. If the online text generator fails, the
runner uses built-in Turkish fallback scripts so the workflow still produces a
video.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import main
from caption_style import apply_caption_style
from thumbnail_helper import make_thumbnail

OUTPUT_DIR = Path("generated-videos")
OUTPUT_VIDEO = OUTPUT_DIR / "latest_short.mp4"
OUTPUT_THUMBNAIL = OUTPUT_DIR / "latest_thumbnail.jpg"
OUTPUT_META = OUTPUT_DIR / "latest_meta.json"
OUTPUT_FIRST_FRAME = OUTPUT_DIR / "latest_first_frame.jpg"
OUTPUT_PREVIEW_GIF = OUTPUT_DIR / "latest_preview.gif"
VIDEO_COMPAT_REPORT = OUTPUT_DIR / "video_compat_report.txt"
RUNTIME_DIR = Path("runtime-status")
RUNTIME_META = RUNTIME_DIR / "video-meta.json"
VOICE_CANDIDATE_DIR = Path("voice-candidates")

MIN_TARGET_DURATION = 30.0
MAX_TARGET_DURATION = 40.0
TARGET_DURATION = 35.0

main.DEFAULT_VOICE = "tr-TR-EmelNeural"
main.RATE = "+10%"
main.PITCH = "+0Hz"

GENERAL_NICHES = [
    "Şok Edici Psikolojik Gerçekler",
    "Bilinmeyen İnsan Davranışları",
    "Çözülememiş Tarihi Gizemler",
    "Uzayın Korkunç Sırları",
    "Günlük Hayatta Stoacı Felsefe",
    "Başarı Psikolojisi ve Motivasyon",
    "Teknolojinin Karanlık Yüzü",
    "Mitoloji ve Efsanelerin Kökenleri",
    "İnanılmaz Bilimsel Keşifler",
    "Tuhaf ve Enteresan Yasalar",
]

GENERAL_PEXELS_QUERIES = {
    "Şok Edici Psikolojik Gerçekler": ["human brain psychology", "thinking person dark", "mind concept", "neural network abstract", "person thinking cinematic"],
    "Bilinmeyen İnsan Davranışları": ["people walking city", "human behavior", "crowd slow motion", "person thinking", "urban people cinematic"],
    "Çözülememiş Tarihi Gizemler": ["ancient ruins", "old manuscript", "archaeology", "mysterious temple", "ancient history cinematic"],
    "Uzayın Korkunç Sırları": ["deep space", "galaxy stars", "black hole", "astronaut space", "space cinematic"],
    "Günlük Hayatta Stoacı Felsefe": ["ancient statue", "stoic statue", "calm person nature", "roman columns", "meditation nature cinematic"],
    "Başarı Psikolojisi ve Motivasyon": ["person running", "mountain climb", "focused work", "success motivation", "athlete training cinematic"],
    "Teknolojinin Karanlık Yüzü": ["cyber security", "phone screen dark", "data center", "hacker code", "technology dark cinematic"],
    "Mitoloji ve Efsanelerin Kökenleri": ["ancient statue", "greek temple", "ancient ruins", "mythology temple", "old sculpture cinematic"],
    "İnanılmaz Bilimsel Keşifler": ["science laboratory", "microscope", "space telescope", "scientist experiment", "laboratory cinematic"],
    "Tuhaf ve Enteresan Yasalar": ["court law", "judge gavel", "old documents", "city street rules", "law books cinematic"],
}

DEFAULT_TAGS = ["shorts", "youtubeshorts", "viral", "viralshorts", "fyp", "bilgi", "ilgincbilgiler", "turkceshorts", "shortsturkiye", "merakedilenler"]

THUMBNAIL_TEXTS = {
    "Şok Edici Psikolojik Gerçekler": "BEYNİN BUNU YAPIYOR",
    "Bilinmeyen İnsan Davranışları": "İNSANLAR NEDEN BÖYLE",
    "Çözülememiş Tarihi Gizemler": "TARİHTE GİZLİ KALDI",
    "Uzayın Korkunç Sırları": "UZAY BUNU SAKLIYOR",
    "Günlük Hayatta Stoacı Felsefe": "BUNU BİLEN SAKİN KALIR",
    "Başarı Psikolojisi ve Motivasyon": "BAŞARI BÖYLE BAŞLAR",
    "Teknolojinin Karanlık Yüzü": "TEKNOLOJİ BUNU GİZLİYOR",
    "Mitoloji ve Efsanelerin Kökenleri": "EFSANENİN KÖKENİ",
    "İnanılmaz Bilimsel Keşifler": "BİLİM BUNU DEĞİŞTİRDİ",
    "Tuhaf ve Enteresan Yasalar": "BU YASA GERÇEK",
}

FALLBACK_SCRIPTS = {
    "Şok Edici Psikolojik Gerçekler": [
        "Beyninin seni kandırdığını biliyor musun? Bir şeyi ne kadar sık duyarsan, doğru olduğuna o kadar kolay inanırsın. Psikolojide buna tanıdıklık etkisi denir. Bu yüzden reklamlar, tekrar eden sözler ve kalabalığın fikri zihninde güçlü görünür. Ama gerçek her zaman en çok duyduğun şey değildir. Bugün bir şeye inanmadan önce kendine şunu sor: Bunu biliyor muyum, yoksa sadece çok mu duydum?",
        "İnsan beyni eksik bilgiyi tamamlamaya bayılır. Birinin yüzünü, ses tonunu veya tek cümlesini görür ve hemen hikaye yazar. Çoğu kavga aslında olaydan değil, beynin eklediği anlamdan çıkar. Bu yüzden sakin kalan insan daha net görür. Bir dahaki sefere hızlı karar vermeden önce dur. Belki sorun karşındaki kişi değil, zihninin boşluğu doldurma şeklidir.",
    ],
    "Bilinmeyen İnsan Davranışları": [
        "İnsanlar neden kalabalıkta daha az yardım eder biliyor musun? Çünkü herkes sorumluluğu başkasına bırakır. Buna seyirci etkisi denir. Etrafta ne kadar çok kişi varsa, biri harekete geçsin diye bekleme ihtimalimiz artar. Bu yüzden gerçek farkı çoğu zaman ilk adımı atan kişi yaratır. Bir olay gördüğünde kalabalığa bakma, kendi kararına bak. Çünkü bazen tek hareket bütün sessizliği bozar.",
        "Bir insanın ne söylediğinden çok, neyi sürekli ertelediğine bak. Çünkü davranışlar, niyetlerden daha dürüsttür. İnsanlar kendilerini kelimelerle anlatır ama gerçek önceliklerini zamanlarıyla gösterir. Bu yüzden biri için önemliysen, bunu sadece sözde değil düzenli davranışta görürsün. Bugün kendine de aynı soruyu sor: Benim zamanım gerçekten neye değer verdiğimi gösteriyor mu?",
    ],
    "Çözülememiş Tarihi Gizemler": [
        "Tarihte bazı olaylar vardır, üzerinden yüzyıllar geçse de tek bir net cevap bulunamaz. Kayıp koloniler, çözülemeyen yazıtlar ve aniden yok olan topluluklar bize şunu hatırlatır: Geçmiş tamamen bitmiş değildir. Toprağın altında, eski belgelerde ve unutulmuş haritalarda hâlâ cevap bekleyen izler var. Belki de tarih, bize anlatılandan çok daha karmaşık. Bir sonraki gizemde hangi parçanın eksik olduğunu düşün.",
        "Eski uygarlıkların bazı yapıları bugün bile şaşırtıcı. Dev taşlar, kusursuz hizalanmış tapınaklar ve bilinmeyen amaçlarla yapılmış odalar var. Bazen teknoloji değil, sabır ve gözlem gücü bizi şaşırtıyor. Ama asıl soru şu: Bu insanlar neyi biliyordu da biz hâlâ tam anlayamıyoruz? Tarihe sadece geçmiş diye bakma. Belki de bazı cevaplar geleceği anlamak için saklandı.",
    ],
    "Uzayın Korkunç Sırları": [
        "Uzay sessiz görünür ama aslında akıl almaz güçlerle doludur. Bir kara deliğin yakınında zaman bile farklı akar. Yıldızlar doğar, patlar ve bütün gezegenleri yok edebilir. Biz ise küçücük bir gezegende, bu dev karanlığın içinde yaşıyoruz. Korkutucu olan boşluk değil, ne kadar az şey bildiğimiz. Gökyüzüne baktığında sadece yıldız görme; orada hâlâ cevaplanmamış büyük sorular var.",
        "Evrenin büyük kısmını göremiyoruz. Bilim insanları karanlık madde ve karanlık enerji olduğunu söylüyor ama tam olarak ne olduklarını bilmiyoruz. Yani gördüğümüz yıldızlar, galaksiler ve gezegenler evrenin sadece küçük bir parçası. Asıl büyük sahne görünmez durumda. Bu düşünce ürkütücü ama büyüleyici. Belki de evrenin en büyük sırrı uzaklarda değil, göremediğimiz şeylerde saklı.",
    ],
    "Günlük Hayatta Stoacı Felsefe": [
        "Şunu biliyor musun? Seni yoran şey çoğu zaman olayın kendisi değil, ona verdiğin anlamdır. Stoacılar bunu yüzyıllar önce fark etti. Kontrol edemediğin şeyi zorladıkça zihnin yorulur. Ama kendi tepkini seçtiğinde güç geri gelir. Bugün biri seni sinirlendirirse hemen cevap verme. Önce dur, nefes al ve şunu sor: Bu benim kontrolümde mi? Cevap hayırsa, enerjini geri al.",
        "Her gün aynı sorunlarla karşılaşıyor gibi hissedebilirsin. Ama stoacı bakış şunu söyler: Hayat sana olayları seçtirmez, fakat duruşunu seçtirir. Küçük bir gecikme, sert bir söz veya beklenmedik bir kayıp seni tamamen yönetmek zorunda değil. Sakinlik doğuştan gelen bir özellik değildir, pratik edilen bir beceridir. Bugün sadece bir olayda daha az tepki ver. Bazen en büyük zafer budur.",
    ],
    "Başarı Psikolojisi ve Motivasyon": [
        "Başarının en gizli tarafı motivasyon değildir, tekrar gücüdür. Motivasyon gelir ve gider. Ama küçük alışkanlıklar sessizce karakterini değiştirir. Her gün sadece biraz daha iyi olmak, uzun vadede büyük fark yaratır. İnsanlar sonucu görünce şans sanır, ama görünmeyen yerde yüzlerce küçük seçim vardır. Bugün büyük bir plan yapma. Sadece yarın da tekrarlayabileceğin küçük bir adım at.",
        "Çoğu insan başarısız olduğu için değil, erken vazgeçtiği için kaybeder. İlk denemede sonuç gelmeyince kendini yetersiz sanırsın. Oysa beyin tekrar ettikçe güçlenir. Disiplin, canın istemediğinde de doğru şeyi yapabilmektir. Başarı bazen büyük bir sıçrama değil, sıkıcı görünen bir rutine sadık kalmaktır. Bugün kendine şunu sor: Ben sonucu mu istiyorum, yoksa sürece dayanabilecek miyim?",
    ],
    "Teknolojinin Karanlık Yüzü": [
        "Telefonun seni dinliyor mu sorusu kadar önemli bir soru daha var: Sen ona ne kadar veri veriyorsun? Her tıklama, bekleme süren, izlediğin video ve geçtiğin reklam bir profile dönüşür. Teknoloji seni anlamaya çalışmaz; davranışını tahmin etmeye çalışır. En korkutucu taraf kameralar değil, alışkanlıklarının ölçülmesi. Bugün bir uygulamayı açmadan önce sor: Bunu ben mi seçtim, yoksa bana mı seçtirildi?",
        "Algoritmalar sadece ne izlediğini değil, ne zaman zayıf olduğunu da öğrenir. Yorgunken, sıkılmışken veya yalnızken ekrana daha uzun bakarsın. Platformlar bunu ölçer ve seni tutacak içerikleri öne çıkarır. Bu yüzden teknoloji bazen araç gibi değil, görünmez bir alışkanlık yöneticisi gibi çalışır. Kontrolü geri almak istiyorsan bildirimleri azalt. Küçük bir ayar, dikkatini geri kazanmanın ilk adımı olabilir.",
    ],
    "Mitoloji ve Efsanelerin Kökenleri": [
        "Mitolojiler sadece eski masallar değildir. İnsanların korkularını, umutlarını ve doğayı anlama çabasını taşır. Gök gürültüsü bir tanrının öfkesi, deniz fırtınası bir yaratığın nefesi gibi anlatılırdı. Çünkü insan bilmediği şeye hikaye vererek dayanır. Bugün bile modern dünyada aynı şeyi yapıyoruz. Sadece tanrıların yerini teoriler, semboller ve kahramanlar aldı. Belki efsaneler geçmiş değil, insan zihninin aynasıdır.",
        "Neredeyse her kültürde büyük tufan, kahraman yolculuğu ve yasak bilgi anlatıları vardır. Bu benzerlik tesadüf mü, yoksa insanların ortak korkularından mı doğdu? Mitoloji bize şunu gösterir: İnsan değişse de temel soruları aynı kalır. Nereden geldik, neden acı çekiyoruz, ölümden sonra ne var? Efsaneler cevap vermek için değil, bu soruları taşıyabilmek için ortaya çıkmış olabilir.",
    ],
    "İnanılmaz Bilimsel Keşifler": [
        "Bilimde en büyük keşifler bazen bir hata gibi başlar. Yanlış sonuç, beklenmeyen leke veya tutmayan deney yeni bir kapı açabilir. Çünkü bilim sadece doğru cevabı bulmak değil, şaşırmayı ciddiye almaktır. Bugün kullandığımız birçok teknoloji, birinin garip görünen bir sonucu çöpe atmaması sayesinde gelişti. Bu yüzden merak küçük görünse de dünyayı değiştirebilir. Bir soruyu önemsemek, bazen keşfin ilk adımıdır.",
        "İnsanlık mikroskobun altında görünmeyen canlıları, teleskobun arkasında uzak galaksileri keşfetti. Her yeni araç bize şunu gösterdi: Dünya sandığımızdan daha büyük ve daha karmaşık. Bilimin gücü, kesin bildiğini sanmak değil, yanılabileceğini kabul etmektir. Bu yüzden gerçek keşif sadece laboratuvarda olmaz. Bir şeye yeniden bakmaya cesaret ettiğinde, kendi zihninde de yeni bir evren açılır.",
    ],
    "Tuhaf ve Enteresan Yasalar": [
        "Dünyada bazı yasalar o kadar tuhaf ki şaka gibi görünür. Ama çoğu, geçmişte yaşanmış garip bir olaydan sonra ortaya çıkmıştır. Bir şehirde sessizlik, başka bir yerde hayvanlar, başka bir ülkede günlük davranışlar yasa konusu olabilir. Hukuk sadece adalet değil, toplumların korkularını ve alışkanlıklarını da gösterir. Bir yasa sana saçma geliyorsa, arkasında unutulmuş bir hikaye olabilir. Bazen en garip kurallar, en ilginç tarihi saklar.",
        "Bazı ülkelerde sıradan davranışlar bile beklenmedik kurallara bağlanmıştır. Parkta ne yaptığın, sokakta nasıl davrandığın veya hangi saatte gürültü çıkardığın ceza sebebi olabilir. Bu yasalar bize şunu gösterir: Normal dediğimiz şey her yerde aynı değildir. Kültür değişince kurallar da değişir. Seyahat ederken sadece haritaya değil, alışkanlıklara da dikkat et. Çünkü bazen en küçük davranış bile başka yerde büyük anlam taşır.",
    ],
}


def clean_script(text: str) -> str:
    text = re.sub(r"[*#_`>\[\]{}]", "", text or "")
    text = re.sub(r"(?i)^(senaryo|metin|cevap|script|text|answer)\s*:\s*", "", text.strip())
    return re.sub(r"\s+", " ", text).strip().strip('"').strip("'")


def build_prompt(niche: str) -> str:
    return f"""
Sen viral YouTube Shorts metinleri yazan bir uzmansın.
Konu: {niche}
Aşağıdaki kurallara uygun, 30-40 saniyelik bir TÜRKÇE metin yaz:
1. İlk cümle şok edici bir soru veya çarpıcı bir gerçekle başlamalı.
2. Orta kısımda kısa, vurucu cümlelerle ilginç bilgiler ver.
3. Son cümle güçlü bir call-to-action içersin.
4. Emoji, sahne yönü, efekt YOK. Sadece konuşulacak metin.
Yalnızca metni döndür.
""".strip()


def fallback_script(niche: str) -> str:
    options = FALLBACK_SCRIPTS.get(niche) or [script for scripts in FALLBACK_SCRIPTS.values() for script in scripts]
    script = clean_script(random.choice(options))
    main.logger.warning("Using built-in fallback Turkish script for niche: %s", niche)
    return script


def generate_script(niche: str) -> str:
    prompt = build_prompt(niche)
    best_script = ""
    best_distance = 10_000

    try:
        from g4f.client import Client
        client = Client()
    except Exception as exc:
        main.logger.warning("g4f client unavailable; using fallback script: %s", exc)
        return fallback_script(niche)

    for attempt in range(4):
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                timeout=60,
            )
            script = clean_script(response.choices[0].message.content)
            words = len(script.split())
            distance = min(abs(words - 52), abs(words - 82)) if not 52 <= words <= 82 else 0
            if script and distance < best_distance:
                best_script = script
                best_distance = distance
            if 52 <= words <= 82:
                return script
            main.logger.warning("Script word count off target: %d; retrying", words)
        except Exception as exc:
            main.logger.warning("Online script generation failed on attempt %d; retrying/fallback: %s", attempt + 1, exc)

    if best_script and len(best_script.split()) >= 45:
        main.logger.warning("Using closest online script after retries: %d words", len(best_script.split()))
        return best_script
    return fallback_script(niche)


def _reset_voice_candidates() -> None:
    VOICE_CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in VOICE_CANDIDATE_DIR.glob("voiceover_candidate_*.mp3"):
        try:
            old_file.unlink()
        except OSError:
            pass


def _copy_selected_voiceover(candidate_audio: str) -> str:
    """Freeze the selected candidate into the canonical voiceover.mp3 path."""
    target = Path(main.VOICEOVER_FILE)
    source = Path(candidate_audio)
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    return str(target)


async def choose_best_timed_script(niche: str):
    _reset_voice_candidates()
    candidates = []

    for idx in range(6):
        script = generate_script(niche)
        audio, word_ts = await main.create_voiceover(script)

        candidate_audio = VOICE_CANDIDATE_DIR / f"voiceover_candidate_{idx:02d}.mp3"
        shutil.copyfile(audio, candidate_audio)

        clip = main.AudioFileClip(str(candidate_audio))
        duration = float(clip.duration)
        clip.close()

        candidate = (abs(TARGET_DURATION - duration), script, str(candidate_audio), word_ts, duration)
        candidates.append(candidate)
        main.logger.info(
            "Voice candidate %02d: duration=%.2fs words=%d file=%s",
            idx,
            duration,
            len(script.split()),
            candidate_audio,
        )

        if MIN_TARGET_DURATION <= duration <= MAX_TARGET_DURATION:
            _, selected_script, selected_audio, selected_ts, selected_duration = candidate
            selected_audio = _copy_selected_voiceover(selected_audio)
            main.logger.info("Selected voice candidate %02d without later overwrite.", idx)
            return selected_script, selected_audio, selected_ts, selected_duration

    candidates.sort(key=lambda row: row[0])
    _, selected_script, selected_audio, selected_ts, selected_duration = candidates[0]
    selected_audio = _copy_selected_voiceover(selected_audio)
    main.logger.info("Selected closest voice candidate and restored matching audio file.")
    return selected_script, selected_audio, selected_ts, selected_duration


def title_and_thumbnail(niche: str, script: str):
    first = re.split(r"[.!?]", script)[0].strip()
    return f"{first[:82]} #shorts", THUMBNAIL_TEXTS.get(niche, "BUNU BİLİYOR MUYDUN")


def build_tags(niche: str):
    niche_tags = {
        "Şok Edici Psikolojik Gerçekler": ["psikoloji", "beyin", "insanpsikolojisi"],
        "Bilinmeyen İnsan Davranışları": ["insandavranisi", "psikoloji", "sosyoloji"],
        "Çözülememiş Tarihi Gizemler": ["tarih", "gizem", "tarihgizemleri"],
        "Uzayın Korkunç Sırları": ["uzay", "evren", "bilim"],
        "Günlük Hayatta Stoacı Felsefe": ["stoacilik", "felsefe", "hayatdersleri"],
        "Başarı Psikolojisi ve Motivasyon": ["motivasyon", "basari", "disiplin"],
        "Teknolojinin Karanlık Yüzü": ["teknoloji", "yapayzeka", "siber"],
        "Mitoloji ve Efsanelerin Kökenleri": ["mitoloji", "efsane", "tarih"],
        "İnanılmaz Bilimsel Keşifler": ["bilim", "kesif", "bilgiler"],
        "Tuhaf ve Enteresan Yasalar": ["yasalar", "ilginc", "dunya"],
    }
    out = []
    for tag in DEFAULT_TAGS + niche_tags.get(niche, []):
        if tag not in out:
            out.append(tag)
    return out[:15]


def run_cmd(args, check=True):
    main.logger.info("$ " + " ".join(str(x) for x in args))
    return subprocess.run(args, check=check, text=True, capture_output=True)


def prepare_background_for_editing(input_path: str, duration: float) -> str:
    prepared = Path("background_prepared.mp4")
    if prepared.exists():
        prepared.unlink()
    dur = max(float(duration) + 0.75, MIN_TARGET_DURATION)
    run_cmd([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(input_path),
        "-t", f"{dur:.2f}",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(prepared),
    ])
    return str(prepared)


def normalize_mp4_for_mobile(input_path: str, output_path: Path) -> None:
    tmp = output_path.with_suffix(".tmp.mp4")
    if tmp.exists():
        tmp.unlink()
    run_cmd([
        "ffmpeg", "-y", "-i", str(input_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "main", "-level", "4.0",
        "-movflags", "+faststart",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(tmp),
    ])
    tmp.replace(output_path)


def make_debug_previews(video_path: Path) -> None:
    run_cmd(["ffmpeg", "-y", "-ss", "00:00:02", "-i", str(video_path), "-frames:v", "1", str(OUTPUT_FIRST_FRAME)], check=False)
    run_cmd(["ffmpeg", "-y", "-ss", "00:00:00", "-t", "6", "-i", str(video_path), "-vf", "fps=8,scale=360:-1:flags=lanczos", str(OUTPUT_PREVIEW_GIF)], check=False)
    probe = run_cmd(["ffprobe", "-v", "error", "-show_entries", "format=format_name,duration,size:stream=codec_name,codec_type,pix_fmt,width,height", "-of", "json", str(video_path)], check=False)
    VIDEO_COMPAT_REPORT.write_text(probe.stdout or probe.stderr or "ffprobe produced no output", encoding="utf-8")


def write_meta(meta: dict) -> None:
    OUTPUT_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


async def run() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    apply_caption_style(main)
    main.NICHE_POOL = GENERAL_NICHES
    main.NICHE_PEXELS_QUERIES = GENERAL_PEXELS_QUERIES

    niche = random.choice(GENERAL_NICHES)
    script, audio, word_ts, duration = await choose_best_timed_script(niche)
    chunked = main.chunk_timestamps(word_ts)
    bg = main.fetch_background_video(script, niche)
    bg = prepare_background_for_editing(bg, duration)
    music = "bg_music.mp3" if main.os.path.exists("bg_music.mp3") else None
    final_path = main.assemble_video(bg, audio, chunked, music)

    title, thumbnail_text = title_and_thumbnail(niche, script)
    tags = build_tags(niche)

    normalize_mp4_for_mobile(final_path, OUTPUT_VIDEO)
    make_debug_previews(OUTPUT_VIDEO)

    thumb_path = make_thumbnail(str(OUTPUT_VIDEO), thumbnail_text, main.ensure_font(), main.logger)
    if thumb_path and Path(thumb_path).exists():
        shutil.copyfile(thumb_path, OUTPUT_THUMBNAIL)

    description = f"{niche} hakkında çarpıcı gerçekler ve ilginç bilgiler.\nHer gün yeni Shorts için takipte kal.\n\n#shorts #bilgi #ilgincbilgiler #turkceshorts"
    meta = {
        "mode": "turkish_general_viral_youtube_upload_with_safe_metadata",
        "language": "tr",
        "voice": main.DEFAULT_VOICE,
        "prompt_style": "general_viral_turkish_quality_guard_with_offline_fallback",
        "niche": niche,
        "caption_style": {
            "font_size": 60,
            "stroke_width": 5,
            "max_words": 1,
            "position": "center",
            "punctuation_removed": True,
            "spaces_removed_inside_caption_word": True,
            "timing": "edge_wordboundary_or_pause_aware_audio_fallback",
        },
        "title": title,
        "thumbnail_text": thumbnail_text,
        "duration_seconds": round(duration, 2),
        "tags": tags,
        "background_queries": GENERAL_PEXELS_QUERIES.get(niche, []),
        "script": script,
        "description": description,
        "video_path": str(OUTPUT_VIDEO),
        "thumbnail_path": str(OUTPUT_THUMBNAIL) if OUTPUT_THUMBNAIL.exists() else None,
        "first_frame_path": str(OUTPUT_FIRST_FRAME) if OUTPUT_FIRST_FRAME.exists() else None,
        "preview_gif_path": str(OUTPUT_PREVIEW_GIF) if OUTPUT_PREVIEW_GIF.exists() else None,
        "compat_report_path": str(VIDEO_COMPAT_REPORT) if VIDEO_COMPAT_REPORT.exists() else None,
        "video_url": None,
        "upload_status": "not_attempted",
        "upload_error": None,
    }
    write_meta(meta)

    try:
        video_url = main.upload_to_youtube(str(OUTPUT_VIDEO), title, description, tags)
        meta["video_url"] = video_url
        meta["upload_status"] = "success"
        main.logger.info(f"Published video: {video_url}")
    except Exception as exc:
        meta["upload_status"] = "failed"
        meta["upload_error"] = str(exc)
        main.logger.error(f"YouTube upload failed but video is saved: {exc}")
    finally:
        write_meta(meta)


if __name__ == "__main__":
    asyncio.run(run())
