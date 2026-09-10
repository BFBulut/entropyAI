#!/usr/bin/env python3
"""Google Flow Video & Image Automation Engine.

Provides an end-to-end Python interface and CLI wrapper for orchestrating
Google Flow (labs.google/fx/tools/flow), supporting Veo models, Omni Flash,
and Imagen with automated session handling, project management, and video generation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


SUPPORTED_VIDEO_MODELS = {
    "omni-flash": {
        "full_name": "omni_flash",
        "max_duration": 10,
        "ref_cap": 7,
        "description": "Google Flow Omni Flash high-speed video synthesis",
    },
    "veo-lite": {
        "full_name": "veo_3_1_lite",
        "max_duration": 8,
        "ref_cap": 3,
        "description": "Veo 3.1 Lite iteration model",
    },
    "veo-fast": {
        "full_name": "veo_3_1_fast",
        "max_duration": 8,
        "ref_cap": 3,
        "description": "Veo 3.1 Fast balanced model",
    },
    "veo-quality": {
        "full_name": "veo_3_1_quality",
        "max_duration": 8,
        "ref_cap": 0,
        "description": "Veo 3.1 Quality maximum fidelity",
    },
}

SUPPORTED_ASPECT_RATIOS = ["16:9", "9:16"]


@dataclass
class FlowGenerationResult:
    status: str
    prompt: str
    model: str
    duration: int
    aspect: str
    project: Optional[str]
    output_path: Optional[str]
    media_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GoogleFlowAutomation:
    """Automates Google Flow interactions through gflow-cli or CDP bridge."""

    def __init__(self, cli_path: str = "gflow") -> None:
        self.cli_path = cli_path

    def check_cli_available(self) -> bool:
        """Verify if gflow executable is available in PATH."""
        return shutil.which(self.cli_path) is not None

    def check_auth_status(self) -> Dict[str, Any]:
        """Check if a verified Google Flow session exists."""
        if not self.check_cli_available():
            return {
                "authenticated": False,
                "error": "gflow CLI not found in PATH",
                "details": None,
            }

        try:
            res = subprocess.run(
                [self.cli_path, "auth", "status"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = (res.stdout + "\n" + res.stderr).strip()
            is_authenticated = "verified" in output.lower() and res.returncode == 0
            return {
                "authenticated": is_authenticated,
                "output": output,
                "return_code": res.returncode,
            }
        except Exception as exc:
            return {
                "authenticated": False,
                "error": str(exc),
                "details": None,
            }

    def validate_generation_params(
        self,
        prompt: str,
        model: str,
        duration: int,
        aspect: str,
    ) -> None:
        """Validate generation parameters against Google Flow constraints."""
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        if model not in SUPPORTED_VIDEO_MODELS:
            supported = ", ".join(SUPPORTED_VIDEO_MODELS.keys())
            raise ValueError(f"Unsupported model '{model}'. Supported models: {supported}")

        model_spec = SUPPORTED_VIDEO_MODELS[model]
        max_dur = model_spec["max_duration"]
        if duration > max_dur or duration < 4:
            raise ValueError(
                f"Invalid duration {duration}s for model '{model}'. "
                f"Must be between 4 and {max_dur} seconds."
            )

        if aspect not in SUPPORTED_ASPECT_RATIOS:
            supported_aspects = ", ".join(SUPPORTED_ASPECT_RATIOS)
            raise ValueError(
                f"Unsupported aspect ratio '{aspect}'. Supported: {supported_aspects}"
            )

    @staticmethod
    def format_dialogue_prompt(
        scene_visual_prompt: str,
        dialogue: str,
        language: str = "Turkish",
        sfx: Optional[str] = None,
        ambient: Optional[str] = None,
    ) -> str:
        """Format a prompt with structured dialogue and audio layers for Veo/Omni Flash.
        
        Ensures quotes and language directives are properly formatted for native
        lip-sync and speech synthesis in Google Flow.
        """
        parts = [scene_visual_prompt.strip()]
        parts.append(
            f"The character speaks fluent {language} with expressive comedic facial expressions and synced lip movements."
        )
        # Strip existing quotes if any
        clean_dialogue = dialogue.strip().strip('"').strip("'")
        parts.append(f'Dialogue: "{clean_dialogue}"')
        
        if sfx:
            parts.append(f"Audio SFX: {sfx.strip()}")
        if ambient:
            parts.append(f"Audio Ambient: {ambient.strip()}")
            
        return " ".join(parts)

    def build_generation_command(
        self,
        prompt: str,
        model: str = "omni-flash",
        duration: int = 10,
        aspect: str = "16:9",
        project_title: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> List[str]:
        """Build the command line arguments for gflow video t2v."""
        self.validate_generation_params(prompt, model, duration, aspect)

        cmd = [
            self.cli_path,
            "video",
            "t2v",
            prompt,
            "--model",
            model,
            "--aspect",
            aspect,
            "--duration",
            str(duration),
        ]

        if project_title:
            cmd.extend(["--project-title", project_title])

        if output_path:
            cmd.extend(["-o", str(output_path)])

        return cmd

    def generate_video(
        self,
        prompt: str,
        model: str = "omni-flash",
        duration: int = 10,
        aspect: str = "16:9",
        project_title: Optional[str] = "Empty Studio Project",
        output_path: Optional[str] = None,
        timeout: int = 600,
    ) -> FlowGenerationResult:
        """Execute text-to-video generation using Google Flow."""
        self.validate_generation_params(prompt, model, duration, aspect)

        # Check authentication first
        auth = self.check_auth_status()
        if not auth["authenticated"]:
            return FlowGenerationResult(
                status="auth_required",
                prompt=prompt,
                model=model,
                duration=duration,
                aspect=aspect,
                project=project_title,
                output_path=output_path,
                error=(
                    "Google Flow session not authenticated. "
                    "Run 'gflow auth login' to establish a real Chrome session."
                ),
            )

        cmd = self.build_generation_command(
            prompt=prompt,
            model=model,
            duration=duration,
            aspect=aspect,
            project_title=project_title,
            output_path=output_path,
        )

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = res.stdout + "\n" + res.stderr
            if res.returncode == 0:
                return FlowGenerationResult(
                    status="success",
                    prompt=prompt,
                    model=model,
                    duration=duration,
                    aspect=aspect,
                    project=project_title,
                    output_path=output_path,
                )
            else:
                return FlowGenerationResult(
                    status="failed",
                    prompt=prompt,
                    model=model,
                    duration=duration,
                    aspect=aspect,
                    project=project_title,
                    output_path=output_path,
                    error=output.strip(),
                )
        except subprocess.TimeoutExpired:
            return FlowGenerationResult(
                status="timeout",
                prompt=prompt,
                model=model,
                duration=duration,
                aspect=aspect,
                project=project_title,
                output_path=output_path,
                error=f"Generation timed out after {timeout} seconds",
            )
        except Exception as exc:
            return FlowGenerationResult(
                status="error",
                prompt=prompt,
                model=model,
                duration=duration,
                aspect=aspect,
                project=project_title,
                output_path=output_path,
                error=str(exc),
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Flow Omni Flash & Veo Video Generation Engine"
    )
    parser.add_argument("--prompt", type=str, required=False, default=None, help="Video generation prompt")
    parser.add_argument(
        "--model",
        type=str,
        default="omni-flash",
        choices=list(SUPPORTED_VIDEO_MODELS.keys()),
        help="Google Flow video model (default: omni-flash)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Video duration in seconds (omni-flash supports up to 10s)",
    )
    parser.add_argument(
        "--aspect",
        type=str,
        default="16:9",
        choices=SUPPORTED_ASPECT_RATIOS,
        help="Video aspect ratio (default: 16:9)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="Empty Studio Project",
        help="Google Flow Project Title",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./output_video.mp4",
        help="Output video destination path (.mp4)",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Check authentication status and exit",
    )

    args = parser.parse_args()

    engine = GoogleFlowAutomation()

    if args.check_auth:
        status = engine.check_auth_status()
        print(json.dumps(status, indent=2))
        sys.exit(0 if status["authenticated"] else 1)

    if not args.prompt:
        parser.error("--prompt is required for video generation")

    result = engine.generate_video(
        prompt=args.prompt,
        model=args.model,
        duration=args.duration,
        aspect=args.aspect,
        project_title=args.project,
        output_path=args.output,
    )

    print(json.dumps(result.to_dict(), indent=2))
    sys.exit(0 if result.status == "success" else 1)


if __name__ == "__main__":
    main()
