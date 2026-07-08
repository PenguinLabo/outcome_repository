from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

import os
import shutil
import time
import traceback
import requests
import pyodbc
import tempfile

from datetime import datetime as dt

URL = "https://宿のURL"

# DB接続設定
ODBC_DRIVER = '{SQL Server}'
DB_SERVER = 'kohei\\SQLSERVER'
DB_DATABASE = 'master'

# LINE Messaging API設定（トークンを直書きしないよう環境変数から読み込む）
LINE_ACCESS_TOKEN = os.environ['LINE_ACCESS_TOKEN']
LINE_USER_ID = os.environ['LINE_USER_ID']

LINE_PUSH_URL = 'https://api.line.me/v2/bot/message/push'


def connect_db():
    return pyodbc.connect(
        'DRIVER=' + ODBC_DRIVER
        + ';SERVER=' + DB_SERVER
        + ';DATABASE=' + DB_DATABASE
        + ';PORT=1433;Trusted_Connection=yes;'
    )


def get_available_dates(calendar_elements):
    """カレンダー要素の一覧から、空室（triangle）のある日付を date 型で返す"""
    available_dates = []

    for calendar in calendar_elements:
        stryearmonth = calendar.find_element(By.CLASS_NAME, 'header').text

        triangles = calendar.find_element(
            By.CLASS_NAME,
            'content'
        ).find_elements(By.CLASS_NAME, 'triangle')

        for triangle in triangles:
            strdate = (
                triangle
                .find_element(By.XPATH, "..")
                .find_element(By.CLASS_NAME, 'date')
                .text
            )

            available_dates.append(
                dt.strptime(
                    stryearmonth + strdate + '日',
                    '%Y年%m月%d日'
                ).date()
            )

    return available_dates


def to_date(value):
    """DBのsenddateカラムが文字列型でもDATE型でも date に揃える"""
    if isinstance(value, str):
        return dt.strptime(value, '%Y-%m-%d').date()
    return value


def get_sent_dates_from_sql():
    """通知済みの日付一覧をDBから取得する"""
    connect = connect_db()
    cursor = connect.cursor()

    cursor.execute('select senddate from YadoInfo')
    sent_dates = {to_date(row[0]) for row in cursor.fetchall()}

    cursor.close()
    connect.close()

    return sent_dates


def insert_sent_dates(dates):
    """通知した日付をDBに登録する"""
    connect = connect_db()
    cursor = connect.cursor()

    cursor.executemany(
        'insert into YadoInfo (senddate) values(?)',
        [(str(d),) for d in dates]
    )

    connect.commit()
    cursor.close()
    connect.close()


def delete_sent_dates(dates):
    """空室でなくなった日付をDBから削除する（再度空きが出たら改めて通知するため）"""
    if not dates:
        return

    connect = connect_db()
    cursor = connect.cursor()

    cursor.executemany(
        'delete from YadoInfo where senddate = ?',
        [(str(d),) for d in dates]
    )

    connect.commit()
    cursor.close()
    connect.close()


def send_line_message(message):
    headers = {
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }

    data = {
        'to': LINE_USER_ID,
        'messages': [
            {
                'type': 'text',
                'text': message
            }
        ]
    }

    return requests.post(
        LINE_PUSH_URL,
        headers=headers,
        json=data,
        timeout=10
    )


def open_with_retry(driver, url, tries=3, wait=60):
    """フェイルセーフ付きで遷移"""
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


def main():
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

    try:
        # 競争状態を避ける：まず about:blank へ
        driver.get("about:blank")

        open_with_retry(driver, URL)

        # ボタンはクリックで消えるUIのため、都度先頭を取り直してクリックする
        # （消えないUIに変わっても無限ループしないよう回数は初回の個数で打ち切る）
        for _ in range(len(driver.find_elements(By.CLASS_NAME, 'v-stack-btn'))):
            buttons = driver.find_elements(By.CLASS_NAME, 'v-stack-btn')

            if not buttons:
                break

            buttons[0].click()
            time.sleep(2)

        time.sleep(1)

        available_dates = get_available_dates(
            driver.find_elements(By.CLASS_NAME, 'c-calendar')
        )

        driver.find_element(
            By.CLASS_NAME,
            'calendar-set__pagination--next'
        ).click()

        time.sleep(1)

        # ページ送り後は2枚目のカレンダーだけが新しい月
        available_dates += get_available_dates(
            [driver.find_elements(By.CLASS_NAME, 'c-calendar')[1]]
        )

        sent_dates = get_sent_dates_from_sql()

        # 空室でなくなった日付は通知済み管理から外す
        delete_sent_dates(sent_dates - set(available_dates))

        # 通知済みの日付を除いた新規分だけ通知する
        new_dates = [d for d in available_dates if d not in sent_dates]

        if new_dates:
            message = '宿名'

            for i, d in enumerate(new_dates):
                if i == 0:
                    message += '\r\n\r\n' + f'{d:%Y年%m月%d日}'
                else:
                    message += '\r\n' + f'{d:%Y年%m月%d日}'

            message += '\r\nURL：https://yadoinfo.com'

            response = send_line_message(message)

            if response.status_code == 200:
                insert_sent_dates(new_dates)

                print('メッセージが送信されました', message)

            else:
                print(
                    f'エラーが発生しました: '
                    f'{response.status_code}, '
                    f'{response.text}'
                )

        print('正常終了')

    finally:
        driver.quit()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    try:
        main()

    except Exception:
        print('異常終了')
        traceback.print_exc()
