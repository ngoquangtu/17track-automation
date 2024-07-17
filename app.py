from flask import Flask, jsonify, render_template, request, send_file
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from bs4 import BeautifulSoup
import threading
import uuid
import os
import time

app = Flask(__name__)
lock = threading.Lock()

UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['RESULTS_FOLDER'] = RESULTS_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

def process_tracking_numbers(tracking_numbers, all_data, results):
    service = Service('./chromedriver.exe')
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-ssl-errors=yes')
    options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Chrome(service=service, options=options)
    driver.get('https://www.17track.net/en')

    try:
        search_box = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, 'auto-size-textarea')))
        tracking_numbers_str = ','.join(tracking_numbers)
        search_box.send_keys(tracking_numbers_str)
        track_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.batch_track_search-area__9BaOs')))
        track_button.click()
        
        try:
            time.sleep(5)
            close_button = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'introjs-skipbutton'))
            )
            close_button.click()
        except:
            pass
        
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'tracklist-item')))
        
        data = []
        rows = driver.find_elements(By.CLASS_NAME, 'tracklist-item')
        for row in rows:
            try:
                tracking_number = row.find_element(By.CLASS_NAME, 'no-container span').text.strip()
                final_status_at = row.find_element(By.CSS_SELECTOR, '.yqcr-last-event-pc time').text.strip()
                status = row.find_element(By.CSS_SELECTOR, '.text-capitalize span').text.strip()

                trn_block = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "trn-block"))
                )

                html_content = trn_block.get_attribute('outerHTML')
                soup = BeautifulSoup(html_content, 'html.parser')
                time_tags = soup.select('.trn-block dd time')

                last_second_time_content = time_tags[-2].get_text() if len(time_tags) > 1 else 'N/A'
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
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')

    if file:
        file_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_FOLDER, file_id + '.xlsx')
        file.save(file_path)
        return jsonify({"status": "success", "file_id": file_id})
    else:
        return jsonify({"status": "error", "message": "No file or tracking numbers provided"})
    
@app.route('/track', methods=['POST'])
def track_shipments():
    file_id = request.form.get('file_id')
    tracking_numbers = request.form.get('tracking_numbers')

    if not file_id and not tracking_numbers:
        return jsonify({"status": "error", "message": "No file or tracking numbers provided"}), 400
    if not tracking_numbers:
        return jsonify({'status': 'error', 'message': 'Tracking numbers are required'})
    if file_id:
        file_path = os.path.join(UPLOAD_FOLDER, file_id + '.xlsx')
    else:
        file_path = None

    len_track_numbers = tracking_numbers.strip().split('\n')
    chunks = [len_track_numbers[i:i+40] for i in range(0, len(len_track_numbers), 40)]
    threads = []
    all_data = []
    results = []
    

    for chunk in chunks:
        thread = threading.Thread(target=process_tracking_numbers, args=(chunk, all_data, results))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()


    if file_path:
        try:
            df = pd.read_excel(file_path)
            all_data_df = pd.DataFrame(all_data, columns=['Tracking Number', 'Final Status At', 'Delivery Status', 'Days In Transit', 'In Transit At'])
            updated_df = pd.concat([df, all_data_df], ignore_index=True)
            updated_df.to_excel(file_path, index=False)
            print("Thông tin vận đơn đã được ghi vào file tracking_info.xlsx")
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})

    return jsonify({"status": "success"})

@app.route('/download/<file_id>')
def download_results(file_id):
    output_file_name = file_id +'.xlsx'
    output_file_path = os.path.join(app.config['UPLOAD_FOLDER'], output_file_name)
    return send_file(output_file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
