import json
import re
from openai import OpenAI
from .config import GROQ_API_KEY, GROQ_BASE_URL, CONFIG
from . import state

client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

# Kanalın 10 nişi — --niche ile tekine zorlanabilir, aksi halde Groq rotasyon yapar.
TURKISH_NICHES = [
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

SYSTEM = """Faceless Türkçe bilgi kanalı için viral YouTube Shorts senaryosu yazıyorsun.
Algoritma gerçekleri: izleyici ilk 1,5 saniyede kalmaya ya da kaydırmaya karar verir;
bitirme oranı ve tekrar izleme dağıtımı belirler. Her kural bunun içindir.

METİN KURALLARI (konuşma metni TÜRKÇE):
- Toplam 60-70 kelime, fazlası YOK (~{target_seconds} sn). Kısa = bitirme oranı demek.
- Yapı: HOOK (0-3 sn) → BAĞLAM (3-8 sn) → PAYOFF (şaşırtıcı bilgi) → LOOP KAPANIŞ.
- İlk cümle SORU DEĞİL, cesur senaryo-tarzı bir iddia olsun (örn. "Beyninin seni her gün kandırıyor.").
  Selamlaşma, kanal introsu, "bugün şunu anlatacağım" YOK — direkt konuya gir.
- Konu anahtar ifadesi ilk 2 cümlede aynen geçsin (başlık + açıklama + konuşma aynı kelimeyi taşır).
- Gövde: hook'u büyüten 3-5 kısa cümle; en az 1 ters-köşe/şaşırtıcı bilgi (paylaşma tetikler).
- Metnin TAMAMINDA en fazla 1 soru cümlesi; o da sonda yorum tetikleyen tek soru olsun.
- Son cümle: açılış iddiasına göz kırpan bir kapanış + doğal tek cümlelik takip çağrısı
  (bitiş başlangıca bağlanır, tekrar izleme hissi verir).
- Emoji, sahne yönü, efekt, madde işareti YOK. Sadece konuşulacak metin.
- Çeviri kokan ifade, anlatım bozukluğu, uydurma sayı/yasa/tıbbi iddia YOK.
- Her sahnenin visual_query alanı Pexels'te sonuç verecek 2-4 İNGİLİZCE isimden oluşsun
  (örn. "octopus swimming ocean"). Stokta karşılığı olmayan soyut kavramı yazma
  (örn. "dopamin" yerine "brain mri neuron").
- 5-7 sahne; her sahne 1-2 kısa cümle (görsel değişim sık olur, kaydırma önlenir).

BAŞLIK (Türkçe, hashtag YOK):
- En fazla 60 karakter. Anahtar kelime İLK 3-4 kelimede.
- Spesifik + merak uyandıran; "işte", "şok", "inanılmaz" gibi boş yemler YOK.

AÇIKLAMA (Türkçe):
- 2-3 cümle; İLK cümlede anahtar kelime geçsin; sonra bağlam + çağrı.
- Tam 4 hashtag ile bitsin: #shorts + 1 geniş + 2 spesifik (içeriğe özel, her videoda farklı).

ETİKETLER: tam 5 adet, küçük harf, içeriye özel; ilki başlıktaki anahtar ifade.

SADECE geçerli JSON döndür: yanıtın tamamı tek JSON objesi olsun, önce/sonra hiçbir kelime yazma. Şema:
{{
  "topic": "konunun kısa slug hali",
  "title": "60 karakteri geçmeyen Türkçe başlık",
  "description": "2-3 cümlelik Türkçe açıklama, 4 hashtag ile bitsin",
  "tags": ["5 adet küçük harf etiket"],
  "scenes": [
    {{"text": "söylenecek Türkçe cümle", "visual_query": "2-4 ingilizce stok isim"}}
  ]
}}"""


def _system_prompt():
    s = CONFIG["script"]
    target_words = int(s["target_seconds"] * s["words_per_second"])
    return SYSTEM.format(
        target_seconds=s["target_seconds"],
        wps=s["words_per_second"],
        target_words=target_words,
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Model başa/sona kelime eklediyse ilk { ile son } arasını al.
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("Yanıt JSON içermiyor")


def generate(niche: str | None = None):
    used = state.load()["used_topics"]
    avoid = ("\n\nZaten işlenenler (farklı bir şey seç): "
             + ", ".join(used[-50:])) if used else ""

    focus = niche or CONFIG["niche"]
    user_msg = (
        f"Niş: {focus}\n"
        f"Hedef kitle: {CONFIG['audience']}\n"
        f"Şimdi TEK taze Short üret.{avoid}"
    )

    last_err: Exception | None = None
    for attempt in range(3):
        resp = client.chat.completions.create(
            model=CONFIG["script"]["model"],
            max_tokens=8000,
            reasoning_effort="low",  # gpt-oss akıl yürütmeye takılıp boş dönmesin
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": user_msg},
            ],
        )
        raw = resp.choices[0].message.content
        try:
            data = _extract_json(raw)
            data["full_text"] = " ".join(s["text"] for s in data["scenes"])
            if not data["scenes"] or not data.get("title"):
                raise ValueError("Eksik alan: scenes/title")
            return data
        except Exception as exc:  # bozuk JSON → aynı kuralla tekrar dene
            last_err = exc
    raise RuntimeError(f"3 denemede geçerli senaryo JSON'u alınamadı: {last_err}")
