import base64
import requests
from flask import Flask, request, jsonify, session
from flask_session import Session
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image

app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['PERMANENT_SESSION_LIFETIME'] = 300  # 5 minutes
Session(app)

@app.route('/initiate', methods=['POST'])
def initiate_session():
    url = 'https://everify.bdris.gov.bd'
    
    try:
        session.clear()
        session['requests_session'] = requests.Session()
        session['requests_session'].headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'
        })
        
        response = session['requests_session'].get(url, verify=False, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        captcha_img_tag = soup.find('img', {'id': 'CaptchaImage'})
        captcha_img_src = captcha_img_tag['src']
        
        # If captcha source is a base64 data URL
        if captcha_img_src.startswith('data:'):
            content_type, encoded_image = captcha_img_src.split(',', 1)
            return jsonify({
                'status': 'captcha_required',
                'captcha_image': captcha_img_src,
                'session_id': session.sid
            })
        else:
            # If the captcha is not a base64 data URL, handle this case
            return jsonify({'error': 'Captcha image source is not a data URL'}), 400

    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Request Error', 'details': str(e)}), 500

@app.route('/submit', methods=['POST'])
def submit_form():
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id or 'requests_session' not in session:
        return jsonify({'error': 'Invalid session'}), 400
    
    form_data = {
        'CaptchaInputText': data.get('captcha'),
        'BirthDate': data.get('birth_date'),
        'UBRN': data.get('serial_number')
    }
    
    try:
        previous_page_url = 'https://everify.bdris.gov.bd'
        response = session['requests_session'].get(previous_page_url, verify=False, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form')
        submit_url = previous_page_url + form['action']

        form_data['btn'] = 'Search'
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': previous_page_url,
        }
        
        response = session['requests_session'].post(submit_url, data=form_data, headers=headers, verify=False, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        main_div = soup.find('div', {'id': 'mainContent'})  # Replace 'mainContent' with actual div ID
        
        return jsonify({
            'status': 'success',
            'content': str(main_div)
        })
    
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Request Error', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
