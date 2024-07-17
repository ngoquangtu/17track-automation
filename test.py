    from flask import Flask, jsonify, render_template, request, send_file
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import pandas as pd
    from bs4 import BeautifulSoup
    import threading
    import requests
    import time
    import uuid  # Thêm thư viện này để tạo ID duy nhất cho mỗi tệp captcha

    app = Flask(__name__)
    lock = threading.Lock()  # Tạo lock để đồng bộ hóa các luồng

    # Hàm giải mã captcha
    def solve_captcha(image_path):
        api_key = '30c92bb3e41fcc468cf4c4ab6d15bfe3'
        data = {
            'key': api_key,
            'method': 'post',
            'json': 1
        }
        files = {'file': open(image_path, 'rb')}
        response = requests.post('http://2captcha.com/in.php', files=files, data=data)
        if response.status_code != 200 or response.json().get('status') != 1:
            print("Error uploading captcha image")
            return None

        request_id = response.json().get('request')

        # Chờ giải mã captcha
        while True:
            response = requests.get(f"http://2captcha.com/res.php?key={api_key}&action=get&id={request_id}&json=1")
            result = response.json()
            if result.get('status') == 1:
                return result.get('request')
            time.sleep(5)
        return None

    # Hàm xử lý các mã vận đơn
    def process_tracking_numbers(tracking_numbers, all_data,results):
        service = Service('./chromedriver.exe')  # Đường dẫn đầy đủ đến file ChromeDriver
        options = webdriver.ChromeOptions()
        options.add_argument('--ignore-ssl-errors=yes')
        options.add_argument('--ignore-certificate-errors')
        driver = webdriver.Chrome(service=service, options=options)
        driver.get('https://www.17track.net/en')

        try:
            search_box = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, 'auto-size-textarea'))
            )
            tracking_numbers_str = ','.join(tracking_numbers)
            search_box.send_keys(tracking_numbers_str)
            track_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.batch_track_search-area__9BaOs'))
            )
            track_button.click()
        
            try:
                submit_button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'button.btn-submit[data-yq-events="submitCode"]')))
                captcha_image = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'img.jaChangeCode')))
                # submit_button = driver.find_element(By.CSS_SELECTOR, 'button.btn-submit[data-yq-events="submitCode"]')
                # captcha_image = driver.find_element(By.CSS_SELECTOR, 'img.jaChangeCode')
                captcha_image_url = captcha_image.get_attribute('src')
                print(captcha_image_url)
                            # Tải ảnh captcha về
                captcha_response = requests.get(captcha_image_url)
                captcha_image_path = f'captcha_{uuid.uuid4().hex}.png'  # Tạo tên tệp duy nhất cho mỗi captcha
                with open(captcha_image_path, 'wb') as f:
                    f.write(captcha_response.content)
                captcha_text = solve_captcha(captcha_image_path)
                captcha_box = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input.ver-input'))  # Thay đổi selector đến selector thực tế của captcha input
                )
                if captcha_text:
                    print(captcha_text)
                    captcha_box.send_keys(captcha_text)
                    submit_button.click()
                else:
                    pass
            except:
                results.append({"status": "error", "message": "Failed to solve CAPTCHA"})            
                return
            try:
                close_button = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'introjs-skipbutton'))
                    )
                close_button.click()
            except:
                pass
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
                        last_second_time_content = 'N/A'
                    status_parts = status.split('(')
                    delivery_status = status_parts[0].strip()
                    days_in_transit = status_parts[1].replace(')', '').strip() if len(status_parts) > 1 else 'N/A'

                    data.append([tracking_number, final_status_at, delivery_status, days_in_transit, last_second_time_content])

                except Exception as e:
                    print(f"Error processing row: {str(e)}")

            with lock:
                all_data.extend(data)
                results.append({"status": "success", "message": "Tracking completed"})

        finally:
            driver.quit()

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/track', methods=['POST'])
    def track_shipments():
        tracking_numbers = request.form.get('tracking_numbers').strip().split('\r\n')
        chunks = [tracking_numbers[i:i + 40] for i in range(0, len(tracking_numbers), 40)]
        threads = []
        all_data = []
        results=[]

        for chunk in chunks:
            thread = threading.Thread(target=process_tracking_numbers, args=(chunk, all_data,results))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()

        # Write to Excel file
        with lock:
            try:
                existing_df = pd.read_excel('tracking_info.xlsx', engine='openpyxl')
                df = pd.DataFrame(all_data, columns=['Tracking Number', 'Final Status At', 'Delivery Status', 'Days in Transit', 'In transit at'])
                combined_df = pd.concat([existing_df, df], ignore_index=True)
            except FileNotFoundError:
                combined_df = pd.DataFrame(all_data, columns=['Tracking Number', 'Final Status At', 'Delivery Status', 'Days in Transit', 'In transit at'])

            combined_df.to_excel('tracking_info.xlsx', index=False)
            print("Thông tin vận đơn đã được ghi vào file tracking_info.xlsx")

        return jsonify(results)


    if __name__ == '__main__':
        app.run(debug=True)
