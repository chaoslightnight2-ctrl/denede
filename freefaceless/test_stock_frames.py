import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from src.stock_frames import visible_start


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg unavailable')
class VisibleOpeningTests(unittest.TestCase):
    def test_uniform_gray_clip_is_not_accepted_as_a_picture(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / 'gray.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                            'color=c=gray:s=160x240:d=3', '-c:v', 'libx264', str(video)], check=True)
            with self.assertRaisesRegex(ValueError, 'no visible opening'):
                visible_start(video, 3)

    def test_blank_lead_can_be_trimmed_without_replacing_the_selected_clip(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / 'lead.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                            'color=c=gray:s=160x240:r=25:d=0.5', '-f', 'lavfi', '-i',
                            'testsrc2=s=160x240:r=25:d=2', '-filter_complex',
                            '[0:v][1:v]concat=n=2:v=1:a=0[out]', '-map', '[out]', '-c:v', 'libx264', str(video)], check=True)
            self.assertGreaterEqual(visible_start(video, 2.5), .5)

if __name__ == '__main__':
    unittest.main()
