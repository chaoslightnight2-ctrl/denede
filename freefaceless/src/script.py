import json
import re
from openai import OpenAI
from .config import GROQ_API_KEY, GROQ_BASE_URL, CONFIG
from . import state

client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

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
- Hook cesur bir soru, şaşırtıcı ama doğru bir bilgi ya da tanıdık bir şeye ters açı olabilir.
  Boş “inanamayacaksın” ve cevabı vermeyen clickbait kullanma.
- İlk 2 sahnede ana konu/varlığın adı açıkça geçsin.
- Hızlı ritim: kısa cümleler, her sahnede yeni bilgi, ortada somut açıklama/ters köşe,
  sonda vaat edilen cevabın payoff'u. Gereksiz tekrar ve dolgu yok.
- Son cümlede izleyiciye konuya özel, kolay cevaplanır tek soru sor ve doğal, kısa bir
  “Denede için abone ol” çağrısı ekle. Genel “beğen-abone ol” listesi yazma.
- Emoji, sahne talimatı, efekt ve madde işareti yok; yalnızca seslendirilecek cümleler.
- Her sahnenin visual_query alanı Pexels'te aranabilir 2-4 İngilizce görsel sözcük olsun.
  Soyut kavram yerine görülebilir nesne/eylem yaz.

BAŞLIK:
- Türkçe, en fazla 60 karakter; konuyu ilk bölümde anlaşılır kıl, merak boşluğu ve güçlü fiil kullan.
- Yanlış izlenim, kanıtlanmamış “şok”, sahte sayı ve alakasız gündem kelimesi yok.
- Her içerikte aynı kalıbı tekrarlama. Soru, karşılaştırma, “neden/nasıl” ve şaşırtıcı sonuç
  kalıpları arasından konuya en uygun olanı seç.

AÇIKLAMA VE ETİKETLER:
- Açıklama 1-2 kısa, videoya özel cümle olsun; ilk cümlede konu adı bulunsun.
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
    data["title"] = title
    data["description"] = description
    data["tags"] = [t.strip().lower() for t in tags]
    data["full_text"] = " ".join(s["text"].strip() for s in scenes)
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
        f"Bu alanda somut, taze ve doğru tek bir konu seç; izleyici merakını güçlü aç ama payoff'u ver. "
        f"Yalnızca bir Short üret.{avoid}"
    )

    last_err: Exception | None = None
    for attempt in range(3):
        correction = ""
        if last_err:
            correction = f"\nÖnceki deneme şu doğrulama hatasını verdi; bu kez düzelt: {last_err}"
        try:
            resp = client.chat.completions.create(
                model=CONFIG["script"]["model"],
                max_tokens=8000,
                reasoning_effort="low",
                messages=[
                    {"role": "system", "content": _system_prompt()},
                    {"role": "user", "content": user_msg + correction},
                ],
            )
            raw = resp.choices[0].message.content or ""
            data = _extract_json(raw)
            return _validate_package(data)
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"3 denemede geçerli senaryo paketi alınamadı: {last_err}")
