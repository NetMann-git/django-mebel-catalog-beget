"""Шаг 64: самостоятельные изображения вместо маленьких фрагментов макета."""
from pathlib import Path
from html.parser import HTMLParser
from django.test import TestCase, SimpleTestCase
from django.contrib.staticfiles import finders
from PIL import Image

NAMES = ['hero','callback','process-measure','process-design','process-production',
         'process-installation','materials-cover','material-ldsp','material-veneer',
         'material-solid','material-hardware']

class MediaParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.pictures=[]; self.current=None
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='picture' and 'fm-editorial-photo' in attrs.get('class',''):
            self.current={'picture':attrs}; self.pictures.append(self.current)
        if self.current is not None and tag in ('img','source'): self.current[tag]=attrs
    def handle_endtag(self,tag):
        if tag=='picture': self.current=None

class EditorialMediaTests(TestCase):
    def test_home_uses_eleven_responsive_images_with_correct_loading(self):
        r=self.client.get('/');self.assertEqual(r.status_code,200)
        parser=MediaParser();parser.feed(r.content.decode())
        self.assertEqual(len(parser.pictures),11)
        for item in parser.pictures:
            self.assertEqual(item['source']['type'],'image/webp')
            self.assertIn('-small.webp',item['source']['srcset'])
            self.assertTrue(item['img']['src'].endswith('.jpg'))
            self.assertIn(item['img']['loading'],['eager','lazy'])
            self.assertIn('width',item['img']);self.assertIn('height',item['img'])
        hero=next(p for p in parser.pictures if 'fm-hero-photo' in p['picture']['class'])
        self.assertEqual(hero['img']['loading'],'eager')
        self.assertEqual(hero['img']['fetchpriority'],'high')
        self.assertEqual(hero['img']['alt'],'')
        self.assertEqual(sum(p['img']['loading']=='lazy' for p in parser.pictures),10)
        self.assertContains(r,'furniture-editorial.css',count=1)
        self.assertContains(r,'home/branding/logo-compact-dark.svg')

    def test_target_sections_no_longer_crop_design_reference(self):
        s=self.client.get('/').content.decode()
        for needle in ['id="process"','id="materials"','class="fm-hero"','class="fm-callback"']:
            a=s.index(needle);b=s.index('</section>',a)
            self.assertNotIn('furniture-reference-',s[a:b])
        for name in NAMES:self.assertIn('/home/images/editorial/'+name+'.jpg',s)

class EditorialAssetTests(SimpleTestCase):
    def test_all_formats_exist_and_have_correct_sizes(self):
        for name in NAMES:
            width=1536 if name in ['hero','callback'] else 640 if name.startswith('material-') else 960
            small=width//2
            for suffix in ['.jpg','.webp','-small.webp']:
                path=finders.find('home/images/editorial/'+name+suffix)
                self.assertIsNotNone(path,name+suffix)
                with Image.open(path) as im:
                    self.assertEqual(im.width,small if suffix.startswith('-small') else width)
                    self.assertEqual(im.width,im.height if name.startswith('material-') else im.height*3//2)
                self.assertLess(Path(path).stat().st_size,700_000)
