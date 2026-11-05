"""Real small fixture files for tests that inspect generated display images."""
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image


def image_test_storage(testcase, names):
    directory = TemporaryDirectory()
    testcase.addCleanup(directory.cleanup)
    override = testcase.settings(MEDIA_ROOT=directory.name)
    override.enable()
    testcase.addCleanup(override.disable)
    for name in names:
        target = Path(directory.name) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (1200, 800), '#b39772').save(target)
