"""
alass4Container - A tool that allows you to run alass directly on an MKV container, without needing to extract the SRT files. 

This script uses mkvmerge, mkvextract and alass to extract subtitles from the selected MKV file, synchronize 
them, and create a new MKV with corrected subtitles.
"""

import os
import tempfile
import subprocess
import sys
import json
import shutil
import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass

# Third-party imports
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, SpinnerColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text

# Constants
DEFAULT_SPLIT_PENALTY = 7
SUBTITLE_EXTENSIONS = {
    "ass": "ass",
    "ssa": "ass",
    "srt": "srt",
    "vobsub": "idx"
}

@dataclass
class ToolPaths:
    """Class to store paths to external tools."""
    mkvmerge: Optional[str] = None
    mkvextract: Optional[str] = None
    alass: Optional[str] = None
    
    def all_found(self) -> bool:
        """Check if all required tools were found."""
        return all([self.mkvmerge, self.mkvextract, self.alass])

@dataclass
class SubtitleTrack:
    """Class to store subtitle track information."""
    track_id: str
    language: str
    track_name: str
    codec: str
    file_path: Optional[str] = None
    corrected_path: Optional[str] = None
    
    @property
    def extension(self) -> str:
        """Determine the appropriate file extension based on codec."""
        for codec_name, ext in SUBTITLE_EXTENSIONS.items():
            if codec_name in self.codec:
                return ext
        return "srt"  # Default to SRT

@dataclass
class SyncOptions:
    """Class to store synchronization options."""
    split_penalty: Optional[float] = None
    no_splits: bool = False

class AlassContainer:
    """Main class for the alass4Container application."""
    
    def __init__(self):
        """Initialize the application."""
        self.console = Console()
        self.tools = ToolPaths()
        self.subtitle_tracks: List[SubtitleTrack] = []
        self.options = SyncOptions()
        
        # Create a root window for tkinter dialogs
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window
        
    def find_tool(self, tool_name: str) -> Optional[str]:
        """
        Find a tool in PATH or common locations.
        
        Args:
            tool_name: Name of the tool to find
            
        Returns:
            Path to the tool if found, None otherwise
        """
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
            # Base directories to check
            common_dirs = [
                os.path.expandvars("%ProgramFiles%\\MKVToolNix"),
                os.path.expandvars("%ProgramFiles(x86)%\\MKVToolNix"),
                os.path.expandvars("%LOCALAPPDATA%\\Programs\\MKVToolNix"),
                os.path.expandvars("%APPDATA%\\MKVToolNix"),
                os.path.expandvars("%USERPROFILE%\\AppData\\Local\\MKVToolNix"),
                os.path.expandvars("%USERPROFILE%\\AppData\\Roaming\\MKVToolNix"),
                os.path.join(os.getcwd(), "bin"),  # Check in a bin directory in current working directory
                os.getcwd()  # Check in current directory
            ]
            
            # Add alass-specific directories if searching for alass
            if tool_name == "alass":
                common_dirs.extend([
                    os.path.expandvars("%USERPROFILE%\\Downloads\\alass"),
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
        # I hate this so much
        # TODO: On non-Windows platforms, could add common install locations here
        
        return None
    
    def check_tools(self) -> bool:
        """
        Check if all required tools are available.
        
        Returns:
            True if all tools are found, False otherwise
        """
        missing_tools = []
        
        with self.console.status("[cyan]Checking for required tools...[/cyan]", spinner="dots"):
            # Check for mkvmerge
            self.tools.mkvmerge = self.find_tool("mkvmerge")
            if not self.tools.mkvmerge:
                missing_tools.append("mkvmerge")
            
            # Check for mkvextract
            self.tools.mkvextract = self.find_tool("mkvextract")
            if not self.tools.mkvextract:
                missing_tools.append("mkvextract")
            
            # Check for alass
            self.tools.alass = self.find_tool("alass")
            if not self.tools.alass:
                # Try alass-cli as an alternative
                self.tools.alass = self.find_tool("alass-cli")
                if not self.tools.alass:
                    missing_tools.append("alass")
        
        if missing_tools:
            missing_str = ", ".join(missing_tools)
            self.console.print(f"[bold red]Error: Required tools are missing: {missing_str}[/bold red]")
            self.console.print("[yellow]Paths searched: PATH environment variable and common installation directories.[/yellow]")
            self.console.print("[yellow]Please make sure mkvtoolnix (mkvmerge, mkvextract) and alass are installed and in your PATH.[/yellow]")
            
            messagebox.showerror(
                "Missing Tools", 
                f"The following tools are required but could not be found: {missing_str}\n\n"
                "Please make sure MKVToolNix and alass are installed and in your PATH."
            )
            
            return False
        
        # Verify the tools work by checking their version/help output
        try:
            # Get version information to display to user
            mkvmerge_version = subprocess.run(
                [self.tools.mkvmerge, "--version"], 
                capture_output=True, text=True, check=True
            ).stdout.strip().split('\n')[0]
            
            mkvextract_version = subprocess.run(
                [self.tools.mkvextract, "--version"], 
                capture_output=True, text=True, check=True
            ).stdout.strip().split('\n')[0]
            
            # Check if alass has a --version flag by checking the help output
            alass_help = subprocess.run(
                [self.tools.alass, "--help"], 
                capture_output=True, text=True
            ).stdout
            
            if "--version" in alass_help:
                alass_version = subprocess.run(
                    [self.tools.alass, "--version"], 
                    capture_output=True, text=True, check=True
                ).stdout.strip()
            else:
                alass_version = "Unknown version"
            
            # Display found tools
            self.console.print("[bold green]Required tools found:[/bold green]")
            self.console.print(f"  [cyan]•[/cyan] MKVMerge: [green]{mkvmerge_version}[/green]")
            self.console.print(f"  [cyan]•[/cyan] MKVExtract: [green]{mkvextract_version}[/green]")
            self.console.print(f"  [cyan]•[/cyan] Alass: [green]{alass_version}[/green]")
            
            return True
        except subprocess.SubprocessError as e:
            self.console.print(f"[bold red]Error running tools: {e}[/bold red]")
            messagebox.showerror(
                "Tool Verification Failed", 
                f"Found the tools, but encountered an error when trying to run them: {e}"
            )
            return False
    
    def select_mkv_file(self) -> str:
        """
        Show a file dialog to select an MKV file.
        
        Returns:
            Path to the selected file
        """
        file_path = filedialog.askopenfilename(
            title="Select MKV file",
            filetypes=[("MKV files", "*.mkv")]
        )
        if not file_path:
            self.console.print("[yellow]No file selected. Exiting.[/yellow]")
            sys.exit(0)
        return file_path
    
    def get_subtitle_tracks(self, mkv_file: str) -> List[SubtitleTrack]:
        """
        Extract subtitle track information from an MKV file.
        
        Args:
            mkv_file: Path to the MKV file
            
        Returns:
            List of SubtitleTrack objects
            
        Raises:
            SystemExit: If there's an error analyzing the MKV file
        """
        try:
            cmd = [self.tools.mkvmerge, "-J", mkv_file]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse JSON output
            info = json.loads(result.stdout)
            
            tracks = []
            
            # Extract subtitle tracks
            for track in info.get('tracks', []):
                if track.get('type') == 'subtitles':
                    track_id = track.get('id')
                    properties = track.get('properties', {})
                    language = properties.get('language', 'und')  # Default to 'und' (undefined) if no language
                    track_name = properties.get('track_name', '')
                    codec = track.get('codec', '').lower()
                    
                    if track_id is not None:
                        tracks.append(SubtitleTrack(
                            track_id=str(track_id),
                            language=language,
                            track_name=track_name,
                            codec=codec
                        ))
            
            return tracks
        except subprocess.SubprocessError as e:
            self.console.print(f"[bold red]Error running mkvmerge: {e}[/bold red]")
            messagebox.showerror("Error", f"Failed to analyze MKV file: {e}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            self.console.print(f"[bold red]Error parsing mkvmerge output: {e}[/bold red]")
            messagebox.showerror("Error", f"Failed to parse MKV information: {e}")
            sys.exit(1)
    
    def get_options(self) -> SyncOptions:
        """
        Show dialogs to get synchronization options.
        
        Returns:
            SyncOptions object with user preferences
        """
        options = SyncOptions()
        
        # Ask if the user wants to disable splits entirely first
        no_splits = messagebox.askyesno(
            "No Splits Mode",
            "Do you want to disable splits entirely?\nOnly constant time shifts will be applied.",
            parent=self.root
        )
        
        if no_splits:
            options.no_splits = True
        else:
            # Only ask about split penalty if we're not disabling splits entirely
            adjust_split = messagebox.askyesno(
                "Split Penalty",
                "Do you want to adjust the split penalty?\nDefault is 7, higher values avoid splits.",
                parent=self.root
            )
            
            if adjust_split:
                split_penalty = simpledialog.askfloat(
                    "Split Penalty Value",
                    f"Enter a value between 0 and 1000 (default is {DEFAULT_SPLIT_PENALTY}):\nHigher values make splits less likely.",
                    parent=self.root,
                    minvalue=0,
                    maxvalue=1000,
                    initialvalue=DEFAULT_SPLIT_PENALTY
                )
                
                if split_penalty is not None:
                    options.split_penalty = split_penalty
        
        return options
    
    def extract_subtitles(self, mkv_file: str, subtitle_tracks: List[SubtitleTrack], 
                         temp_dir: str) -> List[SubtitleTrack]:
        """
        Extract subtitle files from an MKV file.
        
        Args:
            mkv_file: Path to the MKV file
            subtitle_tracks: List of SubtitleTrack objects
            temp_dir: Temporary directory to store extracted files
            
        Returns:
            List of SubtitleTrack objects with file_path set
        """
        extracted_tracks = []
        
        self.console.print("\n[bold]Extracting subtitles...[/bold]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}[/bold blue]"),
            BarColumn(bar_width=None),
            TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
            TimeRemainingColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("[cyan]Extracting...[/cyan]", total=len(subtitle_tracks))
            
            for track in subtitle_tracks:
                # Skip PGS subtitles which are not supported by alass
                if "pgs" in track.codec:
                    progress.update(task, advance=1, description=f"[yellow]Skipping PGS track {track.track_id}...[/yellow]")
                    continue
                
                output_file = os.path.join(temp_dir, f"{track.track_id}.{track.language}.{track.extension}")
                
                progress.update(task, description=f"[cyan]Extracting track {track.track_id} ({track.language})...[/cyan]")
                
                try:
                    # Use mkvextract to extract the subtitle track
                    cmd = [self.tools.mkvextract, "tracks", mkv_file, f"{track.track_id}:{output_file}"]
                    subprocess.run(cmd, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                    
                    # Check if the file exists and is not empty
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        track.file_path = output_file
                        extracted_tracks.append(track)
                    else:
                        progress.update(task, description=f"[red]Failed to extract track {track.track_id}[/red]")
                except subprocess.SubprocessError as e:
                    progress.update(task, description=f"[bold red]Error on track {track.track_id}: {e}[/bold red]")
                
                progress.update(task, advance=1)
        
        return extracted_tracks
    
    def synchronize_subtitles(self, mkv_file: str, subtitle_tracks: List[SubtitleTrack], 
                             temp_dir: str, options: SyncOptions) -> List[SubtitleTrack]:
        """
        Synchronize subtitle files with the video using alass.
        
        Args:
            mkv_file: Path to the MKV file
            subtitle_tracks: List of SubtitleTrack objects with file_path set
            temp_dir: Temporary directory to store corrected files
            options: SyncOptions object with synchronization preferences
            
        Returns:
            List of SubtitleTrack objects with corrected_path set
        """
        corrected_tracks = []
        
        self.console.print("\n[bold]Synchronizing subtitles...[/bold]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}[/bold blue]"),
            BarColumn(bar_width=None),
            TextColumn("[cyan]{task.completed}/{task.total}[/cyan]"),
            TimeRemainingColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("[cyan]Synchronizing...[/cyan]", total=len(subtitle_tracks))
            
            for track in subtitle_tracks:
                # Define output file path for corrected subtitle
                corrected_file = os.path.join(temp_dir, f"{track.track_id}.{track.language}.corrected.{track.extension}")
                
                progress.update(task, description=f"[cyan]Synchronizing track {track.track_id} ({track.language})...[/cyan]")
                
                try:
                    # Build the alass command
                    cmd = [self.tools.alass]
                    
                    # Add options if specified
                    if options.split_penalty is not None:
                        cmd.extend(["--split-penalty", str(options.split_penalty)])
                    if options.no_splits:
                        cmd.append("--no-splits")
                    
                    # Add the reference, input file, and output file
                    cmd.extend([mkv_file, track.file_path, corrected_file])
                    
                    subprocess.run(cmd, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                    
                    # Check if the corrected file was created
                    if os.path.exists(corrected_file) and os.path.getsize(corrected_file) > 0:
                        track.corrected_path = corrected_file
                        corrected_tracks.append(track)
                    else:
                        progress.update(task, description=f"[red]Failed to synchronize track {track.track_id}[/red]")
                except subprocess.SubprocessError as e:
                    progress.update(task, description=f"[bold red]Error on track {track.track_id}: {e}[/bold red]")
                
                progress.update(task, advance=1)
        
        return corrected_tracks
    
    def create_new_mkv(self, mkv_file: str, subtitle_tracks: List[SubtitleTrack]) -> Optional[str]:
        """
        Create a new MKV file with the original video and corrected subtitles.
        
        Args:
            mkv_file: Path to the original MKV file
            subtitle_tracks: List of SubtitleTrack objects with corrected_path set
            
        Returns:
            Path to the new MKV file, or None if creation failed
        """
        # Generate output filename based on input file
        output_file = os.path.splitext(mkv_file)[0] + ".corrected.mkv"
        
        # Check if file already exists and warn user
        if os.path.exists(output_file):
            overwrite = messagebox.askyesno(
                "File Exists",
                f"The output file already exists:\n{output_file}\n\nDo you want to overwrite it?",
                parent=self.root
            )
            if not overwrite:
                # Let user choose a new filename
                new_output = filedialog.asksaveasfilename(
                    title="Save corrected MKV as",
                    initialfile=os.path.basename(output_file),
                    defaultextension=".mkv",
                    filetypes=[("MKV files", "*.mkv")]
                )
                if not new_output:
                    return None
                output_file = new_output
        
        try:
            # Start building the mkvmerge command to include everything except subtitles
            cmd = [self.tools.mkvmerge, "-o", output_file, "--no-subtitles", mkv_file]
            
            # Add each corrected subtitle file
            # Sort them based on original track ID to preserve order
            for track in sorted(subtitle_tracks, key=lambda x: int(x.track_id)):
                cmd_extension = ["--language", f"0:{track.language}"]
                
                # Add track name if it exists
                if track.track_name:
                    cmd_extension.extend(["--track-name", f"0:{track.track_name}"])
                
                cmd_extension.append(track.corrected_path)
                cmd.extend(cmd_extension)
            
            # Run the command
            subprocess.run(cmd, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            
            return output_file
        except subprocess.SubprocessError as e:
            self.console.print(f"[bold red]Error creating new MKV file: {e}[/bold red]")
            messagebox.showerror("Error", f"Failed to create new MKV: {e}")
            return None
    
    def display_options_panel(self, options: SyncOptions):
        """Display the selected synchronization options in a panel."""
        option_text = Text()
        option_text.append("Synchronization Options:\n", style="bold yellow")
        if options.no_splits:
            option_text.append("• No Splits Mode: ", style="bold cyan")
            option_text.append("Enabled (only constant time shifts will be applied)\n")
        elif options.split_penalty is not None:
            option_text.append("• Split Penalty: ", style="bold cyan")
            option_text.append(f"{options.split_penalty} (higher values avoid splits)\n")
        else:
            option_text.append("• Split Penalty: ", style="bold cyan")
            option_text.append(f"Default ({DEFAULT_SPLIT_PENALTY})\n")
        self.console.print(Panel(option_text, border_style="cyan"))
    
    def run(self):
        """Run the main application."""
        # Display app header
        self.console.print(Panel.fit(
            "[bold blue]alass4Container[/bold blue]",
            border_style="cyan"
        ))
        
        # Check for required tools
        if not self.check_tools():
            return 1
        
        # Select MKV file
        mkv_file = self.select_mkv_file()
        self.console.print(f"Selected: [bold green]{mkv_file}[/bold green]")
        
        # Get user options
        self.options = self.get_options()
        
        # Display options
        self.display_options_panel(self.options)
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Get subtitle tracks
                with self.console.status("[cyan]Analyzing MKV file...[/cyan]", spinner="dots"):
                    self.subtitle_tracks = self.get_subtitle_tracks(mkv_file)
                
                if not self.subtitle_tracks:
                    self.console.print("[bold red]No subtitle tracks found in the MKV file.[/bold red]")
                    messagebox.showinfo("No Subtitles", "No subtitle tracks found in the selected MKV file.")
                    return 0
                
                # Display found tracks in a nice format
                self.console.print(f"[bold green]Found {len(self.subtitle_tracks)} subtitle tracks:[/bold green]")
                for track in self.subtitle_tracks:
                    self.console.print(
                        f"  [cyan]•[/cyan] Track [bold]{track.track_id}[/bold]: "
                        f"Language=[yellow]{track.language}[/yellow], "
                        f"Name={track.track_name or 'N/A'}, "
                        f"Codec=[italic]{track.codec}[/italic]"
                    )
                
                # Extract subtitles
                extracted_tracks = self.extract_subtitles(mkv_file, self.subtitle_tracks, temp_dir)
                
                if not extracted_tracks:
                    self.console.print("[bold red]Failed to extract any subtitle tracks.[/bold red]")
                    messagebox.showwarning("Extraction Failed", "Failed to extract any subtitle tracks from the MKV file.")
                    return 1
                
                # Synchronize subtitles
                corrected_tracks = self.synchronize_subtitles(mkv_file, extracted_tracks, temp_dir, self.options)
                
                if not corrected_tracks:
                    self.console.print("[bold red]Failed to synchronize any subtitle tracks.[/bold red]")
                    messagebox.showwarning("Synchronization Failed", "Failed to synchronize any subtitle tracks.")
                    return 1
                
                # Create new MKV with corrected subtitles
                self.console.print("\n[bold]Creating new MKV with corrected subtitles...[/bold]")
                with self.console.status("[cyan]Remuxing MKV file...[/cyan]", spinner="dots"):
                    output_file = self.create_new_mkv(mkv_file, corrected_tracks)
                
                if output_file:
                    result_text = f"Done! Corrected MKV saved as:\n[bold green]{output_file}[/bold green]"
                    self.console.print(Panel(result_text, title="[bold green]Success[/bold green]", border_style="green"))
                    messagebox.showinfo("Success", f"Done! Corrected MKV saved as:\n{output_file}")
                    return 0
                else:
                    self.console.print("[bold red]Failed to create the output MKV file.[/bold red]")
                    return 1
            
            except Exception as e:
                error_msg = f"An unexpected error occurred: {e}"
                self.console.print(f"[bold red]{error_msg}[/bold red]")
                messagebox.showerror("Error", error_msg)
                return 1
        
        return 0

def main():
    """Main entry point for the application."""
    app = AlassContainer()
    return app.run()

if __name__ == "__main__":
    sys.exit(main())