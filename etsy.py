import requests
from bs4 import BeautifulSoup
import pandas as pd

# Define the URL of the Etsy search results page
url = "https://www.etsy.com/search?q=laptop+stand"  # Replace with your actual search URL

# Define headers to include a User-Agent
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Send an HTTP GET request to the URL
response = requests.get(url, headers=headers)

# Check if the request was successful
if response.status_code == 200:
    # Parse the HTML content
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all product items
    items = soup.select('.v2-listing-card')  # Adjust based on the actual class name
    data = []

    for item in items:
        try:
            # Extract title
            title = item.select_one('.v2-listing-card__title').get_text(strip=True) if item.select_one('.v2-listing-card__title') else 'N/A'
            
            # Extract price
            price = item.select_one('.currency-value').get_text(strip=True) if item.select_one('.currency-value') else 'N/A'
            
            # Extract image URL
            image_tag = item.select_one('.v2-listing-card__img img')
            image_url = image_tag['src'] if image_tag and 'src' in image_tag.attrs else 'N/A'
            
            # Append data to list
            data.append([title, price, image_url])
        except Exception as e:
            print(f"Error extracting data for an item: {e}")

    # Create a DataFrame and save to Excel
    df = pd.DataFrame(data, columns=['Title', 'Price', 'Image URL'])
    df.to_excel('etsy_products.xlsx', index=False)
    print("Data successfully written to etsy_products.xlsx")
else:
    print(f"Failed to retrieve the page. Status code: {response.status_code}")
