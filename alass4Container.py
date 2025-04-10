import os
import tempfile
import subprocess
import sys
import json
import tkinter as tk
from tkinter import filedialog, simpledialog
from pathlib import Path

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
        cmd = ["mkvmerge", "-J", mkv_file]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Parse JSON output
        info = json.loads(result.stdout)
        
        subtitle_tracks = []
        
        # Extract subtitle tracks
        for track in info.get('tracks', []):
            if track.get('type') == 'subtitles':
                track_id = track.get('id')
                properties = track.get('properties', {})
                language = properties.get('language')
                track_name = properties.get('track_name', '')
                codec = track.get('codec', '').lower()
                
                if track_id is not None and language:
                    subtitle_tracks.append((str(track_id), language, track_name, codec))
        
        return subtitle_tracks
    except subprocess.SubprocessError as e:
        print(f"Error running mkvmerge: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing mkvmerge output: {e}")
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
        
        output_file = os.path.join(temp_dir, f"{track_id}.{language}.{ext}")
        
        try:
            # Use mkvextract to extract the subtitle track
            cmd = ["mkvextract", "tracks", mkv_file, f"{track_id}:{output_file}"]
            print(f"Extracting track {track_id} ({language}, {codec})...")
            subprocess.run(cmd, check=True)
            
            # Check if the file exists and is not empty
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                extracted_files.append((track_id, language, track_name, output_file))
            else:
                print(f"Warning: Failed to extract subtitle track {track_id} ({language})")
        except subprocess.SubprocessError as e:
            print(f"Error extracting subtitle track {track_id}: {e}")
    
    return extracted_files

# Function to run alass on each subtitle file
def sync_subtitles(mkv_file, extracted_files, temp_dir, split_penalty=None, no_splits=False):
    corrected_files = []
    
    for track_id, language, track_name, subtitle_file in extracted_files:
        # Define output file path for corrected subtitle
        file_ext = os.path.splitext(subtitle_file)[1]
        corrected_file = os.path.join(temp_dir, f"{track_id}.{language}.corrected{file_ext}")
        
        try:
            # Build the alass command
            cmd = ["alass"]
            
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
        cmd = ["mkvmerge", "-o", output_file, "--no-subtitles", mkv_file]
        
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
    print("alass4Container")
    print("---------------------------------------------")
    
    # Check for required tools
    try:
        # Check for mkvmerge
        subprocess.run(["mkvmerge", "--version"], capture_output=True, check=True)
        # Check for mkvextract
        subprocess.run(["mkvextract", "--version"], capture_output=True, check=True)
        # Check for alass
        subprocess.run(["alass", "--help"], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        print("Error: Required tools are missing.")
        print("Please make sure mkvtoolnix (mkvmerge, mkvextract) and alass are installed and in your PATH.")
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
                return
            
            print(f"Found {len(subtitle_tracks)} subtitle tracks:")
            for track_id, language, track_name, codec in subtitle_tracks:
                print(f"  - Track {track_id}: Language={language}, Name={track_name or 'N/A'}, Codec={codec}")
            
            # Extract subtitles
            extracted_files = extract_subtitles(mkv_file, subtitle_tracks, temp_dir)
            if not extracted_files:
                print("Failed to extract any subtitle tracks.")
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
                return
            
            # Create new MKV with corrected subtitles
            output_file = create_new_mkv(mkv_file, corrected_files)
            if output_file:
                print(f"Done! Corrected MKV saved as: {output_file}")
            else:
                print("Failed to create the output MKV file.")
        
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()