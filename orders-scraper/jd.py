from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import logging

def setup_logger(log_file):
    # Create a logger
    logger = logging.getLogger('jingdong_logger')
    logger.setLevel(logging.DEBUG)

    # Create a file handler and set the level to INFO
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)

    # Create a formatter to define the log message format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger
    logger.addHandler(file_handler)

    return logger

def jd(start_date, end_date):
    # Initialize the logger
    current_date = datetime.now().strftime('%Y-%m-%d')
    logger = setup_logger(f'数据结果/jingdong_{current_date}.log')

    logger.info('Starting the program')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # set default timeout
        page.set_default_timeout(120000)
        # Main program
        try:
            # Step 0: Show Instructions
            # Inject a styled message box into the page
            message_js_code = """
            () => {
                const modal = document.createElement('div');
                modal.innerHTML = `
                    <div id="customAlert1" style="
                        position: fixed;
                        top: 40%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        padding: 20px;
                        background-color: white;
                        border: 2px solid black;
                        z-index: 10000;
                        display: none;
                        box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                    ">
                        <h2>开始自动化操作</h2>
                        <p>我们将自动为您打开京东的登录界面，请打开您手机上的京东软件，并使用软件内部的扫码功能来登录您的账号!（当然，您也可以选择微信扫码等其他方式登录）</p>
                        <p>登录完成后，程序会自动操作，请不要使用鼠标和键盘，直到出现完成消息提示！</p>
                        <p>如果您理解了这一步操作，请点击下方的确定按钮。</p>
                        <center>
                        <button onclick="document.getElementById('customAlert1').style.display='none'; document.body.setAttribute('alertClosed', 'true');" 
                        style="
                            padding: 10px 20px;
                            font-size: 15px;
                            cursor: pointer;
                            margin-top: 20px;
                        "
                        > 确定 </button>
                        </center>
                    </div>
                `;
                document.body.appendChild(modal);
            }
            """
            page.evaluate(message_js_code)
            page.evaluate("document.getElementById('customAlert1').style.display='block'")
            # Wait for the 'alertClosed' attribute to appear on the body element
            page.wait_for_selector("body[alertClosed='true']")


            # Step 1: Open the link and login

            # open link and wait until page loaded
            page.goto('https://order.jd.com/center/list.action')
            page.wait_for_load_state()
            logger.info('Login page already loaded')   
            page.wait_for_selector('[id="order02"]', state="visible")
            logger.info('Go to orders page')

            def update_next_link():
                link = "stop"
                next_button = page.query_selector('.next-disabled')
                # If 'next-disabled' doesn't exist, try to find the 'next' element
                if not next_button:
                    next_button = page.query_selector('.next')
                    link = "https:" + next_button.get_attribute('href')
                return link
            
            # Store once
            def store_html():
                element = page.locator('div[id="order02"]')
                html_content = element.inner_html()
                file.write(html_content)
            def check_first_page(end_date):
                try:
                    span_dealtime = page.query_selector('span.dealtime')
                    if span_dealtime is None:
                        return "stop"

                    last_item_text = span_dealtime.inner_text().split(" ")[0]
                    last_item_date = datetime.strptime(last_item_text, '%Y-%m-%d')

                    end_date_parsed = datetime.strptime(end_date, '%Y-%m-%d')

                    if last_item_date < end_date_parsed:
                        return "stop"
                    else:
                        return "continue"
                except Exception as e:
                    logger.info(f'Error in check_first_page: {str(e)}')
                    return "stop"              
             
            output_html = f"数据结果/jingdong_{current_date}.html"
            with open(output_html, "w", encoding="utf-8") as file:
                file.write(f"date range: {start_date} - {end_date}")

                # Store 1st page
                store_html()

                # Update stop logic
                link = update_next_link()
                first_page_stop = check_first_page(end_date)
                if first_page_stop == "stop":
                    link = "stop"

                while link != "stop":
                    page.goto(link)
                    page.wait_for_load_state()
                    store_html()
                    link = update_next_link()
                    first_page_stop = check_first_page(end_date)
                    if first_page_stop == "stop":
                        link = "stop"
        
            # Delete people profile privacy
            with open(output_html, "r", encoding="utf-8") as file:
                soup = BeautifulSoup(file, 'lxml')

            # Find and delete all <td> elements based on the selector
            try:
                for td in soup.select('tr.tr-bd > td:nth-of-type(2)'):
                    td.decompose()
                # Output the modified HTML
                modified_html = soup.prettify()
                # Optionally, write the modified HTML back to the file or another file
                with open(output_html, 'w', encoding='utf-8') as file:
                    file.write(modified_html)
            except Exception as e:
                with open(output_html, 'a', encoding='utf-8') as file:
                    file.write(str(e))
            # Show Finished messages
            # Inject a styled message box into the page
            message_js_code = """
            () => {
                const modal = document.createElement('div');
                modal.innerHTML = `
                    <div id="customAlert2" style="
                        position: fixed;
                        top: 40%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        padding: 20px;
                        background-color: white;
                        border: 2px solid black;
                        z-index: 10000;
                        display: none;
                        box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        font-size: 15px;
                    ">
                        <h2>结束程序</h2>
                        <br>
                        <p>数据收集完成，感谢您的使用！如果要收集其他平台的数据，请重新打开软件</p>
                        <center>
                        <button onclick="document.getElementById('customAlert2').style.display='none'; document.body.setAttribute('alertClosed', 'true');" 
                        style="
                            padding: 10px 20px;
                            font-size: 15px;
                            cursor: pointer;
                            margin-top: 20px;
                        "
                        > 关闭 </button>
                        </center>
                    </div>
                `;
                document.body.appendChild(modal);
            }
            """
            page.evaluate(message_js_code)
            page.evaluate("document.getElementById('customAlert2').style.display='block'")
            # Wait for the 'alertClosed' attribute to appear on the body element
            page.wait_for_selector("body[alertClosed='true']")
            logger.info('Showed finished message')
        except Exception as e:
            # Log exceptions or errors
            logger.error(f'Error occurred: {str(e)}')
            message_js_code = """
            () => {
                const modal = document.createElement('div');
                modal.innerHTML = `
                    <div id="customAlert3" style="
                        position: fixed;
                        top: 40%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        padding: 20px;
                        background-color: white;
                        border: 2px solid black;
                        z-index: 10000;
                        display: none;
                        box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                    ">
                        <h2>出现错误</h2>
                        <p>错误为：__ERR__</p>
                        <center>
                        <button onclick="document.getElementById('customAlert3').style.display='none'; document.body.setAttribute('alertClosed', 'true');" 
                        style="
                            padding: 10px 20px;
                            font-size: 15px;
                            cursor: pointer;
                            margin-top: 20px;
                        "
                        > 关闭 </button>
                        </center>
                    </div>
                `;
                document.body.appendChild(modal);
            }
            """.replace("__ERR__", str(e))
            page.evaluate(message_js_code)
            page.evaluate("document.getElementById('customAlert3').style.display='block'")
            # Wait for the 'alertClosed' attribute to appear on the body element
            page.wait_for_selector("body[alertClosed='true']")
        context.close()
        browser.close()
        logger.info('Closed the browser')
        logger.info('Completed successfully')
    
if __name__ == "__main__":
    jd("2023-01-01", "2023-07-31")
