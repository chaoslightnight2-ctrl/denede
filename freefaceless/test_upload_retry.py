import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httplib2
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest, MediaFileUpload
with patch.dict(os.environ, {'GROQ_API_KEY':'test-only', 'PEXELS_API_KEY':'test-only'}):
    from src import upload


class ResumableUploadTests(unittest.TestCase):
    def exercise(self, statuses):
        calls = []
        remaining = iter(statuses)
        def http_request(uri, method='GET', **kwargs):
            calls.append((uri, method))
            if method == 'POST':
                return httplib2.Response({'status':'200', 'location':'https://upload.test/session'}), b''
            status = next(remaining)
            body = {'id':'AbcDef_1234'} if status == 200 else {'error':{'code':status,'message':'test error'}}
            return httplib2.Response({'status':str(status)}), json.dumps(body).encode()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test-only.mp4'
            path.write_bytes(b'test fixture not a production video')
            request = HttpRequest(types.SimpleNamespace(request=http_request),
                lambda response, body: json.loads(body), 'https://upload.test/start', method='POST', body='{}',
                resumable=MediaFileUpload(str(path), mimetype='video/mp4', resumable=True))
            request._sleep = lambda seconds: None
            insert = Mock(return_value=request)
            service = types.SimpleNamespace(videos=lambda:types.SimpleNamespace(insert=insert))
            try:
                with patch.object(upload,'get_service',return_value=service):
                    result = upload.upload_video(path,'test title','test description',[],publish_at='2050-01-01T00:00:00Z')
            finally:
                request.resumable.stream().close()
                if insert.call_args:
                    insert.call_args.kwargs['media_body'].stream().close()
            self.assertEqual(insert.call_count,1)
            return result,calls,insert.call_args.kwargs['body']

    def test_temporary_server_error_resumes_same_upload_and_keeps_schedule(self):
        result,calls,body = self.exercise([503,200])
        self.assertEqual(result,'AbcDef_1234')
        self.assertEqual(calls,[('https://upload.test/start','POST'),('https://upload.test/session','PUT'),('https://upload.test/session','PUT')])
        self.assertEqual(body['status']['privacyStatus'],'private')
        self.assertEqual(body['status']['publishAt'],'2050-01-01T00:00:00Z')

    def test_permanent_rejection_is_not_treated_as_upload_success(self):
        with self.assertRaises(HttpError):
            self.exercise([400])


if __name__ == '__main__':
    unittest.main()
