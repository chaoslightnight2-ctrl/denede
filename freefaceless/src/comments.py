import json
import re
from openai import OpenAI
from .config import GROQ_API_KEY, GROQ_BASE_URL, CONFIG
from .upload import get_service

client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

CLASSIFY_SYSTEM = """Faceless Türkçe bilgi kanalının YouTube Shorts yorumlarını denetliyorsun.

Her yorum için karar ver:
- "delete": bariz spam (abone dilenme, dolandırıcılık, link tuzağı, hakaret, konu dışı reklam).
- "reply": samimi bir soru veya yanıtı hak eden ilginç bir yorum. Yanıt tek kısa Türkçe cümle,
  samimi, emoji yok, asla abone isteme.
- "ignore": diğer her şey (emoji, genel övgü, nötr yorumlar).

SADECE şu şemada JSON döndür, sırayı koru:
{"results": [{"action": "delete|reply|ignore", "reply": "yanıt ya da boş string"}]}"""


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    return json.loads(text)


def list_recent_comments(yt, video_id: str, max_results: int = 50):
    resp = yt.commentThreads().list(
        part="snippet", videoId=video_id, maxResults=max_results, order="time",
        textFormat="plainText",
    ).execute()
    items = []
    for thr in resp.get("items", []):
        top = thr["snippet"]["topLevelComment"]
        items.append({
            "id": top["id"],
            "thread_id": thr["id"],
            "author": top["snippet"]["authorDisplayName"],
            "text": top["snippet"]["textDisplay"],
        })
    return items


def classify(comments: list[dict]) -> list[dict]:
    if not comments:
        return []
    user_msg = "\n".join(f"{i+1}. {c['text']}" for i, c in enumerate(comments))
    resp = client.chat.completions.create(
        model=CONFIG["comments"].get("model", "openai/gpt-oss-20b"),
        max_tokens=4000,
        reasoning_effort="low",
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    data = _extract_json(resp.choices[0].message.content)
    return data.get("results", [])


def moderate_video(video_id: str):
    yt = get_service()
    cfg = CONFIG["comments"]
    comments = list_recent_comments(yt, video_id)
    if not comments:
        return {"checked": 0}

    actions = classify(comments)
    deleted = replied = 0
    for c, a in zip(comments, actions):
        act = a.get("action", "ignore")
        if act == "delete" and cfg["delete_spam"]:
            try:
                yt.comments().setModerationStatus(id=c["id"], moderationStatus="rejected").execute()
                deleted += 1
            except Exception:
                pass
        elif act == "reply" and cfg["auto_reply"] and a.get("reply"):
            try:
                yt.comments().insert(
                    part="snippet",
                    body={"snippet": {"parentId": c["id"], "textOriginal": a["reply"]}},
                ).execute()
                replied += 1
            except Exception:
                pass
    return {"checked": len(comments), "deleted": deleted, "replied": replied}
