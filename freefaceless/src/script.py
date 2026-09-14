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

Kesin kurallar:
- Konuşma metni TÜRKÇE, toplam ~{target_seconds} saniye (~{target_words} kelime).
- İlk cümle 3 saniyede merak uyandıran güçlü bir HOOK olsun. "Arkadaşlar", kanal introsu yok.
- Gövde: hook'u büyüten 4-6 kısa, vurucu, şaşırtıcı ama doğru bilgi cümlesi.
- Son cümle tek cümlelik doğal takip/yorum çağrısı.
- En fazla 2 soru cümlesi. Emoji, sahne yönü, efekt, madde işareti YOK. Sadece konuşulacak metin.
- Çeviri kokan ifade, anlatım bozukluğu, uydurma sayı/yasa/tıbbi iddia YOK.
- Her sahnenin visual_query alanı Pexels'te sonuç verecek 2-4 İNGİLİZCE isimden oluşsun
  (örn. "octopus swimming ocean"). Stokta karşılığı olmayan soyut kavramı yazma
  (örn. "dopamin" yerine "brain mri neuron").

SADECE geçerli JSON döndür, açıklama ve kod bloğu yok. Şema:
{{
  "topic": "konunun kısa slug hali",
  "title": "95 karakterden kısa Türkçe YouTube başlığı, #shorts içermeli",
  "description": "2-3 cümlelik Türkçe açıklama, ilgili hashtag'lerle bitsin",
  "tags": ["8-12 adet küçük harf etiket"],
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
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    return json.loads(text)


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

    resp = client.chat.completions.create(
        model=CONFIG["script"]["model"],
        max_tokens=2000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = resp.choices[0].message.content
    data = _extract_json(raw)
    data["full_text"] = " ".join(s["text"] for s in data["scenes"])
    return data
