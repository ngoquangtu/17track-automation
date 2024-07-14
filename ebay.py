import requests
from bs4 import BeautifulSoup
import pandas as pd

url = "https://www.ebay.com/sch/i.html?_nkw=laptop"
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

items = soup.select('.s-item')
data = []

for item in items:
    title = item.select_one('.s-item__title').get_text() if item.select_one('.s-item__title') else 'N/A'
    price = item.select_one('.s-item__price').get_text() if item.select_one('.s-item__price') else 'N/A'
    image_tag = item.select_one('.s-item__image-img, .s-item__image-wrapper img')  # Thử thêm một selector khác
    image_url = image_tag['src'] if image_tag else 'N/A'
    data.append([title, price, image_url])

# Ghi dữ liệu vào file Excel
df = pd.DataFrame(data, columns=['Title', 'Price', 'Image URL'])
df.to_excel('ebay_products.xlsx', index=False)


