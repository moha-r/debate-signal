"""Replay short, labeled audio turns through AssemblyAI's realtime API."""

import argparse
from getpass import getpass
import json
import math
import os
from pathlib import Path
from statistics import median
import sys
import time
from urllib.parse import urlencode
import wave

from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import connect

MODEL = "universal-3-6-pro"
MODELS = (MODEL, "assemblyai-stt-3-7-realtime")
ENDPOINT = "wss://streaming.assemblyai.com/v3/ws"
RATE = 16_000
FRAME_SECONDS = 0.1
FRAME_BYTES = int(RATE * FRAME_SECONDS) * 2
TAIL_SECONDS = 0.8
MAX_AUDIO_SECONDS = 120


class SessionStartLimit(RuntimeError):
    pass


def read_clip(path):
    with wave.open(str(path), "rb") as clip:
        if (clip.getnchannels(), clip.getsampwidth(), clip.getframerate()) != (1, 2, RATE):
            raise ValueError(f"{path.name} must be WAV, mono PCM16, at 16 kHz")
        frames = clip.getnframes()
        if not 0 < frames <= MAX_AUDIO_SECONDS * RATE:
            raise ValueError(f"{path.name} must contain 1–{MAX_AUDIO_SECONDS * RATE:,} samples")
        audio = clip.readframes(frames)
    if len(audio) != frames * 2:
        raise ValueError(f"{path.name} is incomplete")
    return audio


def word_errors(reference, hypothesis):
    """Compute the minimum number of word edits after shared tokenization."""
    from nlp_pipeline import tokenize

    ref, hyp = tokenize(reference), tokenize(hypothesis)
    previous = list(range(len(hyp) + 1))
    for row, expected in enumerate(ref, 1):
        current = [row]
        for col, heard in enumerate(hyp, 1):
            current.append(min(current[-1] + 1, previous[col] + 1, previous[col-1] + (expected != heard)))
        previous = current
    return previous[-1], len(ref)


def transcribe(audio, key, model=MODEL, endpoint=ENDPOINT):
    """Measure output arrival relative to the paced replay's clip endpoint."""
    query = urlencode({"sample_rate": RATE, "encoding": "pcm_s16le", "speech_model": model})
    started = time.monotonic()
    finals = {}
    last_final = None
    began = False
    terminated = False
    status = {}
    with connect(f"{endpoint}?{query}", additional_headers={"Authorization": key},
                 open_timeout=10, close_timeout=3) as connection:
        def receive(timeout):
            nonlocal last_final, began, terminated
            try:
                message = json.loads(connection.recv(timeout=timeout))
            except TimeoutError:
                return False
            if message.get("error") or message.get("type") == "Error":
                detail = str(message.get("error") or message.get("message") or "unspecified error")
                if key:
                    detail = detail.replace(key, "[redacted]")
                if not began and "too many concurrent sessions" in detail.casefold():
                    raise SessionStartLimit("AssemblyAI limited new session starts.")
                raise RuntimeError(f"AssemblyAI streaming error: {detail[:300]}")
            kind = message.get("type")
            if kind == "Begin":
                began = True
                provider_model = (message.get("configuration") or {}).get("model")
                if provider_model:
                    status["provider_model"] = provider_model
                    if provider_model != model:
                        raise RuntimeError(f"AssemblyAI began with {provider_model}, expected {model}")
            elif kind == "Turn" and message.get("end_of_turn"):
                text = message.get("transcript", "").strip()
                if text:
                    finals[int(message["turn_order"])] = text
                    last_final = time.monotonic()
            elif kind == "Termination":
                terminated = True
                status["provider_session_seconds"] = message.get("session_duration_seconds")
            return True

        def drain_until(deadline):
            while not terminated:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not receive(remaining):
                    return

        terminate_sent = False
        try:
            if not receive(8) or not began:
                raise TimeoutError("Timed out waiting for the AssemblyAI session to begin.")
            first_frame_at = time.monotonic()
            # Pad only the final partial chunk so all sent frames meet the provider's size requirement.
            frames = math.ceil(len(audio) / FRAME_BYTES)
            padded = audio.ljust(frames * FRAME_BYTES, b"\0")
            trailing = round(TAIL_SECONDS / FRAME_SECONDS)
            next_frame = first_frame_at
            for frame in range(frames + trailing):
                drain_until(next_frame)
                if terminated:
                    raise RuntimeError("AssemblyAI ended the session before the replay completed.")
                chunk = padded[frame * FRAME_BYTES:(frame + 1) * FRAME_BYTES] if frame < frames else bytes(FRAME_BYTES)
                connection.send(chunk)
                next_frame = time.monotonic() + FRAME_SECONDS
                if frame == frames - 1:
                    clip_end = next_frame - (len(padded) - len(audio)) / (2 * RATE)
            drain_until(next_frame)
            connection.send(json.dumps({"type": "Terminate"}))
            terminate_sent = True
            drain_until(time.monotonic() + 8)
        finally:
            if began and not terminate_sent and not terminated:
                try:
                    connection.send(json.dumps({"type": "Terminate"}))
                except ConnectionClosed:
                    pass
    if not terminated:
        raise TimeoutError("AssemblyAI did not confirm termination for the replay.")
    return {
        "transcript": " ".join(finals[order] for order in sorted(finals)),
        "final_turns": len(finals),
        "last_final_minus_clip_end_ms": None if last_final is None else round((last_final - clip_end) * 1000, 1),
        "session_wall_seconds": round(time.monotonic() - started, 3),
        **status,
    }


def run(manifest_path, output, key, model=MODEL):
    from moderation_session import analyze_turn, new_session
    from nlp_pipeline import preprocess_text

    manifest = json.loads(manifest_path.read_text())
    clips = []
    for row in manifest["turns"]:
        if row["speaker"] not in ("A", "B") or not preprocess_text(row["reference"]):
            raise ValueError("Each clip requires a reference transcript and speaker A or B")
        clips.append(read_clip(manifest_path.parent / row["audio"]))
    if not clips or sum(map(len, clips)) > MAX_AUDIO_SECONDS * RATE * 2:
        raise ValueError("The replay manifest must contain up to 120 seconds of audio")

    reference_state = new_session(manifest["topic"])
    asr_state = new_session(manifest["topic"])
    outputs = []
    for index, (row, audio) in enumerate(zip(manifest["turns"], clips), 1):
        try:
            result = transcribe(audio, key, model)
        except SessionStartLimit:
            print(f"Session start limit at clip {index}. Retrying that clip after one minute.", flush=True)
            time.sleep(61)
            result = transcribe(audio, key, model)
        reference_state = analyze_turn(reference_state, row["speaker"], row["reference"])
        reference_turn = reference_state["turns"][-1]
        recognized_turn = None
        if preprocess_text(result["transcript"]):
            asr_state = analyze_turn(asr_state, row["speaker"], result["transcript"])
            recognized_turn = asr_state["turns"][-1]
        edit_count, word_count = word_errors(row["reference"], result["transcript"])
        outputs.append({
            "turn": index, "speaker": row["speaker"], "reference": row["reference"],
            "word_edits": edit_count, "reference_words": word_count, **result,
            "reference_attack_alert": reference_turn["personal_attack"],
            "asr_attack_alert": recognized_turn["personal_attack"] if recognized_turn else None,
            "reference_topic_alert": reference_turn["topic"]["alert"],
            "asr_topic_alert": recognized_turn["topic"]["alert"] if recognized_turn else None,
        })
        print(f"Completed replay {index}/{len(clips)}", flush=True)
    latencies = [r["last_final_minus_clip_end_ms"] for r in outputs if r["last_final_minus_clip_end_ms"] is not None]
    words = sum(r["reference_words"] for r in outputs)
    result = {
        "model": model, "topic": manifest["topic"], "source": manifest["source"],
        "word_error_rate": sum(r["word_edits"] for r in outputs) / words if words else None,
        "turns_with_text": sum(r["asr_attack_alert"] is not None for r in outputs),
        "changed_attack_alerts": sum(r["asr_attack_alert"] is not None and r["reference_attack_alert"] != r["asr_attack_alert"] for r in outputs),
        "changed_topic_alerts": sum(r["asr_topic_alert"] is not None and r["reference_topic_alert"] != r["asr_topic_alert"] for r in outputs),
        "median_last_final_minus_clip_end_ms": median(latencies) if latencies else None,
        "turns": outputs,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".partial")
    temp.write_text(json.dumps(result, indent=2) + "\n")
    temp.replace(output)
    print(f"Saved results to {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("results/assemblyai/replay.json"))
    parser.add_argument("--model", choices=MODELS, default=MODEL)
    parser.add_argument("--prompt-key", action="store_true", help="Read the API key locally with input hidden")
    args = parser.parse_args()
    key = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
    if not key and args.prompt_key:
        if not sys.stdin.isatty():
            parser.error("Use --prompt-key in an interactive terminal.")
        key = getpass("AssemblyAI API key: ").strip()
    if not key:
        parser.error("Set ASSEMBLYAI_API_KEY or use --prompt-key in your terminal.")
    try:
        run(args.manifest, args.output, key, args.model)
    except InvalidStatus as error:
        raise SystemExit(f"AssemblyAI rejected the connection (HTTP {error.response.status_code}). Check the key and model access.") from None
    except ConnectionClosed as error:
        code = error.rcvd.code if error.rcvd else "unknown"
        raise SystemExit(f"AssemblyAI closed the replay connection (code {code}).") from None
    except (RuntimeError, TimeoutError) as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
