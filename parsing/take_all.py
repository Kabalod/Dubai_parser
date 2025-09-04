#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import argparse



def process_all_files(root_dir: str, output_file: str, ext: str = ".json"):
    """
    Рекурсивно обходит root_dir, для каждого файла с расширением ext
    загружает JSON, применяет transform_property и пишет результат
    в output_file в формате JSON-массива.
    """
    first_obj = True
    with open(output_file, "w", encoding="utf-8") as fout:
        fout.write("[\n")
        for dirpath, dirnames, filenames in os.walk(root_dir):
            for filename in filenames:
                if not filename.lower().endswith(ext):
                    continue

                file_path = os.path.join(dirpath, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as fin:
                        data = json.load(fin)
                    new_obj = transform_property(data)
                    if new_obj is not None:
                        if not first_obj:
                            fout.write(",\n")
                        fout.write(json.dumps(new_obj, ensure_ascii=False, indent=2))
                        first_obj = False

                except Exception as e:
                    # Выводим в консоль, но продолжаем обработку остальных файлов
                    print(f"Ошибка обработки {file_path}: {e}")

        fout.write("\n]\n")

    print(f"Обработка завершена. Результат записан в {output_file}")

def transform_property(data):
    """
    Преобразует исходный объект в целевую структуру.
    Возвращает dict с ключом "id" или None.
    """
    prop = data.get("props", {}) \
               .get("pageProps", {}) \
               .get("propertyResult", {}) \
               .get("property", {})

    # основные поля
    property_id = prop.get("id")
    url = prop.get("share_url")
    title = prop.get("title")
    prop = data.get("props", {}).get("pageProps", {}).get("propertyResult", {}).get("property", {})

    # Извлекаем основные поля
    property_id = prop.get("id")
    url = prop.get("share_url")
    title = prop.get("title")
    display_address = prop.get("location", {}).get("full_name")
    bedrooms = prop.get("bedrooms")
    bathrooms = prop.get("bathrooms")
    added_on = prop.get("listed_date")
    broker_name = prop.get("broker", {}).get("name")
    agent_name = prop.get("agent", {}).get("name")

    # agentInfo – копируем всю информацию об агенте
    agent_info = prop.get("agent", {})

    # Извлекаем телефон агента из списка контактных опций (первый контакт с типом "phone")
    agent_phone = None
    for contact in prop.get("contact_options", []):
        if contact.get("type") == "phone":
            agent_phone = contact.get("value")
            break

    verified = prop.get("is_verified")
    reference = prop.get("reference")
    broker_license = prop.get("broker", {}).get("license_number")
    broker_info = prop.get("broker", {})

    # Определяем тип цены: если свойство (например) предназначено для аренды – "rent", иначе "sell"
    price_duration = "rent" if prop.get("isRent") else "sell"

    property_type = prop.get("property_type")
    price = prop.get("price", {}).get("value")
    rera_number = None
    rera_obj = prop.get("rera", {})
    if isinstance(rera_obj, dict):
        rera_number = rera_obj.get("number")
    price_currency = prop.get("price", {}).get("currency")

    # Координаты: преобразуем структуру с lat, lon в нужный формат
    coord = prop.get("location", {}).get("coordinates", {})
    coordinates = {
        "latitude": coord.get("lat"),
        "longitude": coord.get("lon")
    }

    offering_type = prop.get("offering_type")

    # Формируем размер с единицей измерения (если оба поля заданы)
    size_val = prop.get("size", {}).get("value")
    size_unit = prop.get("size", {}).get("unit")
    size_min = f"{size_val} {size_unit}" if size_val and size_unit else None

    # Furnishing – например, если значение "YES" или "NO"
    furnishing = prop.get("furnished", "NO")
    # Если требуется нормализовать – можно, например, привести к верхнему регистру
    furnishing = furnishing.upper()

    # Извлекаем список удобств (features) – берем имена из списка amenities
    features = []
    for amenity in prop.get("amenities", []):
        name = amenity.get("name")
        if name:
            features.append(name)

    description = prop.get("description")
    # Если доступен HTML‑вариант описания, можно его использовать; иначе – берем обычное описание
    description_html = prop.get("descriptionHTML") or description

    # Извлекаем список изображений – например, берём URL поля "full" для каждого изображения в свойстве "images"
    images = []
    images_list = prop.get("images", {}).get("property", [])
    for img in images_list:
        full_url = img.get("full")
        if full_url:
            images.append(full_url)

    similar_transactions = prop.get("similar_price_transactions")
    rera_permit_url = None
    if isinstance(rera_obj, dict):
        rera_permit_url = rera_obj.get("permit_validation_url")

    # Формируем итоговый объект согласно требуемой структуре
    transformed = {
        "id": property_id,
        "url": url,
        "title": title,
        "displayAddress": display_address,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "addedOn": added_on,
        "broker": broker_name,
        "agent": agent_name,
        "agentInfo": agent_info,
        "agentPhone": agent_phone,
        "verified": verified,
        "reference": reference,
        "brokerLicenseNumber": broker_license,
        "brokerInfo": broker_info,
        "priceDuration": price_duration,
        "propertyType": property_type,
        "price": price,
        "rera": rera_number,
        "priceCurrency": price_currency,
        "coordinates": coordinates,
        "type": offering_type,
        "sizeMin": size_min,
        "furnishing": furnishing,
        "features": features,
        "description": description,
        "descriptionHTML": description_html,
        "images": images,
        "similarTransactions": similar_transactions,
        "reraPermitUrl": rera_permit_url
    }



    return transformed

def process_all_files(root_dir: str, output_file: str, ext: str = ".json"):
    """
    Рекурсивно обходит root_dir, для каждого файла с расширением ext
    загружает JSON, применяет transform_property, убирает дубликаты по id
    и пишет результат в output_file в формате JSON-массива.
    """
    seen_ids = set()
    first_obj = True

    with open(output_file, "w", encoding="utf-8") as fout:
        fout.write("[\n")

        for dirpath, dirnames, filenames in os.walk(root_dir):
            for filename in filenames:
                if not filename.lower().endswith(ext):
                    continue

                file_path = os.path.join(dirpath, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as fin:
                        data = json.load(fin)

                    new_obj = transform_property(data)
                    if new_obj is None:
                        continue

                    obj_id = new_obj.get("id")
                    # Если id уже встречался — пропускаем
                    if obj_id is not None:
                        if obj_id in seen_ids:
                            print(f"Дубликат пропущен: id={obj_id} (файл {file_path})")
                            continue
                        seen_ids.add(obj_id)

                    # Запись объекта в выходной файл
                    if not first_obj:
                        fout.write(",\n")
                    fout.write(json.dumps(new_obj, ensure_ascii=False, indent=2))
                    first_obj = False

                except Exception as e:
                    print(f"Ошибка обработки {file_path}: {e}")

        fout.write("\n]\n")

    print(f"Обработка завершена. Результат записан в {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Рекурсивно обработать все файлы, убрать дубли по id и сохранить в один JSON"
    )
    parser.add_argument(
        "-i", "--input-dir",
        default=".",
        help="Корневая директория для обхода (по умолчанию текущая)"
    )
    parser.add_argument(
        "-o", "--output-file",
        required=True,
        help="Путь к выходному JSON-файлу"
    )
    parser.add_argument(
        "-e", "--extension",
        default=".json",
        help="Расширение файлов для обработки (по умолчанию .html)"
    )
    args = parser.parse_args()

    process_all_files(args.input_dir, args.output_file, args.extension)
