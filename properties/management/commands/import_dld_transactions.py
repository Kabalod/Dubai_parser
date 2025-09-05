import csv
import hashlib
import os
from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from properties.models import Property, Building


class Command(BaseCommand):
    help = (
        "Импорт транзакций DLD из CSV с маппингом районов из HyperMatchOut.csv.\n"
        "Пример: python manage.py import_dld_transactions --transactions dld.csv --mapping HyperMatchOut.csv --update"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--transactions",
            required=True,
            help="Путь к CSV с транзакциями DLD",
        )
        parser.add_argument(
            "--mapping",
            required=True,
            help="Путь к CSV HyperMatchOut.csv для маппинга районов",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Обновлять существующие записи",
        )
        parser.add_argument(
            "--limit", type=int, default=None, help="Ограничение количества импортируемых строк"
        )

    def handle(self, *args, **options):
        tx_path = options["transactions"]
        map_path = options["mapping"]
        update_existing = options["update"]
        limit = options["limit"]

        if not os.path.isfile(tx_path):
            raise CommandError(f"Файл транзакций не найден: {tx_path}")
        if not os.path.isfile(map_path):
            raise CommandError(f"Файл маппинга не найден: {map_path}")

        area_map = self._load_area_mapping(map_path)
        self.stdout.write(f"Загружено соответствий районов: {len(area_map)}")

        created, updated = 0, 0
        with open(tx_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        total = len(rows) if limit is None else min(len(rows), limit)
        self.stdout.write(f"Строк к обработке: {total}")

        for i, row in enumerate(rows, 1):
            if limit is not None and i > limit:
                break

            try:
                ok, upd = self._upsert_property_from_tx(row, area_map, update_existing)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Строка {i}: ошибка: {e}"))
                continue

            if ok and upd:
                updated += 1
            elif ok:
                created += 1

            if i % 500 == 0:
                self.stdout.write(f"Обработано {i}/{total}...")

        self.stdout.write(
            self.style.SUCCESS(
                f"Импорт завершён. Создано: {created}, Обновлено: {updated}, Всего обработано: {total}"
            )
        )

    # --- helpers ---
    def _load_area_mapping(self, mapping_csv_path: str) -> dict:
        """Читает CSV HyperMatchOut и строит словарь исходный_район -> целевой_район.

        Пытается автоматически определить названия колонок.
        """
        with open(mapping_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return {}

        # эвристики по названиям колонок
        candidates_src = [
            "area_name_en_out",
            "area_name_en",
            "dld_area",
            "source_area",
            "area",
        ]
        candidates_dst = [
            "rest_area",
            "mapped_area",
            "target_area",
            "match_area",
            "area",
        ]

        headers = rows[0].keys()
        src = next((c for c in candidates_src if c in headers), None)
        dst = next((c for c in candidates_dst if c in headers and c != src), None)
        if not src or not dst:
            # если не нашли явные, пытаемся взять первые 2 колонки
            hdrs = list(headers)
            src = hdrs[0]
            dst = hdrs[1] if len(hdrs) > 1 else hdrs[0]

        mapping = {}
        for r in rows:
            k = (r.get(src) or "").strip()
            v = (r.get(dst) or "").strip()
            if k:
                mapping[k.lower()] = v or k
        return mapping

    def _upsert_property_from_tx(self, row: dict, area_map: dict, update_existing: bool) -> tuple[bool, bool]:
        """Создаёт/обновляет Property из строки CSV с транзакцией.

        Возвращает (ok, updated_flag)
        """
        # transaction id
        tx_id = (row.get("transaction_id") or row.get("tx_id") or "").strip()
        if not tx_id:
            # формируем стабильный хеш из нескольких полей
            basis = (
                (row.get("building") or row.get("building_name") or row.get("project") or "")
                + (row.get("area") or row.get("community") or "")
                + (row.get("transaction_date") or row.get("date") or "")
                + (row.get("price") or row.get("amount") or row.get("transaction_value") or "")
            )
            tx_id = hashlib.md5(basis.encode("utf-8")).hexdigest()
        property_id = f"dld_{tx_id}"

        # basic fields
        title = (row.get("project") or row.get("project_name_en") or row.get("building_name") or "").strip()
        display_address = (row.get("building_name") or row.get("project") or row.get("community") or row.get("area") or "").strip()

        # building/area
        area_raw = (row.get("area") or row.get("community") or row.get("location") or "").strip()
        area_mapped = area_map.get(area_raw.lower(), area_raw)
        building_name = (row.get("building") or row.get("building_name") or row.get("tower") or title or "").strip()

        # price (assume sales)
        price = self._parse_price(row)
        currency = (row.get("currency") or "AED").strip() or "AED"

        # beds/size
        bedrooms = self._parse_int(row.get("bedrooms") or row.get("rooms") or row.get("rooms_en"))
        size_val, size_unit = self._parse_size(row)

        # date
        added_on = None
        date_raw = row.get("transaction_date") or row.get("date") or row.get("instance_date")
        if date_raw:
            try:
                added_on = parse_datetime(date_raw) or datetime.fromisoformat(date_raw)
            except Exception:
                added_on = None

        # upsert property
        try:
            prop = Property.objects.get(property_id=property_id)
            if not update_existing:
                return False, False
            is_update = True
        except Property.DoesNotExist:
            prop = Property(property_id=property_id)
            is_update = False

        # set fields (with safe truncation handled by model/import utils earlier)
        prop.url = f"https://dld.gov/tx/{tx_id}"
        prop.title = title[:500]
        prop.display_address = display_address
        prop.bedrooms = bedrooms
        if size_unit == "sqm":
            prop.area_sqm = size_val
        elif size_unit == "sqft":
            prop.area_sqft = size_val
        prop.price = price
        prop.price_currency = currency
        prop.price_duration = "sell"
        prop.added_on = added_on

        # link/create building
        if display_address and not prop.building:
            building, _ = Building.objects.get_or_create(
                name=building_name[:500] or display_address.split(",")[0].strip() or "Unknown",
                address=display_address,
                defaults={"area": area_mapped},
            )
            # обновим area, если появилось
            if area_mapped and building.area != area_mapped:
                building.area = area_mapped
                building.save(update_fields=["area"])
            prop.building = building

        # skip heavy calcs
        setattr(prop, "_skip_calculations", True)
        prop.save()
        return True, is_update

    def _parse_price(self, row: dict):
        candidates = [
            "price",
            "amount",
            "transaction_value",
            "total_amount",
            "actual_worth",
            "value",
        ]
        raw = None
        for k in candidates:
            v = row.get(k)
            if v not in (None, ""):
                raw = v
                break
        if raw is None:
            return None
        try:
            s = str(raw).lower().replace("aed", " ").replace(",", "").replace("\u00a0", " ")
            # первое число
            import re

            m = re.search(r"\d+(?:[\.\s]\d+)?", s)
            if not m:
                return None
            num = m.group(0).replace(" ", "")
            return Decimal(num)
        except Exception:
            return None

    def _parse_size(self, row: dict):
        """Возвращает (value, unit) где unit in {"sqm","sqft",None}"""
        candidates = ["size", "area", "area_sqm", "area_sqft", "procedure_area", "sizeMin"]
        raw = None
        key = None
        for k in candidates:
            v = row.get(k)
            if v not in (None, ""):
                raw = v
                key = k
                break
        if raw is None:
            return None, None

        s = str(raw).lower()
        # unit by key or content
        unit = None
        if "sqm" in s or (key and "sqm" in key):
            unit = "sqm"
        elif "sqft" in s or (key and "sqft" in key):
            unit = "sqft"

        # extract number
        try:
            import re

            m = re.search(r"\d+\.?\d*", s.replace(",", ""))
            val = float(m.group(0)) if m else None
        except Exception:
            val = None
        return val, unit

    def _parse_int(self, value):
        if value in (None, ""):
            return None
        try:
            return int(str(value).strip().split()[0])
        except Exception:
            return None


