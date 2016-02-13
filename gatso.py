#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import random
import socket
import threading
from datetime import datetime
from urllib.error import URLError

import gspread
import speedtest_cli as st
from oauth2client.client import SignedJwtAssertionCredentials
from requests import HTTPError

SHEET_KEY = '1Y7tAynFs-Mp7GnLaoUXs_tz33WdFQS8m-SbmMr1JlLU'
SOCKET_TIMEOUT = 10  # seconds


def getConfig() -> dict:
    """Download the speedtest.net configuration and return only the data
    we are interested in
    """

    request = st.build_request('://www.speedtest.net/speedtest-config.php')
    uh, e = st.catch_request(request)
    if e:
        print('Could not retrieve speedtest.net configuration: %s' % e)
        return None
    configxml = []
    while 1:
        configxml.append(uh.read(10240))
        if len(configxml[-1]) == 0:
            break
    if int(uh.code) != 200:
        return None
    uh.close()
    try:
        try:
            root = st.ET.fromstring(''.encode().join(configxml))
            return {
                'client': root.find('client').attrib,
                'times': root.find('times').attrib,
                'download': root.find('download').attrib,
                'upload': root.find('upload').attrib}
        except AttributeError:  # Python3 branch
            root = st.DOM.parseString(''.join(configxml))
            return {
                'client': st.getAttributesByTagName(root, 'client'),
                'times': st.getAttributesByTagName(root, 'times'),
                'download': st.getAttributesByTagName(root, 'download'),
                'upload': st.getAttributesByTagName(root, 'upload')}
    except SyntaxError:
        print('Failed to parse speedtest.net configuration')
        return None


def getBestServer(servers, user_agent):
    """Improves speedtest_cli.getBestServer to pick a random server from the 5 fastest ones instead."""

    results = {}
    for server in servers:
        cum = []
        url = '%s/latency.txt' % os.path.dirname(server['url'])
        urlparts = st.urlparse(url)
        for i in range(0, 3):
            try:
                if urlparts[0] == 'https':
                    h = st.HTTPSConnection(urlparts[1])
                else:
                    h = st.HTTPConnection(urlparts[1])
                headers = {'User-Agent': user_agent}
                start = st.timeit.default_timer()
                h.request("GET", urlparts[2], headers=headers)
                r = h.getresponse()
                total = (st.timeit.default_timer() - start)
            except (HTTPError, URLError, socket.error):
                cum.append(3600)
                continue
            text = r.read(9)
            if int(r.status) == 200 and text == 'test=test'.encode():
                cum.append(total)
            else:
                cum.append(3600)
            h.close()
        avg = round((sum(cum) / 6) * 1000, 3)
        results[avg] = server
    key = random.choice(sorted(results.keys())[:5])
    best = results[key]
    best['latency'] = key
    return best


def run_speedtest() -> (dict, float, float):
    st.shutdown_event = threading.Event()
    socket.setdefaulttimeout(SOCKET_TIMEOUT)
    st.build_user_agent()
    config = getConfig()
    if not config:
        return {}, -1, -1
    servers = st.closestServers(config['client'])
    best = getBestServer(servers, st.build_user_agent())
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


def post_results(server_details, dl_speed, ul_speed):
    json_key = json.load(open('credentials.json', 'r'))
    scope = ['https://spreadsheets.google.com/feeds']
    gc = gspread.authorize(SignedJwtAssertionCredentials(
        json_key['client_email'], json_key['private_key'].encode(), scope))
    worksheet = gc.open_by_key(SHEET_KEY).get_worksheet(0)
    worksheet.insert_row(
        [
            datetime.utcnow(),
            server_details.get('latency', -1),
            dl_speed,
            ul_speed,
            server_details.get('host', ''),
            server_details.get('sponsor', ''),
            server_details.get('name', ''),
            server_details.get('cc', ''),
            server_details.get('d', -1),
            server_details.get('id', -1),
            server_details.get('url', ''),
        ], 2)


def run():
    server_details, dl_speed, ul_speed = run_speedtest()
    try:
        post_results(server_details, dl_speed, ul_speed)
    except socket.gaierror:
        print('Network seems down, unable to post results')
        pass


if __name__ == 'main':
    run()
