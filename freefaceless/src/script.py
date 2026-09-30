import json
import re
import os
from .groq_client import chat_json
from .config import GROQ_API_KEY, GROQ_BASE_URL, CONFIG
from . import state
from .quality import validate_and_prepare

os.environ.setdefault("GROQ_MODEL", CONFIG["script"]["model"])

# Denede adina uygun, geniş merak alanları. Günlük akış bunları dönüşümlü kullanır.
TURKISH_NICHES = [
    "Psikoloji ve insan davranışları",
    "Günlük hayatta bilimin açıklamaları",
    "Uzay ve astronomi",
    "Hayvanlar ve doğa",
    "Teknoloji, yapay zekâ ve icatlar",
    "Tarih ve arkeoloji",
    "Coğrafya ve dünyadaki sıra dışı yerler",
    "Diller, kelimelerin kökeni ve iletişim",
    "Kültürler, gelenekler ve gündelik yaşam",
    "Yemeklerin ve nesnelerin şaşırtıcı kökenleri",
    "Mitoloji ve efsanelerin gerçek kökenleri",
    "Matematik ve mantık paradoksları",
    "Denizler, hava olayları ve Dünya",
    "Günlük eşyalar nasıl çalışır",
    "Doğrulanabilir sıra dışı kurallar ve tarihî olaylar",
]

SYSTEM = """Denede adlı Türkçe merak ve bilgi kanalına YouTube Shorts senaryosu yaz.
Amaç: izleyiciyi ilk anda durdurmak, merakını dürüstçe artırmak ve videonun sonunda verdiğin
vaadi karşılamak. İzlenme/keşif garantisi veya algoritma hakkında kesin iddia verme.

KONU:
- Verilen geniş alana bağlı, tek ve somut bir olgu seç. Kanal yalnızca gizem/psikoloji içermez;
  bilim, doğa, uzay, teknoloji, tarih, coğrafya, kültür ve gündelik yaşam arasında çeşitlendir.
- Son 50 videonun konularını ve benzer açılarını tekrarlama.
- Zamana duyarlı haber, kaynağı belirsiz istatistik, uydurma alıntı, sağlık/hukuk/finans tavsiyesi,
  doğrulanmamış yasa ve kesin olmayan iddiayı kullanma. Emin olunmayan olguyu seçme.
- Başlıkta açtığın merak boşluğu senaryoda açık ve tatmin edici biçimde kapansın.

KONUŞMA METNİ:
- 65-78 Türkçe kelime; hedef ses süresi yaklaşık {target_seconds} saniye.
- 5-7 kısa sahne; ilk sahnenin ilk kelimeleri doğrudan güçlü hook olsun. Selam, intro ve
  “bugün anlatacağım” yok.
- İlk 1-2 saniyede konuya özgü, somut bir merak kancası kur: şaşırtıcı ama doğru bir bilgi,
  güçlü bir soru, beklenmedik karşılaştırma veya gündelik bir alışkanlığa ters açı. Her videoda
  farklı bir hook biçimi seç; “şok olacaksın”, “inanamayacaksın” gibi boş kalıpları kullanma.
  Tıklama vaadini mutlaka videoda karşıla; olgu, sayı, alıntı veya sonucu uydurma.
- İlk 2 sahnede ana konu/varlığın adı geçsin ve izleyici neden izlemeyi sürdürmesi gerektiğini anlasın.
- Retention akışı kur: ilk sahnede merak boşluğu, sonraki sahnelerde her seferinde yeni ve kısa bir
  ipucu, orta bölümde açıklama/ters köşe, son sahnede net cevap ve tatmin edici payoff. Yanıtı
  gereksiz yere saklama; dolgu, tekrar ve konu dışı cümle kullanma. Her cümle bir sonrakine merak taşısın.
- Son cümlede izleyiciye konuya özel, kolay cevaplanır tek soru sor ve doğal, kısa bir
  “Denede için abone ol” çağrısı ekle. Genel “beğen-abone ol” listesi yazma.
- Emoji, sahne talimatı, efekt, kaynak, kaynakça, site adı, URL, markdown, hashtag ve madde işareti yok.
- Sayıları konuşmada Türkçe sözcüklerle yaz; birim ve kısaltmaları da okunuşuyla ver.
- text alanlarında noktalama işareti kullanma; yalnızca doğrudan seslendirilecek temiz Türkçe kelimeleri yaz.
- Kanal adı yalnızca son sahnedeki tek CTA içinde geçsin; CTA veya başka cümleyi tekrarlama.
- Her sahnenin visual_query alanı Pexels'te aranabilir 2-4 küçük harfli ASCII İngilizce görsel sözcük; Türkçe karakter yok olsun.
  Soyut kavram yerine konuya özgü görülebilir kişi, yer, nesne veya eylem yaz. Aynı sorguyu tekrarlama.
  Genel "ancient history", "abstract background" veya alakasız ülke/tapınak görüntüsü isteme.

BAŞLIK:
- Türkçe, en fazla 60 karakter; konunun/nesnenin adı başlarda, tek bir net vaat ve güçlü merak boşluğu bulunsun.
- Aynı kalıbı art arda kullanma; kısa, konuşma dilinde ve videodaki belirli sonuca bağlı yaz.
- Konuya özel şaşırtıcı sonuç, meydan okuma, “neden/nasıl” ya da ters köşe açısı seç; başlığın
  verdiği vaadi senaryoda açıkça karşıla.
- Cesur ve clickbait sunum serbest; uydurma olay, sahte sayı, yanlış nedensellik veya videoda
  karşılanmayan vaat yasak. Aynı başlık kalıbını art arda tekrarlama.

AÇIKLAMA VE ETİKETLER:
- Açıklama 1-2 kısa, videoya özel cümle olsun; ilk cümlede konu adı bulunsun ve ikinci cümle
  konuya özel, kolay cevaplanır bir yorum sorusu sorarak etkileşim başlatsın.
  Videoda bulunmayan bilgi, genel SEO anahtar kelime yığını ve tekrar eden abone çağrısı ekleme.
- Açıklama tam 4 alakalı hashtag ile bitsin; bunlardan biri #shorts, diğerleri konuya özel olsun.
- 5 küçük harfli etiket üret: önce ana konu, sonra yakın alt konular; # işareti ekleme.
  #keşfet, viral, trending gibi alakasız etiket kullanma.

SADECE geçerli JSON döndür; başına veya sonuna başka metin ekleme. Şema:
{{
  "topic": "kısa, tekrar denetimine uygun konu adı",
  "title": "en fazla 60 karakter Türkçe başlık",
  "description": "konuya özel 1-2 cümle ve tam 4 hashtag",
  "tags": ["5 küçük harfli, konuya özel etiket"],
  "scenes": [
    {{"text": "seslendirilecek Türkçe cümle", "visual_query": "2-4 English visual words"}}
  ]
}}"""


def _system_prompt():
    return SYSTEM.format(target_seconds=CONFIG["script"]["target_seconds"])


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("Yanıt JSON içermiyor")


def _normalize_description_hashtags(description: str, topic: str) -> str:
    """Keep Groq's copy, but enforce the upload contract with topic-relevant tags."""
    hashtag_pattern = r"(?<!\w)#[\wçğıöşüÇĞİÖŞÜ]+"
    existing = re.findall(hashtag_pattern, description, flags=re.UNICODE)
    body = re.sub(hashtag_pattern, " ", description, flags=re.UNICODE)
    body = re.sub(r"\s+", " ", body).strip()

    chosen: list[str] = []
    seen: set[str] = set()
    for tag in existing:
        if tag.lower() == "#shorts":
            continue
        key = tag.casefold()
        if key not in seen and len(chosen) < 3:
            chosen.append(tag)
            seen.add(key)

    topic_words = re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", topic, flags=re.UNICODE)
    defaults = [f"#{topic_words[0].capitalize()}" if topic_words else "#Bilgi", "#Merak", "#Bilgi", "#Denede"]
    for tag in defaults:
        if len(chosen) == 3:
            break
        if tag.casefold() not in seen:
            chosen.append(tag)
            seen.add(tag.casefold())

    suffix = " ".join(["#shorts", *chosen])
    return f"{body}\n\n{suffix}" if body else suffix


def _validate_package(data: dict) -> dict:
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 5 <= len(scenes) <= 7:
        raise ValueError("scenes 5-7 sahne olmalı")
    if any(not isinstance(s, dict) or not s.get("text") or not s.get("visual_query") for s in scenes):
        raise ValueError("Her sahnede text ve visual_query gerekli")
    title = str(data.get("title", "")).strip()
    if not title or len(title) > 60:
        raise ValueError("Başlık boş veya 60 karakterden uzun")
    tags = data.get("tags")
    if not isinstance(tags, list) or len(tags) != 5 or any(not isinstance(t, str) or not t.strip() or "#" in t for t in tags):
        raise ValueError("Tam 5 adet # işaretsiz etiket gerekli")
    description = str(data.get("description", "")).strip()
    hashtags = re.findall(r"(?<!\w)#[\wçğıöşüÇĞİÖŞÜ]+", description, flags=re.UNICODE)
    if len(hashtags) != 4 or "#shorts" not in {h.lower() for h in hashtags}:
        raise ValueError("Açıklamada #shorts dahil tam 4 hashtag olmalı")
    if len({h.casefold() for h in hashtags}) != 4:
        raise ValueError("Hashtagler tekrar etmemeli; aynı Groq modeli düzeltmeli")
    data["title"] = title
    data["description"] = description
    data["tags"] = [t.strip().lower() for t in tags]
    data = validate_and_prepare(data)
    if not 55 <= len(data["full_text"].split()) <= 90:
        raise ValueError("Konuşma metni hedef süre için 55-90 kelime aralığında olmalı")
    return data


def generate(niche: str | None = None, avoid_extra: str = ""):
    used = state.load()["used_topics"]
    banned = list(used[-50:])
    if avoid_extra and avoid_extra not in banned:
        banned.append(avoid_extra)
    avoid = (
        "\n\nSON 50 VİDEODA KULLANILAN / YAKIN AÇILARI TEKRARLAMA: "
        + " | ".join(banned)
    ) if banned else ""

    focus = niche or CONFIG["niche"]
    user_msg = (
        f"Kanal: Denede\n"
        f"Geniş konu alanı: {focus}\n"
        f"Hedef izleyici: {CONFIG['audience']}\n"
        f"Bu alanda somut, taze ve doğrulanabilir tek bir konu seç; mümkün olan en güçlü merak boşluğunu ve payoff'u kur. "
        f"Yalnızca bir Short üret.{avoid}"
    )

    last_err: Exception | None = None
    for attempt in range(5):
        correction = ""
        if last_err:
            correction = (
                f"\n\nÖNCEKİ ÇIKTI REDDEDİLDİ: {last_err}. Baştan, eksiksiz ve yalnızca geçerli JSON üret. "
                "title boş olmasın ve en fazla 60 karakter olsun; 5-7 sahnenin text alanları toplamı 65-78 Türkçe kelime olsun; "
                "tags 5 öğe olsun; açıklama sonunda #shorts dahil tam 4 hashtag bulunsun. "
                "Alanları atlama veya boş bırakma; JSON şemasının tüm alanlarını tekrar ver."
            )
        try:
            data = chat_json(user_msg + correction, system=_system_prompt(), max_tokens=2600)
            data = _validate_package(data)
            if data["topic"].casefold() in {str(topic).casefold() for topic in banned}:
                raise ValueError("Konu tekrar ediyor; başka olgu seç")
            verdict = chat_json(
                "Bağımsız Türkçe bilim ve kültür editörüsün. Aşağıdaki başlık açıklama ve sahneleri incele. "
                "Türkçesi doğal mı, başlıkla konu uyumlu mu, iddialar yerleşik doğru bilgi mi, "
                "sayı birim nedensellik ve zaman hatası var mı kontrol et. İnternet araştırması yapmış gibi davranma. "
                "Emin olmadığın olguyu ve uydurma gizem veya tarihsel olayı reddet. "
                "Başlıkta verilen vaat sahnelerde açıkça yanıtlanmış olmalı. "
                "JSON döndür: {\"valid\":true,\"reason\":\"kısa gerekçe\"}\n" + json.dumps(data, ensure_ascii=False),
                temperature=0, max_tokens=1024)
            if verdict.get("valid") is not True:
                raise ValueError("Editör reddetti: " + str(verdict.get("reason", "belirsiz olgu")))
            data["editorial_review"] = verdict
            return data
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"5 aynı Groq modeli denemesinde geçerli senaryo paketi alınamadı: {last_err}")
