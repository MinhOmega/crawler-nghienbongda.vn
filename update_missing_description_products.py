import json
import logging
import os
import shutil
import time
from datetime import datetime
from typing import Tuple, Dict, List
import requests

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('description_update.log'),
        logging.StreamHandler()
    ]
)

def generate_default_description(product_name: str) -> Tuple[str, str]:
    """Generate default descriptions used to identify failed products."""
    return (
        f"Khám phá {product_name} - Sản phẩm thể thao chất lượng cao với thiết kế hiện đại và thoải mái.",
        f"{product_name} - Trang phục thể thao chất lượng cao"
    )

def is_default_description(description: str, short_description: str, product_name: str) -> bool:
    """Check if the product has default descriptions."""
    default_desc, default_short_desc = generate_default_description(product_name)
    return description == default_desc and short_description == default_short_desc

def get_ollama_description(product_name: str) -> Tuple[str, str]:
    """Get product descriptions from Ollama with retry mechanism."""
    default_desc = generate_default_description(product_name)
    
    prompt = f"""Tạo một mô tả sản phẩm và mô tả ngắn gọn cho một sản phẩm thuộc bộ sưu tập thể thao trên trang thương mại điện tử. Mô tả cần phải chi tiết, hấp dẫn và tập trung vào các tính năng đặc biệt của sản phẩm thể thao, lợi ích sử dụng, cũng như các ưu điểm về chất lượng và hiệu suất. 
    
Trả về phản hồi theo định dạng JSON sau và không có từ nào khác ngoài định dạng json đó. Ngoài ra ở mô tả sản phẩm sẽ được sử dụng với dạng html và sẽ được sử dụng vào CKEditor sau này. Tối thiểu phải có 300 từ:

{{
  "description": "Mô tả chi tiết về sản phẩm thể thao, bao gồm các tính năng nổi bật, lợi ích khi sử dụng, chất liệu, thiết kế và sự phù hợp cho các hoạt động thể thao cụ thể.",
  "short_description": "Mô tả ngắn gọn về sản phẩm thể thao, tập trung vào những tính năng và lợi ích chính."
}}

Tên sản phẩm thể thao: {product_name}"""
    
    max_retries = 3
    retry_delay = 2  # seconds

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
                response_text = result.get('response', '').strip()
                
                logging.debug(f"Raw Ollama Response: {response_text}")
                
                try:
                    if not response_text:
                        logging.error("Empty response received from Ollama")
                        raise ValueError("Empty response from Ollama")

                    descriptions = json.loads(response_text)
                    
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

def backup_json(json_file: str):
    """Create a backup of the existing JSON file."""
    backup_file = f"{json_file}.backup.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        shutil.copy(json_file, backup_file)
        logging.info(f"Backup created: {backup_file}")
    except Exception as e:
        logging.error(f"Failed to create backup of {json_file}: {str(e)}")

def update_product_descriptions(json_file: str):
    """Update products with default descriptions in the JSON file."""
    if not os.path.exists(json_file):
        logging.error(f"{json_file} does not exist. Exiting.")
        return
    
    # Backup the original JSON file
    backup_json(json_file)
    
    # Load products from JSON
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            products = json.load(f)
        logging.info(f"Loaded {len(products)} products from {json_file}")
    except Exception as e:
        logging.error(f"Failed to read {json_file}: {str(e)}")
        return
    
    # Identify products with default descriptions
    products_to_update = []
    for product in products:
        if is_default_description(product.get('description', ''), product.get('short_description', ''), product.get('product_name', '')):
            products_to_update.append(product)
    
    logging.info(f"Found {len(products_to_update)} products with default descriptions to update.")
    
    if not products_to_update:
        logging.info("No products with default descriptions found. Exiting.")
        return
    
    # Initialize counters and lists
    success_count = 0
    failed_products = []
    
    for product in products_to_update:
        product_name = product.get('product_name', 'Unnamed Product')
        logging.info(f"Updating descriptions for product: {product_name}")
        description, short_description = get_ollama_description(product_name)
        
        # Check if descriptions have been updated (i.e., not default)
        if not is_default_description(description, short_description, product_name):
            product['description'] = description
            product['short_description'] = short_description
            product['updatedAt'] = datetime.now().isoformat()
            success_count += 1
            logging.info(f"Successfully updated descriptions for product: {product_name}")
        else:
            failed_products.append(product_name)
            logging.error(f"Failed to update descriptions for product: {product_name}")
    
    # Save the updated products back to JSON
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        logging.info(f"Successfully updated {success_count} product descriptions in {json_file}")
    except Exception as e:
        logging.error(f"Failed to write updates to {json_file}: {str(e)}")
        return
    
    # Log failed updates
    if failed_products:
        logging.error(f"Failed to update descriptions for {len(failed_products)} products:")
        for pname in failed_products:
            logging.error(f"- {pname}")
        
        # Optionally, save failed products to a separate file
        failed_log = 'failed_description_updates.json'
        try:
            with open(failed_log, 'w', encoding='utf-8') as f:
                json.dump(failed_products, f, indent=2, ensure_ascii=False)
            logging.info(f"Written {len(failed_products)} failed products to {failed_log}")
        except Exception as e:
            logging.error(f"Failed to write failed products to {failed_log}: {str(e)}")
    else:
        logging.info("All targeted product descriptions were successfully updated.")

def main():
    json_file = 'products.json'
    
    # Check if Ollama server is accessible before proceeding
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=10)
        if response.status_code == 200:
            logging.info("Ollama server is accessible.")
        else:
            logging.error(f"Ollama server returned status code {response.status_code}. Exiting.")
            return
    except Exception as e:
        logging.error(f"Failed to connect to Ollama server: {str(e)}. Exiting.")
        return
    
    # Proceed to update product descriptions
    update_product_descriptions(json_file)
    logging.info("Description update process completed.")

if __name__ == "__main__":
    main()
