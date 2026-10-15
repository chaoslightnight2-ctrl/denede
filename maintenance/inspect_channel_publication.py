"""Read the owner's actual uploads and publication status. Never change videos."""
from datetime import datetime, timezone
import json
from pathlib import Path


def publication_state(video, now):
    status = video.get('status', {})
    processing = video.get('processingDetails', {}).get('processingStatus')
    if status.get('uploadStatus') in ('failed', 'rejected', 'deleted') or processing in ('failed', 'terminated'):
        return 'youtube_failed'
    if status.get('privacyStatus') == 'public':
        return 'public'
    planned = status.get('publishAt')
    if planned:
        at = datetime.fromisoformat(planned.replace('Z', '+00:00'))
        return 'scheduled_wait' if at > now else 'overdue_not_public'
    return 'private_unscheduled' if status.get('privacyStatus') == 'private' else 'unlisted'


def main():
    from verify_existing_uploads import youtube_service, CHANNELS
    import os
    repo = os.environ['GITHUB_REPOSITORY'].rsplit('/', 1)[-1]
    expected = CHANNELS[repo]
    yt = youtube_service()
    channels = yt.channels().list(part='id,contentDetails', mine=True).execute(num_retries=3)['items']
    channel = next((row for row in channels if row['id'] == expected), None)
    if channel is None:
        raise RuntimeError('The read credential does not own the intended channel')
    playlist = channel['contentDetails']['relatedPlaylists']['uploads']
    items = yt.playlistItems().list(part='contentDetails', playlistId=playlist, maxResults=50).execute(num_retries=3)['items']
    ids = [row['contentDetails']['videoId'] for row in items]
    root = Path(__file__).resolve().parents[1]
    state_path = root / 'freefaceless/state.json'
    receipts = json.loads(state_path.read_text(encoding='utf-8')).get('published', []) if state_path.exists() else []
    known = {row['video_id']: row for row in receipts if row.get('video_id')}
    # Include acknowledged uploads even if the uploads playlist is delayed.
    ids = list(dict.fromkeys([row['video_id'] for row in receipts[-20:] if row.get('video_id')] + ids))
    now = datetime.now(timezone.utc)
    videos = []
    for start in range(0, len(ids), 50):
        actual = yt.videos().list(part='status,processingDetails,snippet', id=','.join(ids[start:start + 50])).execute(num_retries=3)
        for video in actual.get('items', []):
            receipt = known.get(video['id'], {})
            videos.append({'video_id': video['id'], 'title': video['snippet']['title'],
                           'youtube_published_at': video['snippet'].get('publishedAt'),
                           'state': publication_state(video, now), 'youtube_status': video.get('status'),
                           'processing': video.get('processingDetails', {}).get('processingStatus'),
                           'receipt_run_id': receipt.get('run_id'), 'intended_publish_at': receipt.get('publish_at')})
    videos.sort(key=lambda row: row.get('youtube_published_at') or '', reverse=True)
    public = [row for row in videos if row['state'] == 'public']
    report = {'checked_at': now.isoformat(), 'channel_id': expected, 'read_from_youtube': True,
              'latest_public': public[0] if public else None, 'videos': videos}
    destination = root / 'maintenance/channel-publication.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
