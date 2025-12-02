import threading
from queue import Queue
import re
from tqdm import tqdm
import os
import sys
from collections import Counter
import traceback
import ctypes
from datetime import datetime
from typing import List
import webbrowser

# Try importing document parsing libraries
try:
    import docx
except ImportError:
    docx = None
    print("Warning: Library 'python-docx' not found. .docx files will not be processed.")
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
    print("Warning: Library 'PyPDF2' not found. .pdf files will not be processed.")

# Enable UTF-8 support in Windows console
if sys.platform.startswith('win'):
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    os.system('color')  # Enable ANSI support
    sys.stdout.reconfigure(encoding='utf-8')

# Logger setup (for colored output)
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'

def logger(message: str, type: str = 'info', end: str = '\n'):
    """
    Outputs a message to the console with a timestamp and type.
    Added 'end' parameter to control line ending character.
    """
    timestamp = datetime.now().strftime('%H:%M:%S')
    if type == 'info':
        sys.stdout.write(f"[{timestamp}] {message}{end}")
    elif type == 'success':
        sys.stdout.write(f"[{timestamp}] {Colors.GREEN}{message}{Colors.ENDC}{end}")
    elif type == 'error':
        sys.stderr.write(f"[{timestamp}] {Colors.RED}{message}{Colors.ENDC}{end}")
    elif type == 'warning':
        sys.stdout.write(f"[{timestamp}] {Colors.YELLOW}{message}{Colors.ENDC}{end}")
    else:
        sys.stdout.write(f"[{timestamp}] {message}{end}")
    sys.stdout.flush() # Force output to console

def find_all_supported_files(directory: str) -> List[str]:
    """
    Recursively finds all supported files in the specified directory and its subfolders.
    Supported formats: .txt, .csv, .json, .html, .docx, .pdf.
    Returns a list of full file paths.
    """
    supported_files = []
    supported_extensions = ('.txt', '.csv', '.json', '.html', '.docx', '.pdf')
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(supported_extensions):
                supported_files.append(os.path.join(root, file))
    return supported_files

class SeedParser:
    def __init__(self, input_path, num_threads=20):
        self.input_path = input_path
        self.num_threads = num_threads
        self.queue = Queue(maxsize=1000)
        
        self.found_data = {
            'keys': set(),
            'seeds_12_24': {'12': set(), '24': set()},
            'seeds_15_18_21': {'15': set(), '18': set(), '21': set()},
            'seeds_25': set(),
            'addresses': set(),
            'garbage': set()
        }
        
        self.stats = {
            'keys_total': 0,
            'seeds_12': 0,
            'seeds_24': 0,
            'seeds_15': 0,
            'seeds_18': 0,
            'seeds_21': 0,
            'seeds_25': 0,
            'addresses': 0,
            'garbage': 0,
            'total_lines': 0
        }
        self.lock = threading.Lock()
        
        self.output_folder = None
        self.output_files = {}

        self.key_in_dict_pattern = re.compile(r"'private_key':\s*['\"](0x)?[0-9a-fA-F]{64}['\"]")
        self.address_in_dict_pattern = re.compile(r"'address':\s*['\"](0x)?[0-9a-fA-F]{40}['\"]")
        self.pipe_separated_pattern = re.compile(r'^\$?\d+(\.\d+)?\s*\|\s*(0x)?[0-9a-fA-F]{40}\s*\|\s*(.+)$')
        self.common_csv_delimiters = [',', ';', '\t', '|']
        
    def create_output_folder(self):
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        
        base_name = os.path.basename(self.input_path)
        if os.path.isfile(self.input_path):
            input_name = os.path.splitext(base_name)[0]
        else:
            input_name = base_name
        
        folder_name = f"{timestamp} [{input_name}_result]"
        self.output_folder = os.path.join("results", folder_name)
        
        os.makedirs(self.output_folder, exist_ok=True)
        
        self.output_files = {
            'keys': os.path.join(self.output_folder, "keys.txt"),
            'seeds_12_24': os.path.join(self.output_folder, "seeds_12_24.txt"),
            'seeds_15_18_21': os.path.join(self.output_folder, "seeds_15_18_21.txt"),
            'seeds_25': os.path.join(self.output_folder, "seeds_25.txt"),
            'addresses': os.path.join(self.output_folder, "addresses.txt"),
            'garbage': os.path.join(self.output_folder, "garbage.txt")
        }
        
    def is_private_key(self, text):
        hex_pattern = re.compile(r'^(0x)?[0-9a-fA-F]{64}$')
        return bool(hex_pattern.match(text.strip()))
    
    def is_address(self, text):
        text = text.strip()
        
        btc_legacy = re.compile(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$')
        btc_bech32 = re.compile(r'^bc1[a-z0-9]{39,59}$')
        eth_pattern = re.compile(r'^(0x)?[0-9a-fA-F]{40}$')
        ltc_pattern = re.compile(r'^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}$')
        doge_pattern = re.compile(r'^D{1}[5-9A-HJ-NP-U]{1}[1-9A-HJ-NP-Za-km-z]{32}$')
        
        return (btc_legacy.match(text) or 
                btc_bech32.match(text) or 
                eth_pattern.match(text) or
                ltc_pattern.match(text) or
                doge_pattern.match(text))
        
    def normalize_private_key(self, key):
        key = key.strip()
        if not key.startswith('0x'):
            return '0x' + key
        return key
    
    def process_content_string(self, content_string: str) -> bool:
        """
        Helper function for processing a string (whole line or CSV cell)
        and categorizing it. Returns True if categorized, False otherwise.
        """
        content_string = content_string.strip()
        if not content_string:
            return False

        words = content_string.split()
        word_count = len(words)

        if self.is_private_key(content_string):
            normalized_key = self.normalize_private_key(content_string)
            with self.lock:
                if normalized_key not in self.found_data['keys']:
                    self.found_data['keys'].add(normalized_key)
                    self.stats['keys_total'] += 1
            return True
        elif self.is_address(content_string):
            with self.lock:
                if content_string not in self.found_data['addresses']:
                    self.found_data['addresses'].add(content_string)
                    self.stats['addresses'] += 1
            return True
        elif word_count in [12, 24]:
            with self.lock:
                if content_string not in self.found_data['seeds_12_24'][str(word_count)]:
                    self.found_data['seeds_12_24'][str(word_count)].add(content_string)
                    if word_count == 12:
                        self.stats['seeds_12'] += 1
                    else:
                        self.stats['seeds_24'] += 1
            return True
        elif word_count in [15, 18, 21]:
            with self.lock:
                if content_string not in self.found_data['seeds_15_18_21'][str(word_count)]:
                    self.found_data['seeds_15_18_21'][str(word_count)].add(content_string)
                    if word_count == 15:
                        self.stats['seeds_15'] += 1
                    elif word_count == 18:
                        self.stats['seeds_18'] += 1
                    else:
                        self.stats['seeds_21'] += 1
            return True
        elif word_count == 25:
            with self.lock:
                if content_string not in self.found_data['seeds_25']:
                    self.found_data['seeds_25'].add(content_string)
                    self.stats['seeds_25'] += 1
            return True
        return False
        
    def worker(self):
        while True:
            line = self.queue.get()
            if line is None:
                break
                
            with self.lock:
                self.stats['total_lines'] += 1
                
            original_line = line.strip()
            processed = False

            match_key_in_dict = self.key_in_dict_pattern.search(original_line)
            if match_key_in_dict:
                extracted_key = match_key_in_dict.group(0).split(':')[1].strip().strip("'\"")
                if self.process_content_string(extracted_key):
                    processed = True
            
            if not processed: 
                match_address_in_dict = self.address_in_dict_pattern.search(original_line)
                if match_address_in_dict:
                    extracted_address = match_address_in_dict.group(0).split(':')[1].strip().strip("'\"")
                    if self.process_content_string(extracted_address):
                        processed = True

            # Try to extract seed phrase from dictionary string representation with 'mnemonic'
            if not processed:
                if "'mnemonic':" in original_line:
                    mnemonic_part_raw = original_line.split("'mnemonic':", 1)[1].strip()
                    quoted_segments = re.findall(r"['\"](.*?)['\"]", mnemonic_part_raw)
                    
                    if quoted_segments:
                        extracted_mnemonic = " ".join(segment.strip() for segment in quoted_segments)
                        if self.process_content_string(extracted_mnemonic):
                            processed = True

            if not processed:
                match_pipe_separated = self.pipe_separated_pattern.match(original_line)
                if match_pipe_separated:
                    address_part = match_pipe_separated.group(2)
                    data_part = match_pipe_separated.group(3).strip()

                    if self.process_content_string(address_part):
                        processed = True
                    if self.process_content_string(data_part):
                        processed = True
                
            if not processed:
                for delimiter in self.common_csv_delimiters:
                    if delimiter in original_line and len(original_line.split(delimiter)) > 1:
                        parts = original_line.split(delimiter)
                        temp_processed_by_csv = False
                        for part in parts:
                            if self.process_content_string(part.strip()):
                                temp_processed_by_csv = True
                        if temp_processed_by_csv:
                            processed = True
                            break

            if not processed:
                if not self.process_content_string(original_line):
                    with self.lock:
                        if original_line not in self.found_data['garbage']:
                            self.found_data['garbage'].add(original_line)
                            self.stats['garbage'] += 1
                
            self.queue.task_done()
    
    def print_progress(self, pbar):
        stats_str = f"Keys: {self.stats['keys_total']} | "
        stats_str += f"Seeds 12w: {self.stats['seeds_12']} | Seeds 24w: {self.stats['seeds_24']} | "
        stats_str += f"Seeds 15w: {self.stats['seeds_15']} | Seeds 18w: {self.stats['seeds_18']} | Seeds 21w: {self.stats['seeds_21']} | "
        stats_str += f"Seeds 25w: {self.stats['seeds_25']} | "
        stats_str += f"Addresses: {self.stats['addresses']} | Garbage: {self.stats['garbage']}"
        pbar.set_description(stats_str)
    
    def save_results(self):
        if self.found_data['keys']:
            unique_keys = sorted(list(self.found_data['keys']))
            with open(self.output_files['keys'], 'w', encoding='utf-8') as f:
                f.write("=== Private Keys ===\n")
                for key in unique_keys:
                    f.write(f"{key}\n")
        
        if self.found_data['seeds_12_24']['12'] or self.found_data['seeds_12_24']['24']:
            with open(self.output_files['seeds_12_24'], 'w', encoding='utf-8') as f:
                if self.found_data['seeds_12_24']['12']:
                    unique_seeds_12 = sorted(list(self.found_data['seeds_12_24']['12']))
                    f.write("=== 12-Word Seeds ===\n")
                    for seed in unique_seeds_12:
                        f.write(f"{seed}\n")
                    f.write("\n")
                
                if self.found_data['seeds_12_24']['24']:
                    unique_seeds_24 = sorted(list(self.found_data['seeds_12_24']['24']))
                    f.write("=== 24-Word Seeds ===\n")
                    for seed in unique_seeds_24:
                        f.write(f"{seed}\n")
        
        if any(self.found_data['seeds_15_18_21'].values()):
            with open(self.output_files['seeds_15_18_21'], 'w', encoding='utf-8') as f:
                for word_count in ['15', '18', '21']:
                    if self.found_data['seeds_15_18_21'][word_count]:
                        unique_seeds = sorted(list(self.found_data['seeds_15_18_21'][word_count]))
                        f.write(f"=== {word_count}-Word Seeds ===\n")
                        for seed in unique_seeds:
                            f.write(f"{seed}\n")
                        f.write("\n")
        
        if self.found_data['seeds_25']:
            unique_seeds_25 = sorted(list(self.found_data['seeds_25']))
            with open(self.output_files['seeds_25'], 'w', encoding='utf-8') as f:
                f.write("=== 25-Word Seeds ===\n")
                for seed in unique_seeds_25:
                    f.write(f"{seed}\n")
        
        if self.found_data['addresses']:
            unique_addresses = sorted(list(self.found_data['addresses']))
            with open(self.output_files['addresses'], 'w', encoding='utf-8') as f:
                f.write("=== Addresses ===\n")
                for address in unique_addresses:
                    f.write(f"{address}\n")
        
        if self.found_data['garbage']:
            unique_garbage = sorted(list(self.found_data['garbage']))
            with open(self.output_files['garbage'], 'w', encoding='utf-8') as f:
                f.write("=== Unrecognized Lines ===\n")
                for garbage in unique_garbage:
                    f.write(f"{garbage}\n")
    
    def process_file(self):
        files_to_process = []
        total_size = 0

        # Determine supported extensions for single file check
        supported_single_file_extensions = ('.txt', '.csv', '.json', '.html', '.docx', '.pdf')

        if os.path.isfile(self.input_path):
            file_extension = os.path.splitext(self.input_path)[1].lower()
            if file_extension in supported_single_file_extensions:
                files_to_process.append(self.input_path)
                total_size = os.path.getsize(self.input_path)
            else:
                print(f"Error: File '{self.input_path}' has unsupported format '{file_extension}'.")
                print("Supported formats: .txt, .csv, .json, .html, .docx, .pdf.")
                input("Press Enter to exit...")
                return
        elif os.path.isdir(self.input_path):
            files_to_process = find_all_supported_files(self.input_path)
            if not files_to_process:
                print(f"No supported files found for processing in folder '{self.input_path}'.")
                input("Press Enter to exit...")
                return
            for f_path in files_to_process:
                total_size += os.path.getsize(f_path)
        else:
            print(f"Error: Input path '{self.input_path}' is not a file or folder!")
            input("Press Enter to exit...")
            return

        print("\nStarting file processing...")
        print("=" * 80)
        
        threads = []
        for _ in range(self.num_threads):
            t = threading.Thread(target=self.worker)
            t.daemon = True
            t.start()
            threads.append(t)
        
        with tqdm(total=total_size, unit='B', unit_scale=True) as pbar:
            for file_path in files_to_process:
                file_extension = os.path.splitext(file_path)[1].lower()
                content_lines = []
                try:
                    if file_extension in ('.txt', '.csv', '.json', '.html'):
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content_lines = f.readlines()
                    elif file_extension == '.docx':
                        if docx:
                            document = docx.Document(file_path)
                            content_lines = [p.text for p in document.paragraphs if p.text.strip()]
                        else:
                            logger(f"Skipping .docx file '{file_path}': library 'python-docx' not installed.", type='warning')
                            continue
                    elif file_extension == '.pdf':
                        if PyPDF2:
                            with open(file_path, 'rb') as f:
                                reader = PyPDF2.PdfReader(f)
                                for page_num in range(len(reader.pages)):
                                    page = reader.pages[page_num]
                                    text = page.extract_text()
                                    if text: # Add only if text is not empty
                                        content_lines.extend(text.splitlines())
                        else:
                            logger(f"Skipping .pdf file '{file_path}': library 'PyPDF2' not installed.", type='warning')
                            continue
                    # .doc, .odt, .rtf files are not directly supported in this version due to parsing complexity
                    # and potential dependency issues. It is recommended to convert them to .txt or .docx/.pdf.
                    # They will be ignored by the find_all_supported_files function.

                    for line in content_lines:
                        self.queue.put(line)
                        pbar.update(len(line.encode('utf-8')))
                        if self.stats['total_lines'] % 1000 == 0:
                            self.print_progress(pbar)
                except Exception as e:
                    logger(f"Error reading or parsing file '{file_path}' ({file_extension}): {e}", type='error')
                    traceback.print_exc()
        
        for _ in range(self.num_threads):
            self.queue.put(None)
            
        for t in threads:
            t.join()
        
        self.create_output_folder()
        self.save_results()
        
        print("\n" + "=" * 80)
        print("Processing Statistics:")
        print(f"Total lines processed: {self.stats['total_lines']}")
        print(f"Unique private keys: {len(self.found_data['keys'])}")
        print(f"Unique 12-word seed phrases: {len(self.found_data['seeds_12_24']['12'])}")
        print(f"Unique 24-word seed phrases: {len(self.found_data['seeds_12_24']['24'])}")
        print(f"Unique 15-word seed phrases: {len(self.found_data['seeds_15_18_21']['15'])}")
        print(f"Unique 18-word seed phrases: {len(self.found_data['seeds_15_18_21']['18'])}")
        print(f"Unique 21-word seed phrases: {len(self.found_data['seeds_15_18_21']['21'])}")
        print(f"Unique 25-word seed phrases: {len(self.found_data['seeds_25'])}")
        print(f"Unique addresses: {len(self.found_data['addresses'])}")
        print(f"Unique unrecognized lines: {len(self.found_data['garbage'])}")
        print("=" * 80)
        
        if self.output_folder:
            print(f"\nAll results saved to folder: {self.output_folder}")
            
            created_files = []
            for file_type, file_path in self.output_files.items():
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    filename = os.path.basename(file_path)
                    created_files.append(filename)
            
            if created_files:
                print("Created files:")
                for filename in created_files:
                    print(f"  {filename}")
            else:
                print("No results found (all output files are empty).")
        else:
            print("\nError creating results folder.")
            

def main():
    telegram_link_text = "Created By @boredmonkeyman"
    telegram_url = "https://t.me/boredmonkeyman"

    try:
        logger(f"{Colors.RED}{telegram_link_text}{Colors.ENDC}", type='info')
        print("\n")

        if len(sys.argv) != 2:
            print("Drag and drop a file or folder into the console window or enter the path:")
            input_path = input().strip().strip('"').strip("'")
            
            if not input_path:
                print("Path not specified!")
                input("Press Enter to exit...")
                return
        else:
            input_path = sys.argv[1]

        input_path = input_path.strip().strip('"').strip("'")
        
        print(f"\nProcessing path: {input_path}")
        
        if not os.path.exists(input_path):
            print(f"Error: Path '{input_path}' not found!")
            input("Press Enter to exit...")
            return
            
        if not os.path.isfile(input_path) and not os.path.isdir(input_path):
            print(f"Error: '{input_path}' is neither a file nor a directory!")
            input("Press Enter to exit...")
            return

        parser = SeedParser(input_path)
        parser.process_file()
        
    except Exception as e:
        print("\nAn error occurred while executing the program:")
        print(f"Error type: {type(e).__name__}")
        print(f"Description: {str(e)}")
        print("\nError details:")
        traceback.print_exc()
        input("\nPress Enter to exit...")
    finally:
        print("\n" + "=" * 80)
        logger(f"{Colors.RED}{telegram_link_text}{Colors.ENDC}", type='info')
        print("=" * 80)
        print("Program execution finished.")
        webbrowser.open(telegram_url)

if __name__ == "__main__":
    main()