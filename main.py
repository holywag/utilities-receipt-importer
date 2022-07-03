from datetime import datetime
from selenium import webdriver
from monobank import MonobankApi
import monobank, check_gov_ua, google_oauth, google_drive, google_sheets, utils
import os

monobank_token = '<monobank API token>'
iban = '<iban of monobank account>'
google_drive_directory_id = '<google drive directory ID where receipts are to be uploaded>'
credentials_file_path = '<file containing google oath credentials>'
spreadsheet_id = '<spreadsheet where shared links are to be added>'

PAYEE_TO_SERVICE_NAME = {
    'Електроенергія': 'electric',
    'Газ': 'gas',
    'Газ (доставлення)': 'gas_delivery',
    'Холодна вода': 'water',
    'Холодна вода (водовідведення)': 'water_delivery'
}

print('Requesting statements info from monobank')

monobank_client = monobank.MonobankApi(monobank_token)
account_id = monobank_client.request_account_id(iban)
statements = monobank_client.request_statements_for_last_n_days(account_id, 30)

utility_statements = []

print("Starting Safari webdriver")
with webdriver.Safari() as driver:
    check_gov_ua_client = check_gov_ua.CheckGovUaApi(driver)
    for stmt in filter(lambda s: s['description'] in PAYEE_TO_SERVICE_NAME, statements):
        print(f'Getting download link for statement {stmt["receiptId"]}')
        recaptcha_token = check_gov_ua_client.get_recaptcha_token()
        receipt_url = check_gov_ua_client.request_download_link('monobank', stmt['receiptId'], recaptcha_token)
        stmt['receiptUrl'] = receipt_url
        utility_statements.append(stmt)

creds = google_oauth.GoogleOAuth(credentials_file_path).authenticate(
    google_oauth.GoogleOAuthScopes.DRIVE_FILE, google_oauth.GoogleOAuthScopes.SHEETS)

google_drive_client = google_drive.GoogleDriveApi(creds)
google_sheets_client = google_sheets.GoogleSheetsApi(creds)

for stmt in utility_statements:
    service_name = PAYEE_TO_SERVICE_NAME[stmt['description']]
    time = datetime.fromtimestamp(int(stmt['time']))
    receipt_file_name = f'{time.year}_{time.month-1:02d}_{service_name}.pdf'

    utils.download_file(stmt["receiptUrl"], receipt_file_name)

    # todo: check if such file already exists
    print(f'Uploading {receipt_file_name} to Google Drive')
    file_id = google_drive_client.upload_file_to_directory(receipt_file_name, 'application/pdf', google_drive_directory_id)

    print(f'Removing temporary file {receipt_file_name}')
    os.remove(receipt_file_name)

    print(f'Enabling link sharing for {receipt_file_name}')
    google_drive_client.enable_link_sharing(file_id, "reader", "anyone")

    shared_link = f'https://drive.google.com/file/d/{file_id}/view?usp=sharing'

    print(f'Adding {shared_link} to Google Sheets')
    range_values = google_sheets_client.get_range(spreadsheet_id, f'{service_name}!G:G', google_sheets.ValueRenderOption.FORMULA)
    hyperlink_formula = f'=HYPERLINK("{shared_link}", {-stmt["amount"]/100})'
    values = google_sheets_client.update_range(
        spreadsheet_id,
        f'{service_name}!G{len(range_values)}',
        [[hyperlink_formula]],
        google_sheets.ValueInputOption.USER_ENTERED,
        True,
        google_sheets.ValueRenderOption.UNFORMATTED_VALUE)
    print(f'Link to {service_name} receipt for {values[0][0]} UAH has been added to the spreadsheet')
