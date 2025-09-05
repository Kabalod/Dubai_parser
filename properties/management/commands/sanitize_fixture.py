import json
from django.core.management.base import BaseCommand, CommandError
from properties.models import Property


class Command(BaseCommand):
    help = 'Санитизировать Django-фикстуру: обрезать строки до max_length модели Property'

    def add_arguments(self, parser):
        parser.add_argument('input', type=str, help='Путь к исходной фикстуре JSON')
        parser.add_argument('output', type=str, help='Путь для сохранения очищенной фикстуры JSON')

    def handle(self, *args, **options):
        input_path = options['input']
        output_path = options['output']

        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as exc:
            raise CommandError(f'Не удалось прочитать файл {input_path}: {exc}')

        # Карта максимальных длин полей Property
        max_len = {
            'property_id': Property._meta.get_field('property_id').max_length,
            'url': Property._meta.get_field('url').max_length,
            'title': Property._meta.get_field('title').max_length,
            'agent_name': Property._meta.get_field('agent_name').max_length,
            'agent_phone': Property._meta.get_field('agent_phone').max_length,
            'broker_name': Property._meta.get_field('broker_name').max_length,
            'broker_license': Property._meta.get_field('broker_license').max_length,
            'property_type': Property._meta.get_field('property_type').max_length,
            'furnishing': Property._meta.get_field('furnishing').max_length,
            'price_currency': Property._meta.get_field('price_currency').max_length,
            'reference': Property._meta.get_field('reference').max_length,
            'rera_number': Property._meta.get_field('rera_number').max_length,
        }

        def truncate(value: str, field_name: str):
            if value is None:
                return None
            try:
                limit = max_len.get(field_name)
                if not limit:
                    return value
                s = str(value)
                return s if len(s) <= limit else s[:limit]
            except Exception:
                return value

        changed = 0
        total = 0

        # Фикстура — это список объектов {model, pk, fields}
        if not isinstance(data, list):
            raise CommandError('Ожидался список объектов в фикстуре JSON')

        for obj in data:
            if not isinstance(obj, dict):
                continue
            model_label = obj.get('model', '')
            if model_label != 'properties.property':
                continue
            fields = obj.get('fields', {}) or {}
            total += 1

            for fname in list(max_len.keys()):
                if fname in fields:
                    orig = fields.get(fname)
                    newv = truncate(orig, fname)
                    if newv != orig:
                        fields[fname] = newv
                        changed += 1

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'), indent=0)
        except Exception as exc:
            raise CommandError(f'Не удалось записать файл {output_path}: {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'Санитация завершена: объектов={total}, измененных полей={changed}. Файл: {output_path}'
        ))


