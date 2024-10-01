import requests
from bs4 import BeautifulSoup
import os
import csv

# Function to download images
def download_image(url, save_path):
    img_data = requests.get(url).content
    with open(save_path, 'wb') as handler:
        handler.write(img_data)

# Function to crawl a product detail page and extract detailed information
def crawl_product_detail(product_url):
    response = requests.get(product_url)
    if response.status_code != 200:
        print(f"Failed to retrieve the product page {product_url}. Status code: {response.status_code}")
        return None
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extract detailed product information
    product_name_tag = soup.find('h1')
    product_name = product_name_tag.text.strip() if product_name_tag else 'No Name'
    print(f"Product Name: {product_name}")
    
    price_tag = soup.find('span', class_='pro-price')
    price = price_tag.text.strip() if price_tag else 'No Price'
    print(f"Price: {price}")
    
    # Extract image URLs
    img_tags = soup.select('ul.productList-slider li.product-gallery a img')
    img_urls = []
    for img_tag in img_tags:
        img_url = img_tag.get('src')
        if 'master' in img_url:
            if img_url.startswith('//'):
                img_url = 'https:' + img_url
            img_urls.append(img_url)
            print(f"Image URL: {img_url}")
    
    # Extract sizes
    size_tags = soup.select('div#variant-swatch-0 div.swatch-element')
    sizes = [size_tag.get('data-value') for size_tag in size_tags]
    print(f"Sizes: {sizes}")
    
    # Extract colors
    color_tags = soup.select('div#variant-swatch-1 div.swatch-element')
    colors = [color_tag.get('data-value') for color_tag in color_tags]
    print(f"Colors: {colors}")
    
    return {
        'name': product_name,
        'price': price,
        'images': img_urls,
        'sizes': sizes,
        'colors': colors
    }

# Function to crawl a category page and extract product data
def crawl_category(base_url, category):
    page = 1
    all_product_data = []

    while True:
        url = f"{base_url}?page={page}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to retrieve the page {url}. Status code: {response.status_code}")
            break
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Log the response content for debugging
        with open(f'response_{category}_page_{page}.html', 'w', encoding='utf-8') as file:
            file.write(soup.prettify())
        
        products = soup.find_all('div', class_='product-inner')
        print(f"Found {len(products)} products on page {page} of category {category}")
        
        if len(products) == 0:
            print(f"No products found on page {page} of category {category}. Stopping pagination.")
            break
        
        for product in products:
            try:
                # Extract product detail URL
                product_link_tag = product.find('a', class_='quickview-product')
                product_url = product_link_tag['href'] if product_link_tag else ''
                if not product_url.startswith('http'):
                    product_url = 'https://nghienbongda.vn' + product_url
                print(f"Product URL: {product_url}")
                
                # Extract SKU from URL
                sku = product_url.split('/')[-1]
                print(f"SKU: {sku}")
                
                # Create a directory for the product images
                product_image_dir = os.path.join('images', sku)
                if not os.path.exists(product_image_dir):
                    os.makedirs(product_image_dir)
                
                # Crawl the product detail page
                product_detail = crawl_product_detail(product_url)
                if product_detail:
                    # Download images
                    for img_url in product_detail['images']:
                        img_filename = os.path.join(product_image_dir, img_url.split('/')[-1])
                        download_image(img_url, img_filename)
                        print(f"Image saved as: {img_filename}")
                    
                    all_product_data.append([category, product_detail['name'], sku, ', '.join(product_detail['images']), product_detail['price'], ', '.join(product_detail['sizes']), ', '.join(product_detail['colors'])])
            except Exception as e:
                print(f"Error processing product: {e}")
        
        page += 1

    return all_product_data

# Function to crawl the main website for 'collections' links and gather all product data
def crawl_website(main_url):
    response = requests.get(main_url)
    if response.status_code != 200:
        print(f"Failed to retrieve the main page. Status code: {response.status_code}")
        return
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Log the response content for debugging
    with open('response_main.html', 'w', encoding='utf-8') as file:
        file.write(soup.prettify())
    
    # Find all collection links
    collection_links = soup.find_all('a', href=True)
    collection_urls = set()
    for link in collection_links:
        href = link['href']
        if 'collections' in href:
            full_url = main_url.rstrip('/') + href
            collection_urls.add(full_url)
    
    print(f"Found {len(collection_urls)} collection links")
    
    all_product_data = []
    
    # Create a directory to save images
    if not os.path.exists('images'):
        os.makedirs('images')
    
    for url in collection_urls:
        category = url.split('/')[-1]
        print(f"Crawling category: {category}")
        product_data = crawl_category(url, category)
        all_product_data.extend(product_data)
    
    # Write all product data to CSV file
    with open('product_data.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Category', 'Product Name', 'SKU', 'Image URLs', 'Price', 'Sizes', 'Colors'])
        writer.writerows(all_product_data)
        print('Product data saved to product_data.csv')

# Main URL of the website
main_url = 'https://nghienbongda.vn/'

# Call the function to crawl the website
crawl_website(main_url)
