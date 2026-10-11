from playwright.sync_api import sync_playwright
import time
import sys
from datetime import datetime
import logging

def setup_logger(log_file):
    # Create a logger
    logger = logging.getLogger('taobao_logger')
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

def taobao(start_date, end_date):

    # Initialize the logger
    current_date = datetime.now().strftime('%Y-%m-%d')
    logger = setup_logger(f'数据结果/taobao_{current_date}.log')

    logger.info('Starting the program')
    # Main program
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        logger.info('Create the page')

        # set default timeout
        page.set_default_timeout(120000)
        logger.info('Set default timeout')

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
                        <p>我们将自动为您打开淘宝的登录界面，请打开您手机上的淘宝软件，并使用软件内部的扫码功能来登录您的账号!(当然，您也可以通过账号密码/手机验证码/支付宝扫码等其他方式登录)</p>
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
            logger.info('Show instructions')

            # Step 1: Open the link and login
            # open link and wait until page loaded
            page.goto('https://buyertrade.taobao.com/trade/itemlist/list_bought_items.htm')
            # page.wait_for_selector("i.icon-qrcode", state="visible")
            # page.locator("i.icon-qrcode").click()
            logger.info('Login page already loaded')

            # Step 2: Wait for login
            # 等待订单容器出现（登录成功才会渲染）。最多等 5 分钟，便于扫码/验证码。
            waited = 0
            while waited < 300:
                if page.query_selector('#bought'):
                    break
                # 若页面出现登录/扫码相关元素，提示用户继续完成登录
                time.sleep(3)
                waited += 3
            else:
                # 诊断：把关键信息打出来，区分“没登录”还是“改版”
                diag = {
                    'url': page.url,
                    'title': page.title(),
                    'has_login_kw': page.evaluate(
                        "() => document.body ? document.body.innerText.slice(0,500) : ''"
                    ),
                }
                logger.error(f'#bought not found. url={diag["url"]}')
                logger.error(f'page text head: {diag["has_login_kw"]!r}')
                print('==>> DIAG url:', diag['url'])
                print('==>> DIAG title:', diag['title'])
                print('==>> DIAG body head:', diag['has_login_kw'][:300])
                raise RuntimeError(
                    '未能进入淘宝订单页（未检测到 #bought）。请确认已扫码登录成功；'
                    '若已登录仍失败，说明淘宝页面改版，需要更新选择器。'
                )
            page.wait_for_load_state("domcontentloaded")
            logger.info('Bought items page already loaded')
            
            # Find more-functions button and click

            # Click on the input element to open the calendar
            page.wait_for_selector("button.search-mod__more-button___nbIba", state="visible")
            page.locator('button.search-mod__more-button___nbIba').click()
            page.wait_for_selector('[data-reactid=".0.2.1.0.1.1"]', state="visible")
            # Click start date
            page.locator('[data-reactid=".0.2.1.0.1.1"]').click()
            page.wait_for_selector('a.rc-calendar-month-select', state="visible")
            # Click start date in calendar
            page.locator('a.rc-calendar-month-select').click() # months
            page.wait_for_selector('div.rc-calendar-month-panel', state="visible")
            logger.info('Chose the calendar')

            # Now, let's say you want to select the date '2023-08-10'.
            # You can construct the selector dynamically based on the desired date.
            date_to_select = start_date
            year, month, day = date_to_select.split('-')
            month_dict = {
                1: "一月",
                2: "二月",
                3: "三月",
                4: "四月",
                5: "五月",
                6: "六月",
                7: "七月",
                8: "八月",
                9: "九月",
                10: "十月",
                11: "十一月",
                12: "十二月"
            }
            month_selector = f'[title="{month_dict[int(month)]}"]'
            page.locator(month_selector).click()
            page.wait_for_selector('div.rc-calendar-calendar-body', state="visible")
            logger.info('Chose the month')

            # Select the date
            date_selector = f'td[title="{int(year)}-{int(month)}-{int(day)}"]'
            page.locator(date_selector).click()
            page.wait_for_selector('a.rc-calendar-ok-btn', state="visible")
            page.locator('a.rc-calendar-ok-btn').click()
            logger.info(f'Chose the start date: {start_date}')

            time.sleep(2)

            date_to_select_end = end_date
            year, month, day = date_to_select_end.split('-')            

            page.wait_for_selector('[data-reactid=".0.2.1.0.1.3"]', state="visible")
            # Click start date
            page.locator('[data-reactid=".0.2.1.0.1.3"]').click()
            page.wait_for_selector('a.rc-calendar-month-select', state="visible")
            # Click start date in calendar
            page.locator('a.rc-calendar-month-select').click() # months
            page.wait_for_selector('div.rc-calendar-month-panel', state="visible")

            month_selector = f'[title="{month_dict[int(month)]}"]'
            page.locator(month_selector).click()
            page.wait_for_selector('div.rc-calendar-calendar-body', state="visible")

            # Select the date
            date_selector = f'td[title="{int(year)}-{int(month)}-{int(day)}"]'
            page.locator(date_selector).click()
            page.wait_for_selector('a.rc-calendar-ok-btn', state="visible")
            page.locator('a.rc-calendar-ok-btn').click()
            logger.info(f'Chose the end date: {end_date}')

            # Click search
            time.sleep(2)
            search_button_selector = 'button.button-mod__primary___1tmFA'
            print(f"==>> search_button_selector: {search_button_selector}")
            page.wait_for_selector(search_button_selector, state="visible")
            print(f"==>> search_button_selector find: {search_button_selector}")
            page.locator(search_button_selector).click()
            print(f"==>> search_button_selector click: {search_button_selector}")

            time.sleep(3)

            results = page.query_selector_all('.pagination-item')
            results_num = len(results)
            print(f"==>> results_num: {results_num}")

            def watch_for_change(id, page, xpath, timeout=30):
                # assume now we are in page-id
                current_value = page.eval_on_selector(f'xpath={xpath}', 'element => element.textContent')
                print(f"==>> current_value: {current_value}")
                # click to next page
                page.locator(f'li.pagination-item-{id+1}').click()
                time.sleep(5)

                start_time = time.time()
                while time.time() - start_time < timeout:
                    new_value = page.eval_on_selector(f'xpath={xpath}', 'element => element.textContent')
                    print(f"==>> new_value: {new_value}")
                    if new_value != current_value:
                        print(f"Page navigated to {id+1}")
                        time.sleep(2)
                        break
                    time.sleep(1)  # wait for 0.5 seconds before checking again

                return None
            
            output_html = f"数据结果/taobao_{current_date}.html"

            def store_html():
                element = page.locator('div[id="tp-bought-root"]')
                html_content = element.inner_html()
                file.write(html_content)            
            with open(output_html, "w", encoding="utf-8") as file:
                file.write(f"date range: {start_date} - {end_date}\n")  
                if results_num == 1:
                    print("only one page detected")
                    logger.info(f'only one page detected')
                    store_html()
                    logger.info(f'Finished writing page 1')
                else:
                    for i in range(1, results_num):
                        file.write(f"Page {i}\n")
                        logger.info(f'Start writing page {i}')
                        store_html()
                        logger.info(f'Finished writing page {i}')
                        watch_for_change(i, page, "//div/table/tbody/tr/td/span/span[3]")
                        logger.info(f'Finished page navigation {i}')
                    logger.info(f'Start writing page {results_num}')
                    file.write(f"Page {results_num}\n")
                    store_html()
                    logger.info(f'Finished writing page {results_num}')

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
            logger.info(f'Show finished messages')
        except Exception as e:
            # Log exceptions or errors
            logger.error(f'Error occurred: {str(e)}')
            # Show Finished messages
            # Inject a styled message box into the page
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
            logger.info(f'Show error messages')
        # Shutdown
        context.close()
        browser.close()
        logger.info('Completed successfully')

if __name__ == "__main__":
    taobao("2023-01-01", "2023-07-31")