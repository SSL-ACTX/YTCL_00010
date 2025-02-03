###############################################################$
##                    <-- YTCL_00010 -->                      ##
##                                                            ##
##    Written By: SSL-ACTX   For educational purposes only!   ##
###############################################################$
import asyncio
import aiohttp
import json
import time
import re
import argparse
import configparser
import os
from typing import Optional
from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.filesize import decimal
from youtubesearchpython import Search

# Constants and Configuration
POLLING_INTERVAL = 2
CONFIG_FILE = 'config.ini'
DOWNLOAD_DIR = "downloads"
HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'dnt': '1',
    'origin': 'https://en.loader.to',
    'priority': 'u=1, i',
    'referer': 'https://en.loader.to/',
    'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
}
FORMAT_OPTIONS = ["mp3", "1080", "720", "480", "360", "240"]


# Rich setup
custom_theme = Theme({
    "info": "bold cyan", "warning": "bold yellow", "error": "bold red",
    "success": "bold green", "url": "underline blue", "progress": "magenta", "status": "white"
})
console = Console(theme=custom_theme)


def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    if 'settings' not in config:
        config['settings'] = {'auto_download': 'false', 'auto_clear': 'false'}
    return config


def save_config(config: configparser.ConfigParser):
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)


async def _api_request(url: str, params: dict, method: str = "GET", retries: int = 3) -> Optional[dict]:
    """Handles API requests with retry logic and error handling using aiohttp."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=HEADERS, params=params) as response:
                response.raise_for_status()
                return await response.json()
    except aiohttp.ClientError as e:
        console.print(f"Error during request: {e}", style="error")
        if retries > 0:
            await asyncio.sleep(1)
            console.print(f"Retrying... (retries left: {
                          retries})", style="warning")
            return await _api_request(url, params, method, retries - 1)
        console.print("Request failed after multiple retries.", style="error")
    except json.JSONDecodeError as e:
        console.print(f"Error decoding JSON response: {e}", style="error")
    return None


async def get_download_link(youtube_url: str, format: str = "mp3") -> Optional[str]:
    """Fetches the download link for a given YouTube URL."""
    params = {'format': format, 'url': youtube_url}
    download_url = "https://p.oceansaver.in/ajax/download.php"
    data = await _api_request(download_url, params)

    if data and data.get("success") and (video_id := data.get("id")):
        return await process_download_progress(video_id)
    else:
        console.print(f"Error: Download initiation failed. Response: {
                      data}", style="error")
        return None


async def process_download_progress(video_id: str) -> Optional[str]:
    """Fetches download URL by continuously polling the progress endpoint with progress bar."""
    progress_url = "https://p.oceansaver.in/ajax/progress.php"
    params = {'id': video_id}

    with Progress(
            TextColumn("[bold blue]{task.description}[/bold blue]"),
            BarColumn(bar_width=40),
            "[progress.percentage]{task.percentage:>3.1f}%", "•",
            TimeRemainingColumn(),
            console=console
    ) as progress:
        task_id = progress.add_task("Fetching Download URL", total=1000)
        while True:
            data = await _api_request(progress_url, params)
            if not data:
                continue
            if data.get("success") == 1 and (download_url := data.get("download_url")):
                progress.update(task_id, completed=1000)
                console.print("Initializing...", style="success")
                return download_url
            elif (current_progress := data.get("progress")) is not None:
                progress_text = data.get('text', '')
                try:
                    progress.update(task_id, completed=int(current_progress),
                                    description=f"Fetching Download URL: [bold magenta]{progress_text}[/bold magenta]")
                except ValueError:
                    progress.update(task_id, description=f"Fetching Download URL: [bold magenta]{
                                    progress_text}[/bold magenta]")
            else:
                progress.update(task_id, description=f"Status: [bold]{
                                data.get('text')}[/bold]")
            await asyncio.sleep(POLLING_INTERVAL)


def sanitize_filename(title: str) -> str:
    """Sanitizes the title for use as a filename."""
    return re.sub(r'\s+', '_', re.sub(r'[^\w\s-]', '', title)).strip()


async def download_file(url: str, youtube_url: str, format: str):
    """Downloads a file from the given URL to the correct subfolder using aiohttp."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(youtube_url) as response:
                response.raise_for_status()
                text = await response.text()
            title_match = re.search(r'<title>(.*?)</title>', text)
            title = title_match.group(1).strip() if title_match else "download"
            sanitized_title = sanitize_filename(title)
            extension = ".mp3" if format == "mp3" else ".mp4"
            filename = f"{sanitized_title}{extension}"
            download_path = os.path.join(
                DOWNLOAD_DIR, "Music" if format == "mp3" else "Videos")
            os.makedirs(download_path, exist_ok=True)
            file_path = os.path.join(download_path, filename)

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                with Progress(
                    TextColumn("[bold blue]{task.description}[/bold blue]"),
                    BarColumn(),
                    "[progress.percentage]{task.percentage:>3.1f}%",
                    "•",
                    "[progress.filesize]{task.completed:.2f}MB[/progress.filesize]",
                    "/",
                    "[progress.filesize]{task.total:.2f}MB[/progress.filesize]",
                    "•",
                    TimeRemainingColumn(),
                    console=console
                ) as progress:
                    task_id = progress.add_task(
                        "Downloading", total=total_size)
                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            progress.update(task_id, advance=len(chunk))

        console.print(Panel(Text(f"Downloaded '{filename}' successfully to '{
                      download_path}'.", style="success")), style="success")

    except aiohttp.ClientError as e:
        console.print(f"Error during download: {e}", style="error")


async def search_youtube_video(query: str) -> Optional[str]:
    """Searches for a video on YouTube and returns the video URL."""
    try:
        search = Search(query, limit=1)
        result = search.result()
        if result and result['result']:
            video_data = result['result'][0]
            video_url = video_data.get('link')
            console.print(f"Found Video: {
                          video_data.get('title')}", style="info")
            return video_url
        else:
            console.print("No video found.", style="error")
            return None
    except Exception as e:
        console.print(f"Error during search: {e}", style="error")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="YouTube downloader with auto-download and clear options.")
    parser.add_argument("--auto-dl", type=str,
                        choices=['true', 'false'], help="Enable auto-download.")
    parser.add_argument("--auto-clr", type=str,
                        choices=['true', 'false'], help="Enable auto-clear terminal.")
    args = parser.parse_args()

    config = load_config()

    if args.auto_dl:
        config['settings']['auto_download'] = args.auto_dl.lower()
    if args.auto_clr:
        config['settings']['auto_clear'] = args.auto_clr.lower()
    save_config(config)

    if config['settings']['auto_clear'] == "true":
        clear_terminal()

    search_query = console.input(
        "[bold]Enter the YouTube video name or URL:[/bold] ")

    if "youtube.com" not in search_query:
        youtube_url = asyncio.run(search_youtube_video(search_query))
    else:
        youtube_url = search_query

    if not youtube_url:
        console.print("Invalid YouTube URL or Search Query", style="error")
        return

    format_choice = console.input(
        f"[bold]Enter the desired format[/bold] ({
            ', '.join(FORMAT_OPTIONS)}): "
    ).lower()

    if format_choice not in FORMAT_OPTIONS:
        console.print(f"Invalid format. Choose one of: {
            ', '.join(FORMAT_OPTIONS)}.", style="error")
        return

    download_link = asyncio.run(get_download_link(
        youtube_url, format=format_choice))

    if download_link:
        if config['settings']['auto_download'] == "true":
            asyncio.run(download_file(download_link,
                        youtube_url, format_choice))
        else:
            console.print(
                Panel(Text(f"Download URL: {download_link}", style="url")), style="info")


if __name__ == "__main__":
    main()
