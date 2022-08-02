#!/usr/bin/env python3

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

google_creds = oauth.GoogleOAuth(args.credentials_file_path).authenticate(
    oauth.GoogleOAuthScopes.DRIVE_FILE, oauth.GoogleOAuthScopes.SHEETS)

drive = gdrive.GoogleDriveApi(google_creds)
sheets = gsheets.GoogleSheetsApi(google_creds)
monobank = Monobank(args.monobank_token)
check_gov_ua = None

print('Requesting statements from monobank')

account_id = monobank.request_account_id(args.iban)
statements = monobank.request_statements_for_last_n_days(account_id, 1)

print('Synchronizing with Google Drive')

for stmt in filter(utils.is_utility_statement, statements):
    service_name = utils.get_service_name(stmt)
    receipt_file_name = utils.make_receipt_file_name(service_name, stmt)
    google_drive_id = drive.find_first_file(
        receipt_file_name, parent_directory_id=args.google_drive_directory_id, mime_type='application/pdf')

    if google_drive_id is None:
        print(f'Receipt for {service_name} was not found in Google Drive, trying to upload it')
        print(f'Getting download link for statement {stmt["receiptId"]}')
        if check_gov_ua is None:
            print("Starting Safari webdriver")
            check_gov_ua = CheckGovUa(webdriver.Safari())
        recaptcha_token = check_gov_ua.get_recaptcha_token()
        receipt_url = check_gov_ua.request_download_link('monobank', stmt['receiptId'], recaptcha_token)
        
        print(f'Downloading from {receipt_url}')
        utils.download_file(receipt_url, receipt_file_name)

        print(f'Uploading {receipt_file_name} to Google Drive')
        google_drive_id = drive.upload_file_to_directory(
            receipt_file_name, 'application/pdf', args.google_drive_directory_id)

        print(f'Removing temporary file {receipt_file_name}')
        os.remove(receipt_file_name)

    permissions = drive.get_file_permissions(google_drive_id)
    if permissions is None or not utils.contains_permission(permissions, 'anyone', 'reader'):
        print(f'Enabling link sharing for {receipt_file_name}')
        drive.enable_link_sharing(google_drive_id, 'reader', 'anyone')

    shared_link = f'https://drive.google.com/file/d/{google_drive_id}/view?usp=sharing'

    print(f'Verifying that the link to {receipt_file_name} is added to Google Sheets')
    range_values = sheets.get_range(args.spreadsheet_id, f'{service_name}!G:G', gsheets.ValueRenderOption.FORMULA)
    hyperlink_formula = f'=HYPERLINK("{shared_link}", {-stmt["amount"]/100})'
    if hyperlink_formula != range_values[-1][0]:
        values = sheets.update_range(
            args.spreadsheet_id,
            f'{service_name}!G{len(range_values)}',
            [[hyperlink_formula]],
            gsheets.ValueInputOption.USER_ENTERED,
            True,
            gsheets.ValueRenderOption.UNFORMATTED_VALUE)
        print(f'Link to {service_name} receipt for {values[0][0]} UAH has been added to the spreadsheet')
