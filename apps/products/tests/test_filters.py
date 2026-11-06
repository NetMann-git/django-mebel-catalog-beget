from django.test import RequestFactory, TestCase

from apps.products.filters import CatalogFilter
from apps.products.models import (
    AttributeType, AttributeValue, Category, Product, ProductAttribute,
)


class CatalogFilterCategoryTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category_a = Category.objects.create(
            title="Свадебные платья",
            slug="wedding-dresses",
        )

        cls.category_b = Category.objects.create(
            title="Вечерние платья",
            slug="evening-dresses",
        )

        cls.product_a = Product.objects.create(
            title="Платье А",
            slug="dress-a",
            price=100000,
            category=cls.category_a,
        )

        cls.product_b = Product.objects.create(
            title="Платье Б",
            slug="dress-b",
            price=200000,
            category=cls.category_b,
        )

    def test_category_filter_returns_only_selected_category(self):
        request = RequestFactory().get(
            "/catalog/",
            {"category": str(self.category_a.pk)},
        )

        catalog_filter = CatalogFilter(request.GET)

        queryset = Product.objects.all()
        result = catalog_filter.apply(queryset)

        self.assertIn(self.product_a, result)
        self.assertNotIn(self.product_b, result)


class CatalogFurnitureFilterTest(TestCase):
    """Проверить числовые границы и совместное применение фильтров."""

    @classmethod
    def setUpTestData(cls):
        cls.small = Product.objects.create(
            title="Авто 90", slug="auto-90", price=2000000, currency="RUB",
        )
        cls.large = Product.objects.create(
            title="Авто 100", slug="auto-100", price=3000000, currency="RUB",
        )
        cls.unknown = Product.objects.create(
            title="Без характеристик", slug="unknown", price=2500000,
        )
        for slug, small, large in (
            ("year", "2021", "2022"),
            ("mileage", "90000", "100000"),
            ("engine_volume", "1,5", "2.0"),
            ("power", "150", "200"),
            ("engine_type", "Бензин", "Дизель"),
        ):
            kind = AttributeType.objects.create(name=slug, slug=slug)
            for product, raw in ((cls.small, small), (cls.large, large)):
                value, _ = AttributeValue.objects.get_or_create(
                    attribute_type=kind, value=raw,
                )
                ProductAttribute.objects.create(
                    product=product, attribute_type=kind, attribute_value=value,
                )

    def filtered(self, **params):
        request = RequestFactory().get("/catalog/", params)
        return list(CatalogFilter(request.GET).apply(Product.objects.all()))

    def test_automotive_mileage_does_not_filter_furniture(self):
        self.assertEqual(self.filtered(mileage_min="95000"), self.filtered())

    def test_all_numeric_ranges_and_year(self):
        self.assertEqual(self.filtered(
            year="2021", mileage_max="90000", engine_volume_min="1.5",
            engine_volume_max="1.5", power_min="150", power_max="150",
            price_max="2000000",
        ), [self.small])

    def test_invalid_range_returns_no_results(self):
        request = RequestFactory().get("/catalog/", {
            "price_min": "3000000", "price_max": "2000000",
        })
        selected = CatalogFilter(request.GET)
        self.assertTrue(selected.errors)
        self.assertFalse(selected.apply(Product.objects.all()).exists())

    def test_blank_specs_stay_in_unfiltered_catalog(self):
        self.assertIn(self.unknown, self.filtered())
        self.assertIn(self.unknown, self.filtered(power_min="1"))

    def test_fuel_filter_and_title_search(self):
        fuel_id = AttributeValue.objects.get(
            attribute_type__slug="engine_type", value="Бензин",
        ).pk
        self.assertEqual(self.filtered(fuel_type=str(fuel_id), q="АВТО 90"), [self.small])

    def test_cyrillic_search_without_other_filters(self):
        self.assertEqual(self.filtered(q="авто 90"), [self.small])

    def test_ruble_range_excludes_foreign_currency(self):
        self.large.currency = "USD"
        self.large.save(update_fields=["currency"])
        self.assertNotIn(self.large, self.filtered(price_min="1"))
