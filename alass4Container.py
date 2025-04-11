import os
import tempfile
import subprocess
import sys
import json
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, SpinnerColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text

# Initialize Rich console
console = Console()
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
    
    with console.status("[cyan]Checking for required tools...[/cyan]", spinner="dots"):
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
        console.print(f"[bold red]Error: Required tools are missing: {missing_str}[/bold red]")
        console.print("[yellow]Paths searched: PATH environment variable and common installation directories.[/yellow]")
        console.print("[yellow]Please make sure mkvtoolnix (mkvmerge, mkvextract) and alass are installed and in your PATH.[/yellow]")
        
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
        # Get version information to display to user
        mkvmerge_version = subprocess.run([MKVMERGE_PATH, "--version"], capture_output=True, text=True, check=True).stdout.strip().split('\n')[0]
        mkvextract_version = subprocess.run([MKVEXTRACT_PATH, "--version"], capture_output=True, text=True, check=True).stdout.strip().split('\n')[0]
        alass_version = subprocess.run([ALASS_PATH, "--version"], capture_output=True, text=True, check=True).stdout.strip() if "--version" in subprocess.run([ALASS_PATH, "--help"], capture_output=True, text=True).stdout else "Unknown version"
        
        # Display found tools
        console.print("[bold green]Required tools found:[/bold green]")
        console.print(f"  [cyan]•[/cyan] MKVMerge: [green]{mkvmerge_version}[/green]")
        console.print(f"  [cyan]•[/cyan] MKVExtract: [green]{mkvextract_version}[/green]")
        console.print(f"  [cyan]•[/cyan] Alass: [green]{alass_version}[/green]")
        
        return True
    except subprocess.SubprocessError as e:
        console.print(f"[bold red]Error running tools: {e}[/bold red]")
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

# These functions have been moved into the main() function to use progress bars

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
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        
        return output_file
    except subprocess.SubprocessError as e:
        console.print(f"[bold red]Error creating new MKV file: {e}[/bold red]")
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
    
    # Ask if the user wants to disable splits entirely first
    # This is more logical as it would override any split penalty setting
    no_splits = messagebox.askyesno(
        "No Splits Mode",
        "Do you want to disable splits entirely?\nOnly constant time shifts will be applied.",
        parent=root
    )
    
    if no_splits:
        options["no_splits"] = True
    else:
        # Only ask about split penalty if we're not disabling splits entirely
        adjust_split = messagebox.askyesno(
            "Split Penalty",
            "Do you want to adjust the split penalty?\nDefault is 7, higher values avoid splits.",
            parent=root
        )
        
        if adjust_split:
            split_penalty = simpledialog.askfloat(
                "Split Penalty Value",
                "Enter a value between 0 and 1000 (default is 7):\nHigher values make splits less likely.",
                parent=root,
                minvalue=0,
                maxvalue=1000,
                initialvalue=7  # Show the default value
            )
            
            if split_penalty is not None:
                options["split_penalty"] = split_penalty
    
    root.destroy()
    return options

# Main function
def main():
    console.print(Panel.fit(
        "[bold blue]alass4Container[/bold blue]",
        border_style="cyan"
    ))
    
    # Check for required tools
    if not check_tools():
        sys.exit(1)
    
    # Select MKV file
    mkv_file = select_mkv_file()
    console.print(f"Selected: [bold green]{mkv_file}[/bold green]")
    
    # Get user options
    options = get_options()
    
    # Display options
    option_text = Text()
    option_text.append("Synchronization Options:\n", style="bold yellow")
    if options.get("no_splits"):
        option_text.append("• No Splits Mode: ", style="bold cyan")
        option_text.append("Enabled (only constant time shifts will be applied)\n")
    elif options.get("split_penalty") is not None:
        option_text.append("• Split Penalty: ", style="bold cyan")
        option_text.append(f"{options.get('split_penalty')} (higher values avoid splits)\n")
    else:
        option_text.append("• Split Penalty: ", style="bold cyan")
        option_text.append("Default (7)\n")
    console.print(Panel(option_text, border_style="cyan"))
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Get subtitle tracks
            with console.status("[cyan]Analyzing MKV file...[/cyan]", spinner="dots"):
                subtitle_tracks = get_subtitle_tracks(mkv_file)
            
            if not subtitle_tracks:
                console.print("[bold red]No subtitle tracks found in the MKV file.[/bold red]")
                messagebox.showinfo("No Subtitles", "No subtitle tracks found in the selected MKV file.")
                return
            
            # Display found tracks in a nice format
            console.print(f"[bold green]Found {len(subtitle_tracks)} subtitle tracks:[/bold green]")
            for track_id, language, track_name, codec in subtitle_tracks:
                console.print(f"  [cyan]•[/cyan] Track [bold]{track_id}[/bold]: Language=[yellow]{language}[/yellow], Name={track_name or 'N/A'}, Codec=[italic]{codec}[/italic]")
            
            # Extract subtitles with progress bar
            console.print("\n[bold]Extracting subtitles...[/bold]")
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}[/bold blue]"),
                BarColumn(bar_width=None),
                TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Extracting...[/cyan]", total=len(subtitle_tracks))
                
                extracted_files = []
                for track_id, language, track_name, codec in subtitle_tracks:
                    # Determine the appropriate extension based on codec
                    ext = "srt"
                    if "ass" in codec or "ssa" in codec:
                        ext = "ass"
                    elif "vobsub" in codec:
                        ext = "idx"
                    elif "pgs" in codec:
                        progress.update(task, advance=1, description=f"[yellow]Skipping PGS track {track_id}...[/yellow]")
                        continue
                    
                    output_file = os.path.join(temp_dir, f"{track_id}.{language}.{ext}")
                    
                    progress.update(task, description=f"[cyan]Extracting track {track_id} ({language})...[/cyan]")
                    
                    try:
                        # Use mkvextract to extract the subtitle track
                        cmd = [MKVEXTRACT_PATH, "tracks", mkv_file, f"{track_id}:{output_file}"]
                        subprocess.run(cmd, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                        
                        # Check if the file exists and is not empty
                        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                            extracted_files.append((track_id, language, track_name, output_file, ext))
                        else:
                            progress.update(task, description=f"[red]Failed to extract track {track_id}[/red]")
                    except subprocess.SubprocessError as e:
                        progress.update(task, description=f"[bold red]Error on track {track_id}[/bold red]")
                    
                    progress.update(task, advance=1)
            
            if not extracted_files:
                console.print("[bold red]Failed to extract any subtitle tracks.[/bold red]")
                messagebox.showwarning("Extraction Failed", "Failed to extract any subtitle tracks from the MKV file.")
                return
            
            # Synchronize subtitles with progress bar
            console.print("\n[bold]Synchronizing subtitles...[/bold]")
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}[/bold blue]"),
                BarColumn(bar_width=None),
                TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Synchronizing...[/cyan]", total=len(extracted_files))
                
                corrected_files = []
                for track_id, language, track_name, subtitle_file, ext in extracted_files:
                    # Define output file path for corrected subtitle
                    corrected_file = os.path.join(temp_dir, f"{track_id}.{language}.corrected.{ext}")
                    
                    progress.update(task, description=f"[cyan]Synchronizing track {track_id} ({language})...[/cyan]")
                    
                    try:
                        # Build the alass command
                        cmd = [ALASS_PATH]
                        
                        # Add options if specified
                        if options.get("split_penalty") is not None:
                            cmd.extend(["--split-penalty", str(options.get("split_penalty"))])
                        if options.get("no_splits", False):
                            cmd.append("--no-splits")
                        
                        # Add the reference, input file, and output file
                        cmd.extend([mkv_file, subtitle_file, corrected_file])
                        
                        subprocess.run(cmd, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                        
                        # Check if the corrected file was created
                        if os.path.exists(corrected_file) and os.path.getsize(corrected_file) > 0:
                            corrected_files.append((track_id, language, track_name, corrected_file))
                        else:
                            progress.update(task, description=f"[red]Failed to synchronize track {track_id}[/red]")
                    except subprocess.SubprocessError as e:
                        progress.update(task, description=f"[bold red]Error on track {track_id}[/bold red]")
                    
                    progress.update(task, advance=1)
            
            if not corrected_files:
                console.print("[bold red]Failed to synchronize any subtitle tracks.[/bold red]")
                messagebox.showwarning("Synchronization Failed", "Failed to synchronize any subtitle tracks.")
                return
            
            # Create new MKV with corrected subtitles
            console.print("\n[bold]Creating new MKV with corrected subtitles...[/bold]")
            with console.status("[cyan]Remuxing MKV file...[/cyan]", spinner="dots"):
                output_file = create_new_mkv(mkv_file, corrected_files)
            
            if output_file:
                result_text = f"Done! Corrected MKV saved as:\n[bold green]{output_file}[/bold green]"
                console.print(Panel(result_text, title="[bold green]Success[/bold green]", border_style="green"))
                messagebox.showinfo("Success", f"Done! Corrected MKV saved as:\n{output_file}")
            else:
                console.print("[bold red]Failed to create the output MKV file.[/bold red]")
        
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            console.print(f"[bold red]{error_msg}[/bold red]")
            messagebox.showerror("Error", error_msg)
            sys.exit(1)

if __name__ == "__main__":
    main()