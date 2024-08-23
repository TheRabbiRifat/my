import base64
import requests
from flask import Flask, request, jsonify, session
from flask_session import Session
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
from io import BytesIO
from PIL import Image

app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['PERMANENT_SESSION_LIFETIME'] = 300  # 5 minutes
Session(app)

# Global Selenium WebDriver, session management
driver = None

def initialize_driver():
    global driver
    if driver is None:
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Ensure GUI is off
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
    return driver

def take_screenshot_of_captcha(driver, captcha_element):
    location = captcha_element.location
    size = captcha_element.size
    png = driver.get_screenshot_as_png()

    im = Image.open(BytesIO(png))

    left = location['x']
    top = location['y']
    right = location['x'] + size['width']
    bottom = location['y'] + size['height']

    im = im.crop((left, top, right, bottom))  # defines crop points
    buffered = BytesIO()
    im.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return img_str

@app.route('/initiate', methods=['POST'])
def initiate_session():
    url = 'https://everify.bdris.gov.bd'
    
    try:
        session.clear()
        session['requests_session'] = requests.Session()
        session['requests_session'].headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'
        })
        
        # Initialize and navigate with Selenium
        driver = initialize_driver()
        driver.get(url)
        
        time.sleep(2)  # Wait for page to fully load
        
        captcha_element = driver.find_element(By.ID, 'CaptchaImage')
        captcha_base64 = take_screenshot_of_captcha(driver, captcha_element)
        
        return jsonify({
            'status': 'captcha_required',
            'captcha_image': f"data:image/png;base64,{captcha_base64}",
            'session_id': session.sid
        })
    
    except Exception as e:
        return jsonify({'error': 'An error occurred', 'details': str(e)}), 500

@app.route('/submit', methods=['POST'])
def submit_form():
    global driver
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
        # Interact with the form in the active session
        driver.find_element(By.NAME, 'UBRN').send_keys(form_data['UBRN'])
        driver.find_element(By.NAME, 'BirthDate').send_keys(form_data['BirthDate'])
        driver.find_element(By.NAME, 'CaptchaInputText').send_keys(form_data['CaptchaInputText'])
        driver.find_element(By.CSS_SELECTOR, 'input.btn.btn-primary[type=submit]').click()
        
        time.sleep(2)  # Wait for form to process
        
        main_content = driver.find_element(By.ID, 'mainContent')
        content_html = main_content.get_attribute('outerHTML')
        
        return jsonify({
            'status': 'success',
            'content': content_html
        })
    
    except Exception as e:
        return jsonify({'error': 'An error occurred', 'details': str(e)}), 500
    
    finally:
        # Close the Selenium session after completing the second response
        if driver:
            driver.quit()
            driver = None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
