import csv
import json
from datetime import datetime
import requests
import time
from typing import Tuple, Dict, List
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('product_processing.log'),
        logging.StreamHandler()
    ]
)

def get_category_ids(category_path):
    # Category mapping based on the provided structure
    category_map = {
        'ao-bong-da-ban-player-2022': [1, 2, 3],  # Sản phẩm > Áo bóng đá > Áo bóng đá bản Player
        'ao-bong-da-ban-fan': [1, 2, 4],  # Sản phẩm > Áo bóng đá > Áo bóng đá bản Fan
        'giay-puma': [1, 5, 6],  # Sản phẩm > Giày bóng đá > Giày Puma
        'giay-nike': [1, 5, 7],  # Sản phẩm > Giày bóng đá > Giày Nike
        'giay-adidas': [1, 5, 8],  # Sản phẩm > Giày bóng đá > Giày Adidas
        'giay-bong-da': [1, 5],  # Sản phẩm > Giày bóng đá
        'frontpage': [1],  # Sản phẩm
        'all': [1],  # Sản phẩm
        'ao-giu-nhiet': [1]  # Sản phẩm
    }
    
    return category_map.get(category_path, [])

def generate_default_description(product_name: str) -> Tuple[str, str]:
    """Generate default descriptions when Ollama fails"""
    return (
        f"Khám phá {product_name} - Sản phẩm thể thao chất lượng cao với thiết kế hiện đại và thoải mái.",
        f"{product_name} - Trang phục thể thao chất lượng cao"
    )

def check_ollama_server():
    """Check if Ollama server is running and accessible"""
    try:
        response = requests.get('http://localhost:11434/api/tags')
        return response.status_code == 200
    except Exception:
        return False

def get_ollama_description(product_name: str) -> Tuple[str, str]:
    """Get product descriptions from Ollama"""
    default_desc = generate_default_description(product_name)
    
    prompt = f"""Tạo một mô tả sản phẩm và mô tả ngắn gọn cho một sản phẩm thuộc bộ sưu tập thể thao trên trang thương mại điện tử. Mô tả cần phải chi tiết, hấp dẫn và tập trung vào các tính năng đặc biệt của sản phẩm thể thao, lợi ích sử dụng, cũng như các ưu điểm về chất lượng và hiệu suất. 

Trả về phản hồi theo định dạng JSON sau và không có từ nào khác ngoài định dạng json đó. Ngoài ra ở mô tả sản phẩm sẽ được sử dụng với dạng html và sẽ được sử dụng vào CKEditor sau này. Tối thiểu phải có 300 từ:

{{
  "description": "Mô tả chi tiết về sản phẩm thể thao, bao gồm các tính năng nổi bật, lợi ích khi sử dụng, chất liệu, thiết kế và sự phù hợp cho các hoạt động thể thao cụ thể.",
  "short_description": "Mô tả ngắn gọn về sản phẩm thể thao, tập trung vào những tính năng và lợi ích chính."
}}

Tên sản phẩm thể thao: {product_name}"""

    max_retries = 3
    retry_delay = 2

    logging.info(f"Processing product: {product_name}")
    logging.debug(f"Sending prompt to Ollama: {prompt}")

    for attempt in range(max_retries):
        try:
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=30
            )
            
            logging.debug(f"Attempt {attempt + 1} - Status code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                response_text = result['response']
                
                logging.debug(f"Raw Ollama Response: {response_text}")
                
                try:
                    # Add response validation
                    if not response_text.strip():
                        logging.error("Empty response received from Ollama")
                        raise ValueError("Empty response from Ollama")

                    descriptions = json.loads(response_text)
                    
                    # Validate the required fields exist
                    if not all(key in descriptions for key in ['description', 'short_description']):
                        logging.error(f"Missing required fields in response: {descriptions}")
                        raise ValueError("Invalid response format")

                    logging.info(f"Successfully processed description for: {product_name}")
                    return (
                        descriptions.get('description', default_desc[0]),
                        descriptions.get('short_description', default_desc[1])
                    )
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON from Ollama response for product: {product_name}")
                    logging.error(f"JSON Parse Error: {str(e)}")
                    logging.error(f"Response text causing error: {response_text}")
                    if attempt < max_retries - 1:
                        continue
                    return default_desc
            else:
                logging.error(f"HTTP Error {response.status_code} for product: {product_name}")
                logging.error(f"Response content: {response.text}")
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed for product {product_name}: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error processing {product_name}: {str(e)}", exc_info=True)
            
        if attempt < max_retries - 1:
            logging.warning(f"Attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
        else:
            logging.error(f"All attempts failed for product: {product_name}")
            return default_desc

    return default_desc

def create_product_dict(row: Dict, description: str, short_description: str) -> Dict:
    """Create a product dictionary from row data and descriptions"""
    price_str = row['Price'].replace('₫', '').replace(',', '').strip()
    price = float(price_str)
    
    has_sizes = 'Sizes' in row and row['Sizes'].strip()
    has_colors = 'Colors' in row and row['Colors'].strip()
    product_type = "CONFIGURABLE" if (has_sizes or has_colors) else "SIMPLE"
    category_ids = get_category_ids(row['Category'])
    
    # Create base product dictionary
    product = {
        "product_name": row['Product Name'],
        "product_sku": row['SKU'],
        "categoryIds": category_ids,
        "price": price,
        "special_price": None,
        "fallbackPrice": price,
        "salable_qty": 0,
        "short_description": short_description,
        "description": description,
        "mediaGallery": [
            {
                "url": url.strip(),
                "alt": row['Product Name'],
                "label": row['Product Name'],
                "position": idx + 1,
                "isDisabled": False,
                "isDeleted": False,
                "createdAt": datetime.now().isoformat(),
                "updatedAt": datetime.now().isoformat(),
                "deletedAt": None
            }
            for idx, url in enumerate(row['Image URLs'].split(','))
        ],
        "product_type": product_type,
        "variants": [],
        "attributes": [],
        "isDisabled": False,
        "isDeleted": False,
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "deletedAt": None
    }
    
    # Add variants and attributes if product is configurable
    if product_type == "CONFIGURABLE":
        current_timestamp = datetime.now().isoformat()
        
        if has_sizes:
            sizes = [size.strip() for size in row['Sizes'].split(',')]
            size_attribute = {
                "code": "size",
                "name": "Size",
                "value": "size",
                "isEnabled": True,
                "createdAt": current_timestamp,
                "updatedAt": current_timestamp,
                "deletedAt": None
            }
            product["attributes"].append(size_attribute)
            
            size_variant = {
                "attributes": [
                    {
                        "code": "size",
                        "name": "Size",
                        "value": size,
                        "priceAdjustment": 0,
                        "createdAt": current_timestamp,
                        "updatedAt": current_timestamp
                    }
                    for size in sizes
                ],
                "price": price,
                "stockQuantity": 0,
                "name": "Size",
                "code": "size",
                "imageUrl": product["mediaGallery"][0]["url"] if product["mediaGallery"] else "",
                "isDisabled": False,
                "isDeleted": False,
                "createdAt": current_timestamp,
                "updatedAt": current_timestamp
            }
            product["variants"].append(size_variant)

        if has_colors:
            colors = [color.strip() for color in row['Colors'].split(',')]
            color_attribute = {
                "code": "color",
                "name": "Color",
                "value": "color",
                "isEnabled": True,
                "createdAt": current_timestamp,
                "updatedAt": current_timestamp,
                "deletedAt": None
            }
            product["attributes"].append(color_attribute)
            
            color_variant = {
                "attributes": [
                    {
                        "code": "color",
                        "name": "Color",
                        "value": color,
                        "priceAdjustment": 0,
                        "createdAt": current_timestamp,
                        "updatedAt": current_timestamp
                    }
                    for color in colors
                ],
                "price": price,
                "stockQuantity": 0,
                "name": "Color",
                "code": "color",
                "imageUrl": product["mediaGallery"][0]["url"] if product["mediaGallery"] else "",
                "isDisabled": False,
                "isDeleted": False,
                "createdAt": current_timestamp,
                "updatedAt": current_timestamp
            }
            product["variants"].append(color_variant)
    
    return product

def convert_csv_to_json():
    # Read CSV file
    with open('product_data.csv', 'r', encoding='utf-8') as csvfile:
        products = list(csv.DictReader(csvfile))
    
    # Process products sequentially
    results = []
    for product_data in products:
        description, short_description = get_ollama_description(product_data['Product Name'])
        product = create_product_dict(product_data, description, short_description)
        results.append(product)
    
    # Write results to JSON file
    with open('products.json', 'w', encoding='utf-8') as jsonfile:
        json.dump(results, jsonfile, indent=2, ensure_ascii=False)
    
    print('CSV file successfully processed and converted to JSON')

if __name__ == "__main__":
    logging.info("Starting CSV to JSON conversion")
    convert_csv_to_json()
    logging.info("Finished CSV to JSON conversion") 