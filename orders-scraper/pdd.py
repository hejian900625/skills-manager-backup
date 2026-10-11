from playwright.sync_api import sync_playwright
import time
from datetime import datetime
import logging
import threading


stop_event = threading.Event()

def setup_logger(log_file):
    # Create a logger
    logger = logging.getLogger('pdd_logger')
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

def date_string_to_int(date_str):
    # Assuming date_str has the format "YYYY-MM-DD"
    components = date_str.split("-")
    year = int(components[0][2:])
    month = int(components[1])
    day = int(components[2])
    return year * 10000 + month * 100 + day

def pdd(start_date, end_date):
    # Initialize the logger
    current_date = datetime.now().strftime('%Y-%m-%d')
    logger = setup_logger(f'数据结果/pdd_{current_date}.log')

    output_json = f"数据结果/pdd_{current_date}.txt"
    logger.info(f'chosen date range: {start_date} - {end_date}')

    def store_json(t):
        with open(output_json, "a", encoding="utf-8") as file:
            file.write("---\n")
            file.write(f'{str(t)}\n')

    # Init the txt file
    # this code ensure start with an empty file
    with open(output_json, "w", encoding="utf-8") as file:
        pass
    
    logger.info('Starting the program')
    store_json(f'date_range: {start_date} - {end_date}')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # set default timeout
        page.set_default_timeout(120000)

        # Main program
        try:
            # make start_date and end_date be int
            # From "2023-01-01"
            # To integer 230101
            # The int format follows pdd order pattern
            date_range = [date_string_to_int(start_date), date_string_to_int(end_date)]

            # Attach an event listener to the response event
            def handle_response(response):
                url = response.url
                # Check if the URL contains the specific pattern
                if "order_list_v" in url:
                    print(url)
                    # Fetch the JSON data from the response
                    json_data = response.json()
                    num = len(json_data["orders"])
                    if num == 0:
                        stop_event.set()
                        print("stop listening since no more orders") 
                    else:
                        # have multiple orders
                        order_list = json_data["orders"]
                        new_order = int(order_list[0]['order_sn'].split("-")[0])
                        old_order = int(order_list[-1]['order_sn'].split("-")[0])
                        print(f"==>> new_order: {new_order}")
                        print(f"==>> old_order: {old_order}")
                        if date_range[0] > new_order:
                            # date range not matched
                            stop_event.set()
                            print("stop listening since date range not matched")
                        else:
                            store_json(f'api_json')
                            store_json(json_data)

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
                        <p>我们将自动为您打开拼多多网页，由于拼多多不提供扫码登录，因此请通过您的账号绑定的手机进行验证码登录!<b>（如果您还没有绑定过您的手机号，请先绑定）</b></p>
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
            logger.info('Showed message popup')


            # Step 1: Open the link and login
            # open link and wait until page loaded
            page.goto('https://mobile.yangkeduo.com/orders.html')
            page.wait_for_load_state()
            logger.info('Login page already loaded')
            
            page.wait_for_selector('._13OAwPyA', state="visible")
            logger.info('Go to orders page')

            def parse_order(orders):
                detail_list = []
                # Using .get() to avoid KeyError if 'ordersStore' or 'orders' is missing
                for order in orders.get('ordersStore', {}).get('orders', []):
                    detail = {}
                    # Using .get() for all dictionary lookups to provide default values if keys are missing
                    detail['order_sn'] = order.get('orderSn', None)
                    detail['order_amount'] = order.get('orderAmount', None)
                    detail['order_status_prompt'] = order.get('orderStatusPrompt', None)
                    # Checking the length of 'orderGoods' list before accessing its elements
                    if order.get('orderGoods') and len(order['orderGoods']) > 0:
                        detail['goods_name'] = order['orderGoods'][0].get('goodsName', None)
                        detail['goods_price'] = order['orderGoods'][0].get('goodsPrice', None)
                        detail['goods_number'] = order['orderGoods'][0].get('goodsNumber', None)
                    else:
                        detail['goods_name'] = None
                        detail['goods_price'] = None
                        detail['goods_number'] = None
                    detail_list.append(detail)
                return detail_list

            # Get first 10 orders
            # Store it in json
            order_10 = page.evaluate("window.rawData")
            orders = parse_order(order_10)
            print(f"==>> orders: {orders}")
            store_json("top ten json")
            store_json(orders)

        
            # Scroll down once to the bottom
            def down():
                page_height = page.viewport_size["height"]
                page.mouse.wheel(0, page_height)
                time.sleep(1)
    

            page.on("response", handle_response)
            print("start listening")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector('._13OAwPyA', state="visible")

            while not stop_event.is_set():
                down()
                time.sleep(0.5) # gap between scroll down
            
            # Auto Scroll down to Bottom
            # page.evaluate(
            #     """
            #     var intervalID = setInterval(function () {
            #         var scrollingElement = (document.scrollingElement || document.body);
            #         scrollingElement.scrollTop = scrollingElement.scrollHeight;
            #     }, 200);

            #     """
            # )
            # prev_height = None
            # while True:
            #     curr_height = page.evaluate('(window.innerHeight + window.scrollY)')
            #     if not prev_height:
            #         prev_height = curr_height
            #         time.sleep(10)
            #     elif prev_height == curr_height:
            #         page.evaluate('clearInterval(intervalID)')
            #         break
            #     else:
            #         prev_height = curr_height
            #         time.sleep(10)
            
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
    pdd("2023-01-01", "2023-07-31")