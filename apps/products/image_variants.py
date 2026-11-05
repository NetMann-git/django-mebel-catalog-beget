"""Small display files. Originals are only used for explicit full-size viewing."""
import json
import logging
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit
from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models.fields.files import FieldFile
from django.templatetags.static import static
from easy_thumbnails.files import get_thumbnailer
from easy_thumbnails.exceptions import EasyThumbnailsError

logger = logging.getLogger(__name__)
# Pixel dimensions include room for high-density screens, not CSS-only shrinking.
IMAGE_SIZES = {
    'table': (224, 168), 'category_table': (192, 128),
    'thumb': (160, 120), 'review': (320, 240), 'logo': (240, 180),
    'card': (800, 600), 'category_card': (640, 580),
    'preview': (960, 720), 'detail': (1200, 1000),
}


@lru_cache(maxsize=1)
def static_variants():
    return json.loads(Path(__file__).with_name('static_image_variants.json').read_text(encoding='utf-8'))


def image_variant(source, preset='card'):
    if preset not in IMAGE_SIZES:
        raise ValueError('Unknown image preset: ' + preset)
    missing = static('products/images/image-unavailable.svg')
    if not source:
        return missing
    try:
        if isinstance(source, FieldFile):
            if source.name.lower().endswith('.svg'):
                return source.url
            thumbnailer = get_thumbnailer(source)
        else:
            value = str(source)
            static_prefix = settings.STATIC_URL
            if value.startswith(static_prefix):
                path = unquote(value[len(static_prefix):].split('?', 1)[0])
                # Small vector icons/logos do not require raster thumbnails.
                if path.endswith('.svg') and '..' not in Path(path).parts:
                    return value
                variant = static_variants().get(path, {}).get(preset)
                return static(variant) if variant else missing
            media_path = urlsplit(settings.MEDIA_URL).path
            source_path = urlsplit(value).path
            if not media_path or not source_path.startswith(media_path):
                return missing
            name = unquote(source_path[len(media_path):])
            if not name or '..' in Path(name).parts or name.startswith('/'):
                return missing
            thumbnailer = get_thumbnailer(default_storage, name)
        thumbnailer.thumbnail_extension = 'webp'
        thumbnailer.thumbnail_transparency_extension = 'webp'
        thumbnailer.thumbnail_preserve_extensions = False
        thumbnail = thumbnailer.get_thumbnail({
            'size': IMAGE_SIZES[preset], 'crop': False, 'upscale': False,
            'quality': 92, 'subsampling': 0,
        })
        return thumbnail.url
    except (OSError, ValueError, TypeError, EasyThumbnailsError) as error:
        # Do not silently download an enormous original on thumbnail failure.
        logger.warning('Image preview unavailable: %s', type(error).__name__)
        return missing
