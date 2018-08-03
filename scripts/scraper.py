#!/usr/bin/python
# -*- coding: utf-8 -*-
import datetime
import lxml.etree
import os
import requests

import glob
import utils


def get_individual_atlantsolia_prices():
    relation = glob.ATLANTSOLIA_LOCATION_RELATION
    url = 'https://www.atlantsolia.is/stodvaverd/'
    res = requests.get(url, headers=utils.headers())
    html_text = res.content
    html = lxml.etree.fromstring(html_text, lxml.etree.HTMLParser())
    div_prices = html.find(('.//*[@id="content"]/div/div/div/div[2]/div/div/'
                            'table/tbody'))
    # Atlantsolia recently declared one of its stations to be without discount,
    # on their site that station is marked with a star (*) and the following
    # comment at the bottom:
    # "* Engir afslaettir gilda"
    discountless_stations = ('ao_008', )
    prices = {}
    for div_price in div_prices:
        key = relation[div_price[0][0].text]
        bensin95 = float(div_price[1][0].text.replace(',', '.'))
        diesel = float(div_price[2][0].text.replace(',', '.'))
        bensin95_discount = int(
            (bensin95 - glob.ATLANTSOLIA_MINIMUM_DISCOUNT) * 10
        ) / 10.0
        diesel_discount = int(
            (diesel - glob.ATLANTSOLIA_MINIMUM_DISCOUNT) * 10
        ) / 10.0
        if key in discountless_stations:
            bensin95_discount = None
            diesel_discount = None
        prices[key] = {
            'bensin95': bensin95,
            'diesel': diesel,
            'bensin95_discount': bensin95_discount,
            'diesel_discount': diesel_discount
        }
    return prices


def get_global_costco_prices():
    # Costco does not intend to show petrol price on their webpage according to
    # email reply I've received from them, so we have no choice but to hardcode
    # their prices if we wish to include their prices in Gasvaktin.
    # Instead of hardcoding prices in the repo itself like with Dælan last
    # summer I've created a personal Google Docs Spreadsheet to hold their
    # current petrol prices, Simplifies updating prices if away from
    # workstation.
    headers = {
        'Accept': (
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,'
            '*/*;q=0.8'
        ),
        'Accept-Encoding': 'gzip, deflate, sdch, br',
        'Accept-Language': 'en-US,en;q=0.8,is;q=0.6,da;q=0.4',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'User-Agent': utils.random_ua()
    }
    url = (
        'https://docs.google.com/spreadsheets/d/'
        '18xuZbhfInW_6Loua3_4LE7KxbGPsh-_3IFfLpf3uwYE/edit'
    )
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    # <shameless-incredibly-naive-html-parsing>
    bensin = None
    diesel = None
    html_text = res.content
    for line in html_text.split('\n'):
        if line.startswith(' Bensin,'):
            bensin = float(line[8:].replace(' ', ''))
        if line.startswith(' Diesel,'):
            diesel = float(line[8:].replace(' ', ''))
        if bensin is not None and diesel is not None:
            break
    if bensin is None or diesel is None:
        err_msg = 'Failed to read costco prices (%s, %s)\n%s ...' % (
            bensin,
            diesel,
            html_text[:10000]
        )
        raise Exception(err_msg)
    # </shameless-incredibly-naive-html-parsing>
    return {
        'bensin95': bensin,
        'diesel': diesel,
        # Costco has no discount program
        'bensin95_discount': None,
        'diesel_discount': None
    }


def get_global_n1_prices():
    url_eldsneyti = 'https://www.n1.is/thjonusta/eldsneyti'
    url_eldsneyti_api = 'https://www.n1.is/umbraco/api/fuel/GetSingleFuelPrice'
    headers = utils.headers()
    session = requests.Session()
    session.get(url_eldsneyti, headers=headers)
    post_data_bensin = 'fuelType=95+Oktan'
    post_data_diesel = 'fuelType=D%C3%ADsel'
    headers_eldsneyti_api = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.8,is;q=0.6',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Host': 'www.n1.is',
        'Origin': 'https://www.n1.is',
        'Referer': 'https://www.n1.is/eldsneyti/',
        'User-Agent': headers['User-Agent'],
        'X-Requested-With': 'XMLHttpRequest'
    }
    headers_eldsneyti_api['Content-Length'] = str(len(post_data_bensin))
    res = session.post(url_eldsneyti_api, data=post_data_bensin,
                       headers=headers_eldsneyti_api)
    bensin95_discount_text = res.content
    headers_eldsneyti_api['Content-Length'] = str(len(post_data_diesel))
    res = session.post(url_eldsneyti_api, data=post_data_diesel,
                       headers=headers_eldsneyti_api)
    diesel_discount_text = res.content
    prices = {}
    prices['bensin95'] = float(
        bensin95_discount_text.replace('"', '').replace(',', '.'))
    prices['diesel'] = float(
        diesel_discount_text.replace('"', '').replace(',', '.'))
    prices['bensin95_discount'] = prices['bensin95'] - glob.N1_DISCOUNT
    prices['diesel_discount'] = prices['diesel'] - glob.N1_DISCOUNT
    return prices


def get_individual_daelan_prices():
    relation = glob.DAELAN_LOCATION_RELATION
    headers = utils.headers()
    session = requests.Session()
    session.get('http://daelan.is/', headers=headers)
    session.get('https://www.n1.is/', headers=headers)
    price_endpoint = 'https://www.n1.is/umbraco/api/Fuel/GetFuelPriceForDaelan'
    res = session.get(price_endpoint, headers=headers)
    res.raise_for_status()
    stations = res.json()
    prices = {}
    for station in stations:
        assert('location' in station)
        assert('gasPrice' in station)
        assert('diselPrice' in station)
        key = relation[station['location']]
        prices[key] = {
            'bensin95': float(station['gasPrice'].replace(',', '.')),
            'diesel': float(station['diselPrice'].replace(',', '.')),
            # Dælan has no discount program
            'bensin95_discount': None,
            'diesel_discount': None
        }
    return prices


def get_global_olis_prices():
    url = 'http://www.olis.is/solustadir/thjonustustodvar/eldsneytisverd/'
    res = requests.get(url, headers=utils.headers())
    html = lxml.etree.fromstring(res.content, lxml.etree.HTMLParser())
    bensin95_text = html.find('.//*[@id="gas-price"]/span[1]').text
    diesel_text = html.find('.//*[@id="gas-price"]/span[2]').text
    bensin_discount_text = html.find('.//*[@id="gas-price"]/span[4]').text
    diesel_discount_text = html.find('.//*[@id="gas-price"]/span[5]').text
    return {
        'bensin95': float(bensin95_text.replace(',', '.')),
        'diesel': float(diesel_text.replace(',', '.')),
        'bensin95_discount': float(bensin_discount_text.replace(',', '.')),
        'diesel_discount': float(diesel_discount_text.replace(',', '.'))
    }


def get_individual_ob_prices():
    url = 'http://www.ob.is/eldsneytisverd/'
    res = requests.get(url, headers=utils.headers())
    html = lxml.etree.fromstring(res.content, lxml.etree.HTMLParser())
    bensin95_text = html.find('.//*[@id="gas-price"]/span[1]').text
    diesel_text = html.find('.//*[@id="gas-price"]/span[2]').text
    bensin_discount_text = html.find('.//*[@id="gas-price"]/span[3]').text
    diesel_discount_text = html.find('.//*[@id="gas-price"]/span[4]').text
    bensin95 = float(bensin95_text.replace(',', '.'))
    diesel = float(diesel_text.replace(',', '.'))
    bensin95_discount = float(bensin_discount_text.replace(',', '.'))
    diesel_discount = float(diesel_discount_text.replace(',', '.'))
    prices = {}
    ob_stations = utils.load_json(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            '../stations/ob.json'
        )
    )
    # 15 ISK discount for selected stations in August
    #
    # Occasionally, selected OB stations have had higher discount than usually
    # for a specified month, it seems they're going to do this every month from
    # now on (according to fb post in July).
    # facebook.com/ob.bensin/photos/a.735324549839400.1073741825.162016470503547/1854520757919768/
    #
    # Stations with additional discount in July 2018:
    # * Hlidarbraut, Akureyri (ob_001)
    # * Selfoss (ob_027)
    # * Snorrabraut (ob_028)
    # * Vestmannaeyjar (ob_032)
    # * Fjardarkaup (ob_012)
    additional_discount = 15
    additional_discount_stations = (
        'ob_001', 'ob_027', 'ob_028', 'ob_032', 'ob_012',
    )
    now = datetime.datetime.now()
    end = datetime.datetime.strptime('2018-08-31T23:59', '%Y-%m-%dT%H:%M')
    for key in ob_stations:
        bensin95_discount = bensin95_discount
        diesel_discount = diesel_discount
        if now < end and key in additional_discount_stations:
            bensin95_discount = bensin95 - additional_discount
            diesel_discount = diesel - additional_discount
        prices[key] = {
            'bensin95': bensin95,
            'diesel': diesel,
            'bensin95_discount': bensin95_discount,
            'diesel_discount': diesel_discount
        }
    return prices


def get_individual_orkan_prices():
    # Read prices for Orkan and Orkan X stations because they're both on the
    # same webpage.
    url = 'https://www.orkan.is/orkan/orkustodvar/'
    res = requests.get(url, headers=utils.headers())
    html = lxml.etree.fromstring(res.content, lxml.etree.HTMLParser())
    div_element = html.find('.//div[@class="accordion__container"]')
    territories = div_element.findall('.//div[@class="accordion__child"]')
    prices = {}
    key = None
    for territory in territories:
        for station in territory:
            station_name = station[0][0].text
            bensin95 = float(station[1].text.replace(',', '.'))
            diesel = float(station[2].text.replace(',', '.'))
            if station_name in glob.ORKAN_LOCATION_RELATION:
                key = glob.ORKAN_LOCATION_RELATION[station_name]
            elif station_name in glob.ORKAN_X_LOCATION_RELATION:
                key = glob.ORKAN_X_LOCATION_RELATION[station_name]
            else:
                continue
            # Orkan X stations have key starting with "ox", while ordinary
            # Orkan statins have keys starting with "or"
            bensin95_discount = None
            diesel_discount = None
            if key.startswith('or'):
                # Orkan has a 3-step discount system controlled by your
                # spendings on gas from them the month before
                # See more info here: https://www.orkan.is/Afslattarthrep
                # For consistency we just use the minimum default discount
                bensin95_discount = bensin95 - glob.ORKAN_MINIMUM_DISCOUNT
                diesel_discount = diesel - glob.ORKAN_MINIMUM_DISCOUNT
            prices[key] = {
                'bensin95': bensin95,
                'diesel': diesel,
                'bensin95_discount': bensin95_discount,
                'diesel_discount': diesel_discount
            }
    # TEMPORARY_FIX while three former Skeljungur stations are missing from the
    # list of stations on Orkan webpage
    for key in ['or_053', 'or_054', 'or_055']:
        if key not in prices:
            prices[key] = prices['or_000'].copy()
            if key in ['or_054', 'or_055']:
                # diesel currently 1 ISK more expensive on these two stations
                prices[key]['diesel'] += 1
                prices[key]['diesel_discount'] += 1
    # /TEMPORARY_FIX
    return prices


if __name__ == '__main__':
    print 'Testing scrapers\n'
    print 'Atlantsolía'
    print get_individual_atlantsolia_prices()
    print 'Costco'
    print get_global_costco_prices()
    print 'Dælan'
    print get_individual_daelan_prices()
    print 'N1'
    print get_global_n1_prices()
    print 'Olís'
    print get_global_olis_prices()
    print 'ÓB'
    print get_individual_ob_prices()
    print 'Orkan (including Orkan X)'
    print get_individual_orkan_prices()
