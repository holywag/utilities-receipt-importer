from datetime import datetime
import requests

UTILITY_SERVICES = {
    'Електроенергія': {
        'service_name': 'electric',
        'mcc': 4900,
    },
    'Газ': {
        'service_name': 'gas',
        'mcc': 4900,
    },
    'Газ (доставлення)': {
        'service_name': 'gas_delivery',
        'mcc': 4900,
    },
    'Холодна вода': {
        'service_name': 'water',
        'mcc': 4900,
    },
    'Холодна вода (водовідведення)': {
        'service_name': 'water_delivery',
        'mcc': 4900,
    },
    'I\u043d\u0448\u0435': {
        'service_name': 'water_service_fee',
        'mcc': 4900,
    },
    '536354****1179': {
        'service_name': 'rent',
        'mcc': 4829,
    },
    '414960****2931': {
        'service_name': 'rent',
        'mcc': 4829,
    },
}

def contains_permission(permissions, type, role): 
    for p in permissions:
        if p['type'] == type and p['role'] == role:
            return True
    return False

def get_service_name(stmt):
    svc = UTILITY_SERVICES.get(stmt['description'])
    return svc['service_name'] if svc and stmt['mcc'] == svc['mcc'] else None

def is_utility_statement(stmt):
    return get_service_name(stmt) is not None

def make_receipt_file_name(service_name, stmt):
    time = datetime.fromtimestamp(int(stmt['time']))
    if service_name == 'rent':
        return f'rent_from_{time.year}_{time.month:02d}_18_to_{time.year}_{time.month+1:02d}_17.pdf'
    else:
        return f'{time.year}_{time.month-1:02d}_{service_name}.pdf'

def download_file(url, output_file_path):
    for i in range(5):
        response = requests.get(url)
        if response.status_code == 200:
            with open(output_file_path, 'wb') as file:
                file.write(response.content)
            return
        else:
            print(f'{response.status_code} {response.reason} - trying again')
    raise Exception(f'Cannot download file from {url}')
