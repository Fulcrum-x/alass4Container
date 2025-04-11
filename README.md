# alass4Container

A Python tool that automatically synchronizes subtitle tracks on the selected MKV using alass (Automatic Language-Agnostic Subtitle Synchronization).

## Features

- **Automatic extraction** of all subtitle tracks from MKV files
- **Preservation of language tags** (e.g., en, es-419, fr-FR) and track order
- **Support for multiple subtitle formats** (SRT, ASS/SSA, IDX)
- **Batch processing** of all subtitle tracks in a single operation
- **Customizable synchronization** with adjustable split penalty
- **Clean remuxing** of corrected subtitles back into the original video

## What's the point?

This tool combines the powerful synchronization capabilities of alass with the container manipulation features of MKVToolNix to provide a seamless workflow.

## Prerequisites

- Python 3.6 or higher
- MKVToolNix (mkvmerge and mkvextract)
- alass

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/Fulcrum-x/alass4Container.git
   cd alass4Container
   ```

2. Install required Python dependencies:
   ```
   pip install tkinter
   ```

3. Install external tools:

   **MKVToolNix**:
   - Windows: Download and install from [mkvtoolnix.download](https://mkvtoolnix.download/)
   - Linux: `sudo apt install mkvtoolnix` (Ubuntu/Debian) or `sudo dnf install mkvtoolnix` (Fedora)
   - macOS: `brew install mkvtoolnix` (using Homebrew)

   **alass**:
   - Download from [GitHub releases](https://github.com/kaegi/alass/releases)
   - Add to your system PATH

## Usage

Run the script:
```
python alass4Container.py
```

The tool will guide you through the following steps:
1. Select an MKV file
2. Configure synchronization options (split penalty, no-splits mode)
3. Process the file (extraction, synchronization, remuxing)
4. Save the result as `[original_filename].corrected.mkv`

## Configuration Options

- **Split Penalty**: Controls how likely alass is to introduce splits in subtitles
  - Range: 0-1000 (default is 7)
  - Higher values make splits less likely
  - Recommended range: 5-20

- **No Splits Mode**: When enabled, only applies constant time shifts
  - Faster processing
  - Less accurate for complex desynchronization issues
  - Useful for subtitles that are simply offset by a constant amount

## Example Use Cases

- Synchronize subtitles downloaded from different sources
- Fix subtitles with incorrect timing due to framerate differences
- Repair subtitles broken by advertisement cuts or director's cuts
- Batch process subtitle tracks in multiple languages at once

## Troubleshooting

### Common Issues

**Tool not found errors**:
Make sure MKVToolNix and alass are installed and added to your system PATH.

**Synchronization failures**:
- Try adjusting the split penalty
- Check if the subtitle format is supported
- Ensure the subtitle track contains actual content

**Output file issues**:
- Check disk space
- Ensure you have write permissions for the output directory

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [alass](https://github.com/kaegi/alass) - The underlying subtitle synchronization engine
- [MKVToolNix](https://mkvtoolnix.download/) - Tools for manipulating MKV files

## TODO

- (04/10/25) Support for merging of external subtitle files not embedded in MKV
