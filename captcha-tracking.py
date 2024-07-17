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