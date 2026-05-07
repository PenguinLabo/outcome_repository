from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

import time
import requests
import pyodbc
import tempfile

from datetime import datetime as dt


def getCalendarList(next_page):
    if next_page:
        calender_list = driver.find_elements(By.CLASS_NAME, 'c-calendar')[1]

        stryearmonth = calender_list.find_element(
            By.CLASS_NAME,
            'header'
        ).text

        accommodations_available_num = len(
            calender_list.find_element(
                By.CLASS_NAME,
                'content'
            ).find_elements(By.CLASS_NAME, 'triangle')
        )

        time.sleep(1)

        if accommodations_available_num > 0:
            for num2 in range(accommodations_available_num):
                stryearmonthdate_list.append(
                    stryearmonth
                    + calender_list.find_element(
                        By.CLASS_NAME,
                        'content'
                    ).find_elements(By.CLASS_NAME, 'triangle')[num2]
                    .find_element(By.XPATH, "..")
                    .find_element(By.CLASS_NAME, 'date')
                    .text
                    + '日'
                )

    else:
        calender_list = driver.find_elements(By.CLASS_NAME, 'c-calendar')

        for num in range(len(calender_list)):
            stryearmonth = calender_list[num].find_element(
                By.CLASS_NAME,
                'header'
            ).text

            accommodations_available_num = len(
                calender_list[num].find_element(
                    By.CLASS_NAME,
                    'content'
                ).find_elements(By.CLASS_NAME, 'triangle')
            )

            time.sleep(1)

            if accommodations_available_num > 0:
                for num2 in range(accommodations_available_num):
                    stryearmonthdate_list.append(
                        stryearmonth
                        + calender_list[num].find_element(
                            By.CLASS_NAME,
                            'content'
                        ).find_elements(By.CLASS_NAME, 'triangle')[num2]
                        .find_element(By.XPATH, "..")
                        .find_element(By.CLASS_NAME, 'date')
                        .text
                        + '日'
                    )


def updatesql(list):
    driver = '{SQL Server}'
    server = 'kohei\\SQLSERVER'
    database = 'master'
    trusted_connection = 'yes'

    connect = pyodbc.connect(
        'DRIVER=' + driver
        + ';SERVER=' + server
        + ';DATABASE=' + database
        + ';PORT=1433;Trusted_Connection='
        + trusted_connection
        + ';'
    )

    cursor = connect.cursor()

    for n in range(len(list)):
        sql = 'insert into YadoInfo (senddate) values(?)'

        cursor.execute(
            sql,
            str(dt.strptime(list[n], '%Y年%m月%d日').date())
        )

    connect.commit()
    cursor.close()
    connect.close()


def deletesql():
    driver = '{SQL Server}'
    server = 'kohei\\SQLSERVER'
    database = 'master'
    trusted_connection = 'yes'

    connect = pyodbc.connect(
        'DRIVER=' + driver
        + ';SERVER=' + server
        + ';DATABASE=' + database
        + ';PORT=1433;Trusted_Connection='
        + trusted_connection
        + ';'
    )

    cursor = connect.cursor()

    sql = 'delete from YadoInfo'

    cursor.execute(sql)

    connect.commit()
    cursor.close()
    connect.close()


def getssenddatefromsql():
    driver = '{SQL Server}'
    server = 'kohei\\SQLSERVER'
    database = 'master'
    trusted_connection = 'yes'

    connect = pyodbc.connect(
        'DRIVER=' + driver
        + ';SERVER=' + server
        + ';DATABASE=' + database
        + ';PORT=1433;Trusted_Connection='
        + trusted_connection
        + ';'
    )

    cursor = connect.cursor()

    sql = "select senddate from YadoInfo"

    rc = cursor.execute(sql)

    fetch_ret = cursor.fetchall()

    send_list = fetch_ret

    return send_list


URL = "https://宿のURL"

opts = Options()

opts.add_argument("--no-first-run")
opts.add_argument("--no-default-browser-check")
opts.add_argument("--disable-extensions")

tmp = tempfile.mkdtemp(prefix="selenium-")

opts.add_argument(f"--user-data-dir={tmp}")

driver = webdriver.Chrome(
    service=Service(),
    options=opts
)

# 競争状態を避ける：まず about:blank へ
driver.get("about:blank")


# フェイルセーフ付きで遷移
def open_with_retry(url, tries=3, wait=60):
    for i in range(tries):
        driver.get(url)

        # DOM 完了まで待機
        WebDriverWait(driver, wait).until(
            lambda d: d.execute_script(
                "return document.readyState"
            ) == "complete"
        )

        cur = (driver.current_url or "")

        if not cur.startswith("data:"):
            return

    raise RuntimeError("data: から遷移できませんでした")


open_with_retry(URL)

try:
    if len(driver.find_elements(By.CLASS_NAME, 'v-stack-btn')) >= 1:
        for n in range(len(driver.find_elements(By.CLASS_NAME, 'v-stack-btn'))):
            driver.find_elements(By.CLASS_NAME, 'v-stack-btn')[0].click()
            time.sleep(2)

    time.sleep(1)

    stryearmonthdate_list = []

    getCalendarList(False)

    driver.find_element(
        By.CLASS_NAME,
        'calendar-set__pagination--next'
    ).click()

    time.sleep(1)

    getCalendarList(True)

    if len(stryearmonthdate_list) > 0:
        sendsql_list = getssenddatefromsql()

        for num3 in range(len(stryearmonthdate_list)):
            for num4 in range(len(sendsql_list)):
                if (
                        str(
                            dt.strptime(
                                stryearmonthdate_list[num3],
                                '%Y年%m月%d日'
                            ).date()
                        )
                        == str(sendsql_list[num4])
                        .replace(',', '')
                        .replace('(', '')
                        .replace(')', '')
                        .replace("'", '')
                ):
                    del stryearmonthdate_list[num3]

        if len(stryearmonthdate_list) > 0:
            message = '宿名'

            for num5 in range(len(stryearmonthdate_list)):
                if num5 == 0:
                    message += '\r\n\r\n' + str(stryearmonthdate_list[num5])
                else:
                    message += '\r\n' + str(stryearmonthdate_list[num5])

            message += '\r\nURL：https://yadoinfo.com'

            # チャネルアクセストークン（長期）
            access_token = 'ハードコーディングtoken'

            # ユーザーID
            user_id = 'ハードコーディングid'

            # ヘッダー設定
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            # メッセージ内容
            data = {
                'to': user_id,
                'messages': [
                    {
                        'type': 'text',
                        'text': message
                    }
                ]
            }

            # LINE Messaging APIエンドポイント
            url = 'https://api.line.me/v2/bot/message/push'

            # メッセージ送信
            response = requests.post(
                url,
                headers=headers,
                json=data
            )

            # ステータスを確認
            if response.status_code == 200:
                updatesql(stryearmonthdate_list)

                print('メッセージが送信されました', message)

            else:
                print(
                    f'エラーが発生しました: '
                    f'{response.status_code}, '
                    f'{response.text}'
                )

    else:
        if len(getssenddatefromsql()) > 0:
            deletesql()

    print('正常終了')

    driver.close()

except:
    print('異常終了')

    driver.close()
