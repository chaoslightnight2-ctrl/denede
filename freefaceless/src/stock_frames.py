"""Find an actual visible opening in the selected clip; never insert substitute media."""
from io import BytesIO
import subprocess
from PIL import Image, ImageStat


def visible_start(path, duration):
    for at in (0.0, .5, 1.0, 2.0):
        if at >= duration:
            break
        result = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(at), '-i', str(path),
                                 '-frames:v', '1', '-vf', 'scale=96:-2', '-f', 'image2pipe', '-vcodec', 'png', '-'],
                                capture_output=True, check=True)
        if result.stdout:
            with Image.open(BytesIO(result.stdout)) as frame:
                if max(ImageStat.Stat(frame.convert('RGB')).stddev) >= 5:
                    return at
    raise ValueError('Selected stock has no visible opening; no replacement clip used')
