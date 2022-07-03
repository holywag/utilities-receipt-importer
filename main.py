#!/usr/bin/env python3

from datetime import datetime
from selenium import webdriver
from monobank import Monobank
from check_gov_ua import CheckGovUa
import utils, google_cloud.oauth as oauth, google_cloud.drive as gdrive, google_cloud.sheets as gsheets
import os, argparse

parser = argparse.ArgumentParser()
parser.add_argument('monobank_token', help='monobank API token')
parser.add_argument('iban', help='IBAN of monobank account')
parser.add_argument('google_drive_directory_id', help='google drive directory ID where receipts are to be uploaded')
parser.add_argument('credentials_file_path', help='file containing google oath credentials')
parser.add_argument('spreadsheet_id', help='spreadsheet where shared links are to be added')
args = parser.parse_args()

PAYEE_TO_SERVICE_NAME = {
    'Електроенергія': 'electric',
    'Газ': 'gas',
    'Газ (доставлення)': 'gas_delivery',
    'Холодна вода': 'water',
    'Холодна вода (водовідведення)': 'water_delivery'
}

print('Requesting statements info from monobank')

monobank = Monobank(args.monobank_token)
account_id = monobank.request_account_id(args.iban)
statements = monobank.request_statements_for_last_n_days(account_id, 30)

utility_statements = []

print("Starting Safari webdriver")
with webdriver.Safari() as driver:
    check_gov_ua = CheckGovUa(driver)
    for stmt in filter(lambda s: s['description'] in PAYEE_TO_SERVICE_NAME, statements):
        print(f'Getting download link for statement {stmt["receiptId"]}')
        recaptcha_token = check_gov_ua.get_recaptcha_token()
        receipt_url = check_gov_ua.request_download_link('monobank', stmt['receiptId'], recaptcha_token)
        stmt['receiptUrl'] = receipt_url
        utility_statements.append(stmt)

creds = oauth.GoogleOAuth(args.credentials_file_path).authenticate(
    oauth.GoogleOAuthScopes.DRIVE_FILE, oauth.GoogleOAuthScopes.SHEETS)

drive = gdrive.GoogleDriveApi(creds)
sheets = gsheets.GoogleSheetsApi(creds)

for stmt in utility_statements:
    service_name = PAYEE_TO_SERVICE_NAME[stmt['description']]
    time = datetime.fromtimestamp(int(stmt['time']))
    receipt_file_name = f'{time.year}_{time.month-1:02d}_{service_name}.pdf'

    utils.download_file(stmt["receiptUrl"], receipt_file_name)

    # todo: check if such file already exists
    print(f'Uploading {receipt_file_name} to Google Drive')
    file_id = drive.upload_file_to_directory(receipt_file_name, 'application/pdf', args.google_drive_directory_id)

    print(f'Removing temporary file {receipt_file_name}')
    os.remove(receipt_file_name)

    print(f'Enabling link sharing for {receipt_file_name}')
    drive.enable_link_sharing(file_id, "reader", "anyone")

    shared_link = f'https://drive.google.com/file/d/{file_id}/view?usp=sharing'

    print(f'Adding {shared_link} to Google Sheets')
    range_values = sheets.get_range(args.spreadsheet_id, f'{service_name}!G:G', gsheets.ValueRenderOption.FORMULA)
    hyperlink_formula = f'=HYPERLINK("{shared_link}", {-stmt["amount"]/100})'
    values = sheets.update_range(
        args.spreadsheet_id,
        f'{service_name}!G{len(range_values)}',
        [[hyperlink_formula]],
        gsheets.ValueInputOption.USER_ENTERED,
        True,
        gsheets.ValueRenderOption.UNFORMATTED_VALUE)
    print(f'Link to {service_name} receipt for {values[0][0]} UAH has been added to the spreadsheet')
