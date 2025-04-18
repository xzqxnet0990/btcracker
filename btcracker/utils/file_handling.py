import os
import bz2
import gzip
import tarfile
import zipfile
import tempfile
from btcracker.utils.logging import log

def extract_passwords_from_file(filename):
    """Extract passwords from a file, handling compressed formats."""
    passwords = []
    
    try:
        # Handle different file formats
        if filename.endswith('.txt'):
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                passwords = [line.strip() for line in f if line.strip()]
        elif filename.endswith('.bz2'):
            with bz2.open(filename, 'rt', encoding='utf-8', errors='ignore') as f:
                passwords = [line.strip() for line in f if line.strip()]
        elif filename.endswith('.gz'):
            with gzip.open(filename, 'rt', encoding='utf-8', errors='ignore') as f:
                passwords = [line.strip() for line in f if line.strip()]
        elif filename.endswith('.tgz') or filename.endswith('.tar.gz'):
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    with tarfile.open(filename, 'r:gz') as tar:
                        tar.extractall(path=tmpdir)
                        for root, _, files in os.walk(tmpdir):
                            for file in files:
                                if file.endswith('.txt'):
                                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                                        passwords.extend([line.strip() for line in f if line.strip()])
                except Exception as e:
                    log(f"Error extracting {filename}: {e}", level=1)
        elif filename.endswith('.zip'):
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    with zipfile.ZipFile(filename, 'r') as zip_ref:
                        zip_ref.extractall(tmpdir)
                        for root, _, files in os.walk(tmpdir):
                            for file in files:
                                if file.endswith('.txt'):
                                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                                        passwords.extend([line.strip() for line in f if line.strip()])
                except Exception as e:
                    log(f"Error extracting {filename}: {e}", level=1)
    except Exception as e:
        log(f"Error processing file {filename}: {e}", level=1)
    
    return passwords

def collect_password_files(base_dir):
    """收集指定目录下的所有密码字典文件，包括子目录和压缩文件"""
    password_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # Include text files and compressed files that might contain passwords
            if file.endswith(('.txt', '.bz2', '.gz', '.tgz', '.tar.gz', '.zip')):
                password_files.append(file_path)
    print(f"收集到 {len(password_files)} 个密码文件")
    return password_files 