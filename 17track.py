from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from flask import Flask, render_template, request, send_file
from bs4 import BeautifulSoup
app = Flask(__name__)

# Khởi động trình duyệt WebDriver
service = Service('./chromedriver.exe')  # Đường dẫn đầy đủ đến file ChromeDriver
options = webdriver.ChromeOptions()
options.add_argument('--ignore-ssl-errors=yes')
options.add_argument('--ignore-certificate-errors')
driver = webdriver.Chrome(service=service, options=options)

@app.route('/')
def index():
    return render_template('index.html')

# Đặt mã vận đơn của bạn ở đây
tracking_numbers = [
    '92001903608804805960417187',
    '92001903608804778447849910',
    '92001903608804459794479608',
    '92001903608804960368872881',
    '92001903608804248433283184',
    '92001903608804186966522151',
    '92001903608804362438579742',
    '92001903608804498923837902',
    '92001903608804769923710732',
    '92001903608804958245632215',
    '92001903608804478933971377',
    '92001903608804098797110240',
    '92001903608804024780530184'
]

driver.get('https://www.17track.net/en')

try:
    # Tìm ô tìm kiếm và nhập tất cả các mã vận đơn vào đó
    search_box = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, 'auto-size-textarea'))
    )
    # Nối các mã vận đơn thành một chuỗi cách nhau bởi dấu phẩy
    tracking_numbers_str = ','.join(tracking_numbers)
    search_box.send_keys(tracking_numbers_str)
    
    track_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, '.batch_track_search-area__9BaOs'))
    )
    track_button.click()

    # Đóng thông báo hướng dẫn nếu xuất hiện
    try:
        close_button = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'introjs-skipbutton'))
        )
        close_button.click()
    except:
        pass  # Nếu không có thông báo, bỏ qua

    # Đợi cho trang kết quả tải xong
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'tracklist-item'))
    )

    # Thu thập thông tin từng mã vận đơn
    data = []
    rows = driver.find_elements(By.CLASS_NAME, 'tracklist-item')

    for row in rows:
        try:
            tracking_number = row.find_element(By.CLASS_NAME, 'no-container span').text.strip()
            final_status_at = row.find_element(By.CSS_SELECTOR, '.yqcr-last-event-pc time').text.strip()
            status = row.find_element(By.CSS_SELECTOR, '.text-capitalize span').text.strip()

            # Chờ cho phần tử trn-block xuất hiện trong 10 giây
            trn_block = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "trn-block"))
            )

            # Lấy HTML của phần tử trn-block
            html_content = trn_block.get_attribute('outerHTML')

            # Sử dụng BeautifulSoup để phân tích HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Tìm tất cả các thẻ <time> trong các thẻ <dd> của lớp 'trn-block'
            time_tags = soup.select('.trn-block dd time')

            # Lấy nội dung của thẻ <time> cuối cùng thứ hai
            if len(time_tags) > 1:  # Đảm bảo có ít nhất 2 thẻ <time>
                last_second_time_content = time_tags[-2].get_text()
            else:
                last_second_time_content='N/A'
            status_parts = status.split('(')
            delivery_status = status_parts[0].strip()
            days_in_transit = status_parts[1].replace(')', '').strip() if len(status_parts) > 1 else 'N/A'
            
            data.append([tracking_number, final_status_at, delivery_status, days_in_transit,last_second_time_content])

        except Exception as e:
            print(f"Error processing row: {str(e)}")

finally:
    # Đóng trình duyệt sau khi hoàn thành
    driver.quit()

    try:
        existing_df = pd.read_excel('tracking_info.xlsx', engine='openpyxl')
        df = pd.DataFrame(data, columns=['Tracking Number', 'Final Status At', 'Delivery Status', 'Days in Transit', 'In transit at'])
        combined_df = pd.concat([existing_df, df], ignore_index=True)
    except FileNotFoundError:
        combined_df = pd.DataFrame(data, columns=['Tracking Number', 'Final Status At', 'Delivery Status', 'Days in Transit', 'In transit at'])

    # Ghi dữ liệu vào file Excel
    combined_df.to_excel('tracking_info.xlsx', index=False)
    print("Thông tin vận đơn đã được ghi vào file tracking_info.xlsx")
