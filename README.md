# Seed Parser

come chat and ask questions or suggest new scripts to create 

https://t.me/boredmanhq

A powerful, multi-threaded Python tool for parsing and extracting cryptocurrency-related data from various file formats. The script can identify and categorize private keys, seed phrases (mnemonics), addresses, and other data from text-based files, PDFs, and Word documents.

## Features

- **Multi-format Support**: Processes `.txt`, `.csv`, `.json`, `.html`, `.docx`, and `.pdf` files
- **Multi-threaded Processing**: Uses up to 20 threads for fast processing of large datasets
- **Smart Data Categorization**: Automatically categorizes found data into:
  - Private keys (64-character hex strings)
  - Seed phrases (12, 15, 18, 21, 24, 25 words)
  - Cryptocurrency addresses (BTC, ETH, LTC, DOGE formats)
  - Unrecognized data
- **Pattern Recognition**: Identifies data in various formats including:
  - Dictionary-style entries (`'private_key': '...'`)
  - CSV/delimited files
  - Pipe-separated data
  - Raw strings
- **Progress Tracking**: Real-time progress bar with detailed statistics
- **Output Organization**: Creates timestamped folders with categorized output files
- **Color-coded Logging**: Easy-to-read console output with colored messages

## Installation

### Prerequisites

- Python 3.6 or higher
- pip (Python package manager)

### Required Libraries

Install the required libraries using pip:

```bash
pip install tqdm python-docx PyPDF2
```

Optional dependencies:
- `python-docx`: For processing `.docx` files
- `PyPDF2`: For processing `.pdf` files

If these libraries are not installed, the parser will skip those file types and continue processing.

## Usage

### Basic Usage

You can use the parser in two ways:

1. **Drag and Drop**: Drag a file or folder onto the script
2. **Command Line**: Specify the path as an argument

```bash
python "Seed Parser.py" "path/to/your/file_or_folder"
```

### Interactive Mode

If no path is provided as an argument, the script will prompt you to enter or drag-and-drop a file/folder:

```bash
python "Seed Parser.py"
```

## Supported Data Formats

### Private Keys
- 64-character hexadecimal strings
- With or without `0x` prefix
- Example: `0x0123456789abcdef...` or `0123456789abcdef...`

### Seed Phrases
- **Common**: 12, 24 words
- **Less common**: 15, 18, 21, 25 words
- Space-separated words
- Extracted from dictionary format: `'mnemonic': 'word1 word2 ...'`

### Cryptocurrency Addresses
- **Bitcoin**: Legacy (P2PKH, P2SH) and Bech32 (SegWit)
- **Ethereum**: 40-character hex (with/without `0x`)
- **Litecoin**: Addresses starting with L, M, or 3
- **Dogecoin**: Addresses starting with D

### Other Supported Patterns
- Dictionary entries: `'private_key': '...'`, `'address': '...'`
- Pipe-separated: `amount | address | data`
- CSV/delimited files with common separators: `,` `;` `\t` `|`

## Output Structure

Results are saved in a timestamped folder within the `results/` directory:

```
results/
└── YYYY-MM-DD_HH-MM-SS [filename_result]/
    ├── keys.txt              # Private keys found
    ├── seeds_12_24.txt       # 12 and 24-word seeds
    ├── seeds_15_18_21.txt    # 15, 18, and 21-word seeds
    ├── seeds_25.txt          # 25-word seeds
    ├── addresses.txt         # Cryptocurrency addresses
    └── garbage.txt           # Unrecognized lines
```

Each output file contains categorized, unique entries sorted alphabetically.

## Performance Tips

1. **Large Files**: The parser handles large files efficiently using multi-threading
2. **Multiple Files**: When processing folders, all supported files are processed recursively
3. **Memory Usage**: Files are read line-by-line to minimize memory consumption
4. **Progress**: Real-time statistics show what types of data are being found

## Limitations

- **Unsupported Formats**: `.doc`, `.odt`, `.rtf` files are not directly supported
- **Encoding**: Uses UTF-8 encoding; may have issues with other encodings
- **Complex PDFs**: May not extract text perfectly from scanned or complex PDF documents
- **Binary Data**: Only processes text-based data within files

## Troubleshooting

### Common Issues

1. **"Module not found" errors**:
   - Install missing dependencies: `pip install python-docx PyPDF2`

2. **File encoding issues**:
   - The script uses `errors='ignore'` to handle encoding problems

3. **Empty output files**:
   - Check if your files contain data in supported formats
   - Verify file permissions

4. **Processing takes too long**:
   - Reduce thread count by modifying `num_threads` parameter in the script

### Error Messages

- **Warnings**: Indicate skipped files due to missing libraries
- **Errors**: File access issues or parsing problems
- **Statistics**: Final output shows what was found and categorized

## License

This tool is provided for educational and research purposes only. Users are responsible for complying with all applicable laws and regulations regarding data processing and cryptocurrency usage.

## Disclaimer

This software is provided "as is", without warranty of any kind. The authors are not responsible for any loss of funds, data, or other damages resulting from the use of this tool. Always exercise caution when handling cryptocurrency keys and seed phrases.

## Development

### Adding New Patterns

To add support for new data patterns, modify the `process_content_string()` method and add appropriate regular expressions to the `__init__()` method.

### Extending Functionality

The modular design allows for easy extension:
- Add new file format parsers in the `process_file()` method
- Add new cryptocurrency address formats in the `is_address()` method
- Modify thread count in the constructor for performance tuning

## Support

For issues and feature requests, please check the documentation and ensure you're using the latest version of the script.
