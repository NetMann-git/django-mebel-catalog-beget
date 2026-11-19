from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('products', '0011_product_price_details')]
    operations = [
        migrations.AddField(model_name='product', name='project_task', field=models.TextField(blank=True, max_length=2500, verbose_name='Задача клиента', help_text='Что требовалось разместить, какие были ограничения помещения и пожелания.')),
        migrations.AddField(model_name='product', name='project_solution', field=models.TextField(blank=True, max_length=3500, verbose_name='Решение мастерской', help_text='Как организованы хранение, рабочие зоны, техника и нестандартные узлы.')),
        migrations.AddField(model_name='product', name='project_dimensions', field=models.TextField(blank=True, max_length=700, verbose_name='Размеры проекта', help_text='Укажите единицы измерения и размеры основных элементов. Пишите только известные размеры.')),
        migrations.AddField(model_name='product', name='project_materials', field=models.TextField(blank=True, max_length=1200, verbose_name='Материалы и фурнитура проекта', help_text='Материалы корпуса, фасадов, столешницы, покрытия и механизмы фактически выполненной работы.')),
    ]
