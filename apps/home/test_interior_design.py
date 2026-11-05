"""Шаг 65: изображения и разрешимые контурные иконки внутренних страниц."""
import re
from pathlib import Path
from django.test import TestCase, SimpleTestCase
from django.contrib.staticfiles import finders
from PIL import Image

class InteriorDesignTests(TestCase):
    def test_five_pages_have_split_hero_images_and_resolved_symbols(self):
        for url in ['/about/','/services/','/materials/','/reviews/','/contacts/']:
            with self.subTest(url=url):
                r=self.client.get(url);self.assertEqual(r.status_code,200)
                self.assertContains(r,'class="fi-hero"',count=1)
                self.assertContains(r,'furniture-interior.css',count=1)
                self.assertContains(r,'furniture-editorial.css',count=1)
                self.assertContains(r,'fetchpriority="high"',count=1)
                html=r.content.decode();symbols=set(re.findall(r'<symbol id="([^"]+)"',html))
                for used in re.findall(r'<use href="#([^"]+)"',html):self.assertIn(used,symbols)
                for src in re.findall(r'(?:src|href)="/static/(home/images/editorial/[^"]+)"',html):
                    self.assertIsNotNone(finders.find(src),src)

    def test_materials_have_four_photographic_cards(self):
        r=self.client.get('/materials/')
        self.assertContains(r,'class="fi-card-image"',count=4)
        for name in ['material-ldsp','material-solid','material-hardware','materials-cover']:
            self.assertContains(r,name+'.jpg')

    def test_reviews_keep_real_photo_separate_from_editorial_hero(self):
        from apps.products.models import Product
        from apps.reviews.models import Review, ReviewImage
        p=Product.objects.create(title='Шкаф',slug='interior-review',price=100)
        review=Review.objects.create(product=p,guest_name='Клиент',rating=3,text='Мой отзыв',is_published=True)
        ReviewImage.objects.create(review=review,image='reviews/customer-original.jpg')
        html=self.client.get('/reviews/').content.decode()
        self.assertIn('/media/reviews/customer-original.jpg',html)
        self.assertIn('Оценка 3 из 5',html)
        start=html.index('<article class="fs-service fr-review">');end=html.index('</article>',start)
        self.assertNotIn('editorial/',html[start:end])

class InteriorFilesTests(SimpleTestCase):
    def test_generated_assets_have_large_small_and_jpeg_versions(self):
        for name in ['workshop-detail','bespoke-interior','living-detail']:
            for suffix,width in [('.jpg',960),('.webp',960),('-small.webp',480)]:
                p=finders.find('home/images/editorial/'+name+suffix);self.assertIsNotNone(p)
                with Image.open(p) as im:self.assertEqual(im.size,(width,width*2//3))
                self.assertLess(Path(p).stat().st_size,600000)
