from flask import Flask, jsonify, render_template, request, send_file
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
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
    service = Service('chromedriver.exe')
    options = webdriver.ChromeOptions()
    options.add_argument('--ignore-ssl-errors=yes')
    options.add_argument('--ignore-certificate-errors')
    driver = webdriver.Chrome(service=service, options=options)
    driver.get('https://www.17track.net/en')

    try:
        search_box = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, 'auto-size-textarea')))

        tracking_numbers = [str(num) for num in tracking_numbers if pd.notna(num)]
        tracking_numbers_str = ','.join(tracking_numbers)
        
        search_box.send_keys(tracking_numbers_str)
        track_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, '.batch_track_search-area__9BaOs')))
        track_button.click()
        
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, 'captcha-container')))
            results.append({"status": "error", "message": "CAPTCHA detected. Please solve it manually."})
            return
        except Exception as e:
            pass

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

                trn_block = row.find_element(By.CLASS_NAME, "trn-block")
                html_content = trn_block.get_attribute('outerHTML')
                soup = BeautifulSoup(html_content, 'html.parser')
                time_tags = soup.select('.trn-block dd time')

                if len(time_tags) > 1:
                    last_second_time_content = time_tags[-2].get_text()
                else:
                    last_second_time_content = 'N/A'
                status_parts = status.split('(')
                delivery_status = status_parts[0].strip()
                days_in_transit = status_parts[1].replace(')', '').strip() if len(status_parts) > 1 else 'N/A'

                data.append([tracking_number, delivery_status, last_second_time_content, final_status_at, days_in_transit])
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
        return jsonify({"status": "error", "message": "No file uploaded"})

@app.route('/track', methods=['POST'])
def track_shipments():
    file_id = request.form.get('file_id')
    start_row = int(request.form.get('start_row', 0))
    end_row = int(request.form.get('end_row', None))

    if file_id:
        file_path = os.path.join(UPLOAD_FOLDER, file_id + '.xlsx')
        df = pd.read_excel(file_path)
        
        if end_row is None or end_row > len(df):
            end_row = len(df)

        tracking_numbers = df['Tracking'].iloc[start_row:end_row].tolist()
    else:
        return jsonify({'status': 'error', 'message': 'File ID not provided'})

    chunks = [tracking_numbers[i:i+40] for i in range(0, len(tracking_numbers), 40)]
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
            all_data_df = pd.DataFrame(all_data, columns=['Tracking', 'Status', 'In transit at', 'Final status at', 'Time to final status at'])
            all_data_df['In transit at'] = pd.to_datetime(all_data_df['In transit at'], format='%Y-%m-%d %H:%M', errors='coerce')
            all_data_df['Final status at'] = pd.to_datetime(all_data_df['Final status at'], format='%Y-%m-%d %H:%M', errors='coerce')
            df['Processed at'] = pd.to_datetime(df['Processed at'], format='%Y-%m-%d %H:%M', errors='coerce')

            merged_df = pd.merge(all_data_df, df[['Tracking', 'Processed at']], on='Tracking', how='left')
            merged_df['Time in transit at'] = (merged_df['In transit at'] - merged_df['Processed at']).dt.total_seconds() / 3600 +12
            merged_df['Refund'] = merged_df['Time in transit at'] > 48

            df['In transit at'] = pd.to_datetime(df['In transit at'], errors='coerce')
            df['Final status at'] = pd.to_datetime(df['Final status at'], errors='coerce')

            for index, row in merged_df.iterrows():
                tracking_number = row['Tracking']
                if tracking_number in df['Tracking'].values:
                    df.loc[df['Tracking'] == tracking_number, 'Status'] = row['Status']
                    df.loc[df['Tracking'] == tracking_number, 'In transit at'] = row['In transit at']
                    df.loc[df['Tracking'] == tracking_number, 'Final status at'] = row['Final status at']
                    df.loc[df['Tracking'] == tracking_number, 'Time to final status at'] = row['Time to final status at']
                    df.loc[df['Tracking'] == tracking_number, 'Time in transit at'] = row['Time in transit at']
                    df.loc[df['Tracking'] == tracking_number, 'Refund'] = row['Refund']

            df.to_excel(file_path, index=False)
            print("Tracking information has been saved to file")
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})

    return jsonify({"status": "success"})


@app.route('/download/<file_id>')
def download_results(file_id):
    output_file_name = file_id + '.xlsx'
    output_file_path = os.path.join(app.config['UPLOAD_FOLDER'], output_file_name)
    if os.path.exists(output_file_path):
        return send_file(output_file_path, as_attachment=True)
    return "File not found", 404

if __name__ == '__main__':
    app.run(debug=True)
