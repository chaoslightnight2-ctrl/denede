from .upload import get_service


def main():
    print("Google yetkisi için tarayıcı açılıyor...")
    yt = get_service()
    resp = yt.channels().list(part="snippet", mine=True).execute()
    items = resp.get("items", [])
    if items:
        print("Yetki tamam. Kanal:", items[0]["snippet"]["title"])
        print("token.json kaydedildi — sonraki çalıştırmalar tarayıcı istemez.")
    else:
        print("Yetki tamam ama bu Google hesabına bağlı YouTube kanalı yok.")
        print("Önce youtube.com'da kanal aç, sonra tekrar çalıştır.")


if __name__ == "__main__":
    main()
