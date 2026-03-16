"""
title: ExifTool Metadata Extractor
author: openclaw-intel
version: 0.1.0
description: Runs ExifTool to extract metadata from images and documents — GPS coordinates, camera info, software, timestamps, author data.
"""

import subprocess
import asyncio
from pydantic import BaseModel, Field
from typing import Optional


class Tools:
    class Valves(BaseModel):
        timeout: int = Field(
            default=30,
            description="Maximum execution time in seconds.",
        )
        wsl_distro: str = Field(
            default="kali-linux",
            description="WSL distribution name where ExifTool is installed.",
        )
        max_output_lines: int = Field(
            default=300,
            description="Maximum output lines to return.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def exiftool_extract(
        self,
        file_path: str,
        gps_only: Optional[bool] = False,
        __event_emitter__=None,
    ) -> str:
        """
        Extract all metadata from a file using ExifTool.
        Works on images (JPG, PNG, TIFF, RAW), documents (PDF, DOCX), videos (MP4, MOV), and more.
        Extracts GPS coordinates, camera model, software used, creation dates, author info, and embedded data.

        :param file_path: Path to the file to analyze. Use WSL-accessible paths (e.g., /mnt/c/Users/... or /home/...).
        :param gps_only: If true, only extract GPS/location related metadata.
        :return: All extracted metadata fields and values.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Extracting metadata from {file_path}...",
                        "done": False,
                    },
                }
            )

        if gps_only:
            cmd_str = f'exiftool -gps* -GPSPosition -GPSLatitude -GPSLongitude -GPSAltitude -GPSDateTime "{file_path}"'
        else:
            cmd_str = f'exiftool -a -u -g1 "{file_path}"'

        wsl_cmd = f'wsl -d {self.valves.wsl_distro} -- bash -c \'{cmd_str}\''

        try:
            process = await asyncio.create_subprocess_shell(
                wsl_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.valves.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"ERROR: ExifTool timed out after {self.valves.timeout}s.\nFile: {file_path}"

            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")

            lines = output.strip().split("\n")
            if len(lines) > self.valves.max_output_lines:
                output = "\n".join(lines[: self.valves.max_output_lines])
                output += f"\n\n[TRUNCATED — {len(lines)} total lines]"

            result = f"TOOL: ExifTool\nFILE: {file_path}\nMODE: {'GPS Only' if gps_only else 'Full Extraction'}\n{'=' * 60}\n\n{output}"

            if err_output.strip() and process.returncode != 0:
                result += f"\n\nSTDERR:\n{err_output.strip()}"

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Metadata extraction complete.",
                            "done": True,
                        },
                    }
                )

            return result

        except Exception as e:
            return f"ERROR: Failed to run ExifTool.\nFile: {file_path}\nException: {str(e)}"

    async def exiftool_batch(
        self,
        directory_path: str,
        file_extension: Optional[str] = "jpg",
        __event_emitter__=None,
    ) -> str:
        """
        Extract metadata from all files of a given type in a directory.
        Useful for batch analysis of image dumps or document collections.

        :param directory_path: Path to directory containing files to analyze.
        :param file_extension: File extension to filter (e.g., jpg, png, pdf, docx).
        :return: Summary metadata for all matching files.
        """
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Batch extracting metadata from {directory_path}/*.{file_extension}...",
                        "done": False,
                    },
                }
            )

        cmd_str = f'exiftool -r -ext {file_extension} -csv "{directory_path}"'
        wsl_cmd = f'wsl -d {self.valves.wsl_distro} -- bash -c \'{cmd_str}\''

        try:
            process = await asyncio.create_subprocess_shell(
                wsl_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.valves.timeout * 3
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"ERROR: Batch ExifTool timed out.\nDirectory: {directory_path}"

            output = stdout.decode("utf-8", errors="replace")

            lines = output.strip().split("\n")
            file_count = max(0, len(lines) - 1)

            if len(lines) > self.valves.max_output_lines:
                output = "\n".join(lines[: self.valves.max_output_lines])
                output += f"\n\n[TRUNCATED — {len(lines)} total lines]"

            result = f"TOOL: ExifTool Batch\nDIRECTORY: {directory_path}\nEXTENSION: {file_extension}\nFILES PROCESSED: {file_count}\n{'=' * 60}\n\n{output}"

            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": f"Batch extraction complete — {file_count} files processed.",
                            "done": True,
                        },
                    }
                )

            return result

        except Exception as e:
            return f"ERROR: Failed batch ExifTool.\nDirectory: {directory_path}\nException: {str(e)}"
