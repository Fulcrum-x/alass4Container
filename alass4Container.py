import os
import tempfile
import subprocess
import sys
import json
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from pathlib import Path
import shutil
import re

# Global variables to store tool paths
MKVMERGE_PATH = None
MKVEXTRACT_PATH = None
ALASS_PATH = None

# Function to find a tool in PATH or common locations
def find_tool(tool_name):
    # Try with and without .exe extension for Windows compatibility
    possible_names = [tool_name]
    if sys.platform == 'win32':
        possible_names.append(f"{tool_name}.exe")
        possible_names.append(f"{tool_name}-cli.exe")  # For alass on Windows
        
    # First try to find it in PATH
    for name in possible_names:
        path = shutil.which(name)
        if path:
            return path
    
    # If on Windows, look in common installation directories
    if sys.platform == 'win32':
        common_dirs = [
            os.path.expandvars("%ProgramFiles%\\MKVToolNix"),
            os.path.expandvars("%ProgramFiles(x86)%\\MKVToolNix"),
            os.path.expandvars("%LOCALAPPDATA%\\Programs\\MKVToolNix"),
            os.path.expandvars("%APPDATA%\\MKVToolNix"),
            os.path.expandvars("%USERPROFILE%\\AppData\\Local\\MKVToolNix"),
            os.path.expandvars("%USERPROFILE%\\AppData\\Roaming\\MKVToolNix"),
            os.path.expandvars("%USERPROFILE%\\Downloads\\alass"),
            os.path.join(os.getcwd(), "bin"),  # Check in a bin directory in current working directory
            os.getcwd()  # Check in current directory
        ]
        
        # Additional paths for alass
        if tool_name == "alass":
            common_dirs.extend([
                os.path.expandvars("%USERPROFILE%\\Documents\\alass"),
                os.path.expandvars("%USERPROFILE%\\Desktop\\alass"),
                os.path.expandvars("%LOCALAPPDATA%\\Programs\\alass"),
                os.path.expandvars("%APPDATA%\\alass"),
            ])
            
        for directory in common_dirs:
            if os.path.exists(directory):
                for name in possible_names:
                    path = os.path.join(directory, name)
                    if os.path.isfile(path):
                        return path
    
    return None

# Function to verify tools are available
def check_tools():
    global MKVMERGE_PATH, MKVEXTRACT_PATH, ALASS_PATH
    missing_tools = []
    
    # Check for mkvmerge
    MKVMERGE_PATH = find_tool("mkvmerge")
    if not MKVMERGE_PATH:
        missing_tools.append("mkvmerge")
    
    # Check for mkvextract
    MKVEXTRACT_PATH = find_tool("mkvextract")
    if not MKVEXTRACT_PATH:
        missing_tools.append("mkvextract")
    
    # Check for alass
    ALASS_PATH = find_tool("alass")
    if not ALASS_PATH:
        # Try alass-cli as an alternative
        ALASS_PATH = find_tool("alass-cli")
        if not ALASS_PATH:
            missing_tools.append("alass")
    
    if missing_tools:
        missing_str = ", ".join(missing_tools)
        print(f"Error: Required tools are missing: {missing_str}")
        print(f"Paths searched: PATH environment variable and common installation directories.")
        print("Please make sure mkvtoolnix (mkvmerge, mkvextract) and alass are installed and in your PATH.")
        
        # Create a graphical error message
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing Tools", 
            f"The following tools are required but could not be found: {missing_str}\n\n"
            "Please make sure MKVToolNix and alass are installed and in your PATH."
        )
        
        return False
    
    # Verify the tools work by checking their version/help output
    try:
        subprocess.run([MKVMERGE_PATH, "--version"], capture_output=True, check=True)
        subprocess.run([MKVEXTRACT_PATH, "--version"], capture_output=True, check=True)
        subprocess.run([ALASS_PATH, "--help"], capture_output=True, check=True)
        return True
    except subprocess.SubprocessError as e:
        print(f"Error running tools: {e}")
        messagebox.showerror(
            "Tool Verification Failed", 
            f"Found the tools, but encountered an error when trying to run them: {e}"
        )
        return False

# Function to select an MKV file
def select_mkv_file():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    file_path = filedialog.askopenfilename(
        title="Select MKV file",
        filetypes=[("MKV files", "*.mkv")]
    )
    if not file_path:
        print("No file selected. Exiting.")
        sys.exit(0)
    return file_path

# Function to extract subtitle information from MKV
def get_subtitle_tracks(mkv_file):
    try:
        cmd = [MKVMERGE_PATH, "-J", mkv_file]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Parse JSON output
        info = json.loads(result.stdout)
        
        subtitle_tracks = []
        
        # Extract subtitle tracks
        for track in info.get('tracks', []):
            if track.get('type') == 'subtitles':
                track_id = track.get('id')
                properties = track.get('properties', {})
                language = properties.get('language', 'und')  # Default to 'und' (undefined) if no language
                track_name = properties.get('track_name', '')
                codec = track.get('codec', '').lower()
                
                if track_id is not None:
                    subtitle_tracks.append((str(track_id), language, track_name, codec))
        
        return subtitle_tracks
    except subprocess.SubprocessError as e:
        print(f"Error running mkvmerge: {e}")
        messagebox.showerror("Error", f"Failed to analyze MKV file: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing mkvmerge output: {e}")
        messagebox.showerror("Error", f"Failed to parse MKV information: {e}")
        sys.exit(1)

# Function to extract subtitle tracks to temp directory
def extract_subtitles(mkv_file, subtitle_tracks, temp_dir):
    extracted_files = []
    
    for track_id, language, track_name, codec in subtitle_tracks:
        # Determine the appropriate extension based on codec
        ext = "srt"
        if "ass" in codec or "ssa" in codec:
            ext = "ass"
        elif "vobsub" in codec:
            ext = "idx"
        elif "pgs" in codec:
            print(f"Warning: Track {track_id} ({language}) is a PGS subtitle which cannot be processed by alass. Skipping.")
            continue
        
        output_file = os.path.join(temp_dir, f"{track_id}.{language}.{ext}")
        
        try:
            # Use mkvextract to extract the subtitle track
            cmd = [MKVEXTRACT_PATH, "tracks", mkv_file, f"{track_id}:{output_file}"]
            print(f"Extracting track {track_id} ({language}, {codec})...")
            subprocess.run(cmd, check=True)
            
            # Check if the file exists and is not empty
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                extracted_files.append((track_id, language, track_name, output_file, ext))
            else:
                print(f"Warning: Failed to extract subtitle track {track_id} ({language})")
        except subprocess.SubprocessError as e:
            print(f"Error extracting subtitle track {track_id}: {e}")
    
    return extracted_files

# Function to run alass on each subtitle file
def sync_subtitles(mkv_file, extracted_files, temp_dir, split_penalty=None, no_splits=False):
    corrected_files = []
    
    for track_id, language, track_name, subtitle_file, ext in extracted_files:
        # Define output file path for corrected subtitle
        corrected_file = os.path.join(temp_dir, f"{track_id}.{language}.corrected.{ext}")
        
        try:
            # Build the alass command
            cmd = [ALASS_PATH]
            
            # Add options if specified
            if split_penalty is not None:
                cmd.extend(["--split-penalty", str(split_penalty)])
            if no_splits:
                cmd.append("--no-splits")
            
            # Add the reference, input file, and output file
            cmd.extend([mkv_file, subtitle_file, corrected_file])
            
            print(f"Synchronizing track {track_id} ({language})...")
            subprocess.run(cmd, check=True)
            
            # Check if the corrected file was created
            if os.path.exists(corrected_file) and os.path.getsize(corrected_file) > 0:
                corrected_files.append((track_id, language, track_name, corrected_file))
            else:
                print(f"Warning: Synchronization failed for track {track_id} ({language})")
        except subprocess.SubprocessError as e:
            print(f"Error synchronizing subtitle track {track_id}: {e}")
    
    return corrected_files

# Function to create a new MKV with corrected subtitles
def create_new_mkv(mkv_file, corrected_files):
    output_file = os.path.splitext(mkv_file)[0] + ".corrected.mkv"
    
    try:
        # Start building the mkvmerge command to include everything except subtitles
        cmd = [MKVMERGE_PATH, "-o", output_file, "--no-subtitles", mkv_file]
        
        # Add each corrected subtitle file
        # Sort them based on original track ID to preserve order
        for track_id, language, track_name, subtitle_file in sorted(corrected_files, key=lambda x: int(x[0])):
            cmd_extension = ["--language", f"0:{language}"]
            
            # Add track name if it exists
            if track_name:
                cmd_extension.extend(["--track-name", f"0:{track_name}"])
            
            cmd_extension.append(subtitle_file)
            cmd.extend(cmd_extension)
        
        # Run the command
        print("Creating new MKV with corrected subtitles...")
        subprocess.run(cmd, check=True)
        
        return output_file
    except subprocess.SubprocessError as e:
        print(f"Error creating new MKV file: {e}")
        messagebox.showerror("Error", f"Failed to create new MKV: {e}")
        return None

# Function to get user options
def get_options():
    # Initialize with default values
    options = {
        "split_penalty": None,
        "no_splits": False
    }
    
    # Create a root window for dialogs
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Ask if the user wants to adjust the split penalty
    adjust_split = simpledialog.askstring(
        "Split Penalty",
        "Do you want to adjust the split penalty? (yes/no)\nDefault is 7, higher values avoid splits.",
        parent=root
    )
    
    if adjust_split and adjust_split.lower() == 'yes':
        split_penalty = simpledialog.askfloat(
            "Split Penalty Value",
            "Enter a value between 0 and 1000 (default is 7):\nHigher values make splits less likely.",
            parent=root,
            minvalue=0,
            maxvalue=1000
        )
        
        if split_penalty is not None:
            options["split_penalty"] = split_penalty
    
    # Ask if the user wants to disable splits entirely
    no_splits = simpledialog.askstring(
        "No Splits",
        "Do you want to disable splits entirely? (yes/no)\nOnly constant time shifts will be applied.",
        parent=root
    )
    
    if no_splits and no_splits.lower() == 'yes':
        options["no_splits"] = True
    
    root.destroy()
    return options

# Main function
def main():
    print("MKV Subtitle Synchronizer")
    print("------------------------")
    
    # Check for required tools
    if not check_tools():
        sys.exit(1)
    
    # Select MKV file
    mkv_file = select_mkv_file()
    print(f"Selected: {mkv_file}")
    
    # Get user options
    options = get_options()
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Get subtitle tracks
            subtitle_tracks = get_subtitle_tracks(mkv_file)
            if not subtitle_tracks:
                print("No subtitle tracks found in the MKV file.")
                messagebox.showinfo("No Subtitles", "No subtitle tracks found in the selected MKV file.")
                return
            
            print(f"Found {len(subtitle_tracks)} subtitle tracks:")
            for track_id, language, track_name, codec in subtitle_tracks:
                print(f"  - Track {track_id}: Language={language}, Name={track_name or 'N/A'}, Codec={codec}")
            
            # Extract subtitles
            extracted_files = extract_subtitles(mkv_file, subtitle_tracks, temp_dir)
            if not extracted_files:
                print("Failed to extract any subtitle tracks.")
                messagebox.showwarning("Extraction Failed", "Failed to extract any subtitle tracks from the MKV file.")
                return
            
            # Synchronize subtitles
            corrected_files = sync_subtitles(
                mkv_file, 
                extracted_files, 
                temp_dir,
                split_penalty=options.get("split_penalty"),
                no_splits=options.get("no_splits", False)
            )
            
            if not corrected_files:
                print("Failed to synchronize any subtitle tracks.")
                messagebox.showwarning("Synchronization Failed", "Failed to synchronize any subtitle tracks.")
                return
            
            # Create new MKV with corrected subtitles
            output_file = create_new_mkv(mkv_file, corrected_files)
            if output_file:
                print(f"Done! Corrected MKV saved as: {output_file}")
                messagebox.showinfo("Success", f"Done! Corrected MKV saved as:\n{output_file}")
            else:
                print("Failed to create the output MKV file.")
        
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()