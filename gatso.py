#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import socket
import threading
from datetime import datetime

import gspread
import speedtest_cli as st
from oauth2client.client import SignedJwtAssertionCredentials

SHEET_KEY = '1Y7tAynFs-Mp7GnLaoUXs_tz33WdFQS8m-SbmMr1JlLU'
SOCKET_TIMEOUT = 10  # seconds


def run_speedtest():
    st.shutdown_event = threading.Event()
    socket.setdefaulttimeout(SOCKET_TIMEOUT)
    st.build_user_agent()
    config = st.getConfig()
    servers = st.closestServers(config['client'])
    best = st.getBestServer(servers)
    # print(best)

    urls = []
    for size in [350, 500, 750, 1000, 1500, 2000, 2500, 3000, 3500, 4000]:
        for i in range(0, 4):
            urls.append('%s/random%sx%s.jpg' % (os.path.dirname(best['url']), size, size))
    dlspeed = st.downloadSpeed(urls, True) * 8 / 1024 / 1024
    # print(dlspeed)

    sizes = []
    for size in [int(.25 * 1024 * 1024), int(.5 * 1024 * 1024)]:
        for i in range(0, 25):
            sizes.append(size)
    ulspeed = st.uploadSpeed(best['url'], sizes, True) * 8 / 1024 / 1024
    # print(ulspeed)

    return best, dlspeed, ulspeed


server_details, dl_speed, ul_speed = run_speedtest()

json_key = json.load(open('credentials.json', 'r'))
scope = ['https://spreadsheets.google.com/feeds']
gc = gspread.authorize(SignedJwtAssertionCredentials(
    json_key['client_email'], json_key['private_key'].encode(), scope))

worksheet = gc.open_by_key(SHEET_KEY).get_worksheet(0)
worksheet.insert_row(
    [
        datetime.utcnow(),
        server_details['latency'],
        dl_speed,
        ul_speed,
        server_details['host'],
        server_details['sponsor'],
        server_details['name'],
        server_details['cc'],
        server_details['d'],
        server_details['id'],
        server_details['url']
    ], 2)
