import asyncio
import base64
from flask import Flask, request, jsonify, session
from flask_session import Session
from pyppeteer import launch

app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['PERMANENT_SESSION_LIFETIME'] = 300  # 5 minutes
Session(app)

async def initiate_and_get_captcha(url):
    browser = await launch(
        headless=True,
        args=['--ignore-certificate-errors']  # Disable SSL verification
    )
    page = await browser.newPage()
    
    # Go to the page
    await page.goto(url)
    
    # Wait for captcha image to load
    await page.waitForSelector('#CaptchaImage')
    
    # Take a screenshot of the captcha image
    captcha_element = await page.querySelector('#CaptchaImage')
    captcha_screenshot = await captcha_element.screenshot()
    
    # Get the form action URL
    form_action = await page.evaluate('''() => {
        return document.querySelector('form').action;
    }''')

    # Encode the screenshot to base64
    screenshot_base64 = base64.b64encode(captcha_screenshot).decode('utf-8')
    
    # Store browser and page in session for later use
    session['browser'] = browser
    session['page'] = page
    session['form_action'] = form_action
    
    return screenshot_base64

async def fill_form_and_submit(captcha, birth_date, serial_number):
    page = session['page']
    
    # Type into the form fields
    await page.type('input[name="CaptchaInputText"]', captcha)
    await page.type('input[name="BirthDate"]', birth_date)
    await page.type('input[name="UBRN"]', serial_number)
    
    # Click the submit button
    await page.click('input[type="submit"]')
    
    # Wait for navigation after the form is submitted
    await page.waitForNavigation()
    
    # Get the resulting page content
    content = await page.content()
    
    # Close the browser after the operation
    await session['browser'].close()
    
    return content

@app.route('/initiate', methods=['POST'])
def initiate_session():
    url = 'https://everify.bdris.gov.bd'
    
    try:
        session.clear()
        screenshot_base64 = asyncio.get_event_loop().run_until_complete(initiate_and_get_captcha(url))
        
        return jsonify({
            'status': 'captcha_required',
            'captcha_image': f"data:image/png;base64,{screenshot_base64}",
            'session_id': session.sid
        })
    
    except Exception as e:
        return jsonify({'error': 'Request Error', 'details': str(e)}), 500

@app.route('/submit', methods=['POST'])
def submit_form():
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id or 'page' not in session:
        return jsonify({'error': 'Invalid session'}), 400
    
    captcha = data.get('captcha')
    birth_date = data.get('birth_date')
    serial_number = data.get('serial_number')
    
    try:
        # Use the stored session and page to fill the form and submit it
        page_content = asyncio.get_event_loop().run_until_complete(
            fill_form_and_submit(captcha, birth_date, serial_number)
        )
        
        return jsonify({
            'status': 'success',
            'content': page_content
        })
    
    except Exception as e:
        return jsonify({'error': 'Request Error', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
