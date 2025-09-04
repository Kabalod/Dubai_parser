#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import time
import json
import glob
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Константы
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

DEFAULT_COOKIES = {
    "pf_essential": "1",
    "pf_analytics": "1",
    "pf_performance": "1",
}

BASE_SEARCH_URL = "https://www.propertyfinder.ae/en/search?l=1&c=1&t=1&fu=0&rp=y&ob=nd"

def build_page_url(base_url, page_num):
    """Build URL for specific page number."""
    if "page=" in base_url:
        return re.sub(r"page=\d+", f"page={page_num}", base_url)
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}page={page_num}"

def extract_links_from_page(html):
    """Extract property links from search page HTML."""
    soup = BeautifulSoup(html, "lxml")
    section = soup.select_one("[aria-label='Properties']")
    if not section:
        return []
    return [
        a["href"]
        for a in section.select("[data-testid='property-card-link']")
        if a.has_attr("href")
    ]

def extract_first_script(html):
    """Extract JSON data from first script tag."""
    soup = BeautifulSoup(html, "lxml")
    script = soup.body.find("script")
    text = script.string or ""
    idx = text.find("{")
    return text[idx:] if idx >= 0 else ""

def get_file_name_from_url(url, ext=".json"):
    """Generate filename from URL."""
    base = os.path.basename(urlparse(url).path) or f"page_{int(time.time())}"
    name = re.sub(r"\W+", "_", base)
    return f"{name}{ext}"

def process_page(session, url, page_num, retries=3):
    """Process a single search page and return property links."""
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            links = extract_links_from_page(r.text)
            print(f"[Page {page_num}] Found {len(links)} links")
            return links
        except Exception as e:
            if attempt == retries - 1:
                print(f"[Page {page_num}] Error after {retries} attempts: {e}")
                return []
            time.sleep(2 ** attempt)  # exponential backoff

def process_property(session, link, json_dir, idx, total):
    """Process a single property page and save JSON data."""
    try:
        r = session.get(link, timeout=30)
        r.raise_for_status()
        script = extract_first_script(r.text)
        if script:
            fname = get_file_name_from_url(link, ext=".json")
            path = os.path.join(json_dir, fname)
            with open(path, "w", encoding="utf-8") as outf:
                outf.write(script)
            print(f"[Property {idx}/{total}] Saved: {link}")
    except Exception as e:
        print(f"[Property {idx}/{total}] Error processing {link}: {e}")

def transform_property(data):
    """Transform raw property data into standardized format."""
    prop = data  # now the JSON is at the root

    # Extract fields
    property_id = prop.get("id")
    url = prop.get("share_url")
    title = prop.get("title")
    display_address = prop.get("location", {}).get("full_name")
    bedrooms = prop.get("bedrooms")
    bathrooms = prop.get("bathrooms")
    added_on = prop.get("listed_date")
    broker_name = prop.get("broker", {}).get("name")
    agent_name = prop.get("agent", {}).get("name")
    agent_info = prop.get("agent", {})

    # phone
    agent_phone = None
    for c in prop.get("contact_options", []):
        if c.get("type") == "phone":
            agent_phone = c.get("value")
            break

    verified = prop.get("is_verified")
    reference = prop.get("reference")
    broker_license = prop.get("broker", {}).get("license_number")
    broker_info = prop.get("broker", {})
    price_duration = "rent" if prop.get("isRent") else "sell"
    property_type = prop.get("property_type")
    price = prop.get("price", {}).get("value")
    rera_obj = prop.get("rera", {}) or {}
    rera_number = rera_obj.get("number")
    price_currency = prop.get("price", {}).get("currency")

    coord = prop.get("location", {}).get("coordinates", {}) or {}
    coordinates = {
        "latitude": coord.get("lat"),
        "longitude": coord.get("lon"),
    }

    offering_type = prop.get("offering_type")
    size_val = prop.get("size", {}).get("value")
    size_unit = prop.get("size", {}).get("unit")
    size_min = f"{size_val} {size_unit}" if size_val and size_unit else None

    furnishing = prop.get("furnished", "NO").upper()

    features = [
        a.get("name")
        for a in prop.get("amenities", [])
        if a.get("name")
    ]

    description = prop.get("description")
    description_html = prop.get("descriptionHTML") or description

    images = [
        img.get("full")
        for img in prop.get("images", {}).get("property", [])
        if img.get("full")
    ]

    similar_transactions = prop.get("similar_price_transactions")
    rera_permit_url = rera_obj.get("permit_validation_url")

    return {
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
        "reraPermitUrl": rera_permit_url,
    }

def process_directory(input_dir, output_file, ext=".json"):
    """Process all JSON files in directory and save transformed data."""
    seen = set()
    first = True
    with open(output_file, "w", encoding="utf-8") as fout:
        fout.write("[\n")
        for dirpath, _, files in os.walk(input_dir):
            for fn in files:
                if not fn.lower().endswith(ext):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    obj = transform_property(data)
                    if obj is None:
                        continue
                    oid = obj.get("id")
                    if oid and oid in seen:
                        continue
                    if oid:
                        seen.add(oid)
                    if not first:
                        fout.write(",\n")
                    fout.write(json.dumps(obj, ensure_ascii=False, indent=2))
                    first = False
                except Exception as e:
                    print(f"Error processing {path}: {e}")
        fout.write("\n]\n")
    print(f"Processing complete. Output written to {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="PropertyFinder.ae Scraper: Scrape, extract JSON, merge & transform"
    )
    parser.add_argument("--threads", type=int, default=7, 
                      help="Number of threads to use (default: 7)")
    parser.add_argument("--start-page", type=int, default=1, 
                      help="Starting page number (default: 1)")
    parser.add_argument("--end-page", type=int, default=360, 
                      help="Ending page number (default: 360)")
    parser.add_argument("--output-dir", type=str, default="scraped_data",
                      help="Output directory (default: scraped_data)")
    
    args = parser.parse_args()

    # Create output directories
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(args.output_dir, f"scrape_{ts}")
    links_file = os.path.join(output_dir, "links.txt")
    json_dir = os.path.join(output_dir, "json_data")
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(json_dir, exist_ok=True)

    # Initialize session with default headers and cookies
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    session.cookies.update(DEFAULT_COOKIES)

    # 1) Gather links from all pages in parallel
    all_links = set()
    page_range = range(args.start_page, args.end_page + 1)
    
    print(f"Starting to scrape {len(page_range)} pages with {args.threads} threads...")
    
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = []
        for page_num in page_range:
            url = build_page_url(BASE_SEARCH_URL, page_num)
            futures.append(executor.submit(process_page, session, url, page_num))
        
        for future in as_completed(futures):
            links = future.result()
            if links:
                all_links.update(links)

    # Save all links to file
    with open(links_file, "w", encoding="utf-8") as lf:
        for l in sorted(all_links):
            lf.write(l + "\n")
    print(f"Saved {len(all_links)} links to {links_file}")

    # 2) Process all properties in parallel
    print(f"Processing {len(all_links)} properties with {args.threads} threads...")
    
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = []
        for idx, link in enumerate(sorted(all_links), 1):
            futures.append(executor.submit(
                process_property, session, link, json_dir, idx, len(all_links)
            ))
        
        # Wait for all futures to complete
        for future in as_completed(futures):
            pass  # Results are handled in the process_property function

    # 3) Transform & dedupe into final output
    final_out = os.path.join(output_dir, "properties.json")
    process_directory(json_dir, final_out, ext=".json")

    print("Scraping completed successfully!")
    print(f"Results saved in: {output_dir}")
    time.sleep(0.36)

if __name__ == "__main__":
    main()