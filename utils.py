import requests

def download_file(url, output_file_path):
    for i in range(5):
        print(f'Downloading {output_file_path} from {url}')
        response = requests.get(url)
        if response.status_code == 200:
            with open(output_file_path, 'wb') as file:
                file.write(response.content)
            return
        else:
            print(f'{response.status_code} {response.reason} - trying again')
    raise Exception(f'Cannot download file from {url}')
