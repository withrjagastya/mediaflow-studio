from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from mediaflow.core import filter_graph, find_videos, load_presets, probe_media, safe_stem, source_id
from mediaflow.pipeline import build, verify


class CoreTests(unittest.TestCase):
    def test_safe_stem(self):
        self.assertEqual(safe_stem('My Video #01!'), 'My-Video-01')
        self.assertEqual(safe_stem('गाणे'), 'video')

    def test_filter_modes(self):
        self.assertIn('pad=720:1280', filter_graph(720, 1280, 'pad'))
        self.assertIn('crop=720:1280', filter_graph(720, 1280, 'crop'))
        with self.assertRaises(ValueError):
            filter_graph(720, 1280, 'stretch')

    def test_presets_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'custom.json'
            p.write_text('{"bad": {"width": 641, "height": 480}}')
            with self.assertRaises(ValueError):
                load_presets(p)
            p.write_text('{"tiny": {"width": 160, "height": 160}}')
            self.assertIn('tiny', load_presets(p))

    def test_source_id_differs_for_formats(self):
        self.assertNotEqual(source_id(Path('/tmp/a.mp4')), source_id(Path('/tmp/a.mov')))

    def test_discovery_excludes_exports(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / 'video.mp4').touch()
            (base / 'exports').mkdir()
            (base / 'exports' / 'result.mp4').touch()
            self.assertEqual(len(find_videos(base, excluded_folder=base / 'exports')), 1)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg is not installed')
class FFmpegIntegrationTests(unittest.TestCase):
    def test_build_and_verify(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            input_dir, output_dir = base / 'input', base / 'exports'
            input_dir.mkdir()
            clip = input_dir / 'clip.mp4'
            subprocess.run([
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                'color=c=blue:s=160x90:r=10:d=1.2', '-c:v', 'mpeg4', '-y', str(clip)
            ], check=True)
            preset_path = base / 'presets.json'
            preset_path.write_text('{"tiny": {"width": 160, "height": 160}}')
            self.assertAlmostEqual(probe_media(clip).duration, 1.2, delta=.3)
            summary = build(input_dir, output_dir, ['tiny'], preset_file=preset_path, thumbs=True)
            self.assertEqual(summary['total'], 1)
            self.assertEqual(summary['errors'], 0)
            status = verify(Path(summary['manifest']))
            self.assertTrue(status['passed'], status['issues'])
            self.assertEqual(status['checked'], 1)
            again = build(input_dir, output_dir, ['tiny'], preset_file=preset_path, thumbs=True)
            self.assertEqual(again['errors'], 0)


if __name__ == '__main__':
    unittest.main()
