"""Relay live PCM to AssemblyAI and commit finalized turns to the moderator."""

import asyncio
from contextlib import suppress
import json
import os
from time import monotonic
from urllib.parse import urlencode
from uuid import uuid4
from conversation_insights import voice_timing

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

MODEL = "assemblyai-stt-3-7-realtime"
ENDPOINT = "wss://streaming.assemblyai.com/v3/ws"
FRAME_BYTES = 3200  # 100 ms of mono PCM16 at 16 kHz
START_TIMEOUT = 12
IDLE_TIMEOUT = 60
MAX_VOICE_SECONDS = int(os.getenv('MAX_VOICE_SECONDS','900'))
if not 1 <= MAX_VOICE_SECONDS <= 3600:
    raise ValueError('MAX_VOICE_SECONDS must be between 1 and 3600.')
VOICE_UNAVAILABLE = "Recording is currently unavailable. Contact the site administrator."


def server_voice_key():
    key = os.getenv("ASSEMBLYAI_API_KEY", "").strip()
    return key if key.isascii() and not any(character.isspace() for character in key) else ""


def has_voice_key():
    return bool(server_voice_key())


class VoiceError(Exception):
    pass


def labeled_speaker(label):
    return label if label in ("A", "B") else "Unknown"


def provider_message(raw):
    try:
        message = json.loads(raw)
    except (TypeError, ValueError):
        raise VoiceError("AssemblyAI returned an unreadable response.") from None
    if not isinstance(message, dict):
        raise VoiceError("AssemblyAI returned an unreadable response.")
    if message.get("type") == "Error" or message.get("error"):
        detail = str(message.get("error") or message.get("message", "")).casefold()
        if "too many concurrent sessions" in detail:
            raise VoiceError("AssemblyAI is limiting new sessions. Wait one minute before reconnecting.")
        if any(term in detail for term in ("insufficient", "balance", "unauthorized", "invalid api")):
            raise VoiceError(VOICE_UNAVAILABLE)
        raise VoiceError("AssemblyAI could not continue transcription. Reconnect to try again.")
    return message


def command(message):
    try:
        data = json.loads(message.get("text") or "")
    except ValueError:
        raise VoiceError("The voice connection received an invalid command.") from None
    if not isinstance(data, dict):
        raise VoiceError("The voice connection received an invalid command.")
    return data


async def serve_voice(socket: WebSocket, commit_turn, *, endpoint=ENDPOINT, max_duration_seconds=MAX_VOICE_SECONDS):
    """Send continuous audio and add each finalized provider turn once."""
    upstream_task = None
    browser_task = None
    draft = ""
    recording_id = str(uuid4())
    try:
        first = await asyncio.wait_for(socket.receive(), START_TIMEOUT)
        if first["type"] == "websocket.disconnect":
            return
        hello = command(first)
        if hello.get("type") != "connect":
            raise VoiceError("Reconnect to set up the voice session.")
        key = server_voice_key()
        if not key:
            raise VoiceError(VOICE_UNAVAILABLE)
        params = urlencode({
            "speech_model": MODEL, "sample_rate": 16000, "encoding": "pcm_s16le",
            "language_codes": json.dumps(["en"]), "mode": "balanced",
            "speaker_labels": "true", "max_speakers": 2,
            "filter_profanity": "false", "inactivity_timeout": IDLE_TIMEOUT,
        })
        async with connect(f"{endpoint}?{params}", additional_headers={"Authorization": key},
                           open_timeout=START_TIMEOUT, close_timeout=2, max_size=262144) as upstream:
            stopping = False
            try:
                begin = provider_message(await asyncio.wait_for(upstream.recv(), START_TIMEOUT))
                configuration = begin.get("configuration") or {}
                if begin.get("type") != "Begin" or configuration.get("model") != MODEL:
                    raise VoiceError("AssemblyAI did not confirm the requested voice model.")
                if configuration.get("speaker_labels") is not True:
                    raise VoiceError("AssemblyAI did not enable automatic speaker detection.")
                await socket.send_json({"type": "ready", "model": MODEL, 'max_duration_seconds':max_duration_seconds})

                last_final = -1
                saved = 0
                deadline = monotonic() + IDLE_TIMEOUT
                recording_deadline=monotonic()+max_duration_seconds
                stop_reason=None
                browser_task = asyncio.create_task(socket.receive())
                upstream_task = asyncio.create_task(upstream.recv())
                while True:
                    if stopping and monotonic()>=deadline:
                        raise VoiceError('The final audio did not finish processing. Check the transcript.')
                    if not stopping and monotonic()>=recording_deadline:
                        await upstream.send(json.dumps({'type':'ForceEndpoint'}))
                        await upstream.send(json.dumps({'type':'Terminate'}))
                        stopping=True;stop_reason='duration_limit';deadline=monotonic()+10
                    done, _ = await asyncio.wait(
                        (browser_task, upstream_task), timeout=max(0, (deadline if stopping else min(deadline,recording_deadline)) - monotonic()),
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        if not stopping and monotonic()>=recording_deadline: continue
                        if stopping:
                            raise VoiceError("The final audio did not finish processing. Check the transcript.")
                        raise VoiceError("Voice session ended after a minute without audio. Start again when ready.")

                    if upstream_task in done:
                        event = provider_message(upstream_task.result())
                        kind = event.get("type")
                        if kind == "Termination":
                            if not stopping:
                                raise VoiceError("AssemblyAI ended the voice session. Start again to continue.")
                            await socket.send_json({"type": "stopped", "count": saved, "draft": draft,'reason':stop_reason})
                            return
                        if kind == "Turn":
                            order = event.get("turn_order")
                            transcript = event.get("transcript")
                            if isinstance(order, int) and order > last_final and isinstance(transcript, str):
                                draft = transcript.strip()
                                if event.get("end_of_turn") is True:
                                    last_final = order
                                    if draft:
                                        speaker = labeled_speaker(event.get("speaker_label"))
                                        if len(draft) > 4000:
                                            raise VoiceError("A speaking turn exceeded the transcript limit. Review the recovered draft.")
                                        try:
                                            state = await asyncio.to_thread(commit_turn, speaker, draft, voice_timing(event, recording_id))
                                        except HTTPException as error:
                                            raise VoiceError(str(error.detail)) from None
                                        saved += 1
                                        await socket.send_json({"type": "turn_added", "session": state,
                                                                "speaker": speaker, "text": draft})
                                    draft = ""
                                else:
                                    await socket.send_json({"type": "transcript", "text": draft})
                        upstream_task = asyncio.create_task(upstream.recv())

                    if browser_task in done:
                        message = browser_task.result()
                        if message["type"] == "websocket.disconnect":
                            return
                        pcm = message.get("bytes")
                        if stopping and (pcm is not None or command(message).get('type')=='stop'):
                            browser_task=asyncio.create_task(socket.receive())
                            continue
                        if pcm is not None and not stopping and len(pcm) == FRAME_BYTES:
                            await upstream.send(pcm)
                            deadline = monotonic() + IDLE_TIMEOUT
                        elif pcm is None and not stopping and command(message).get("type") == "stop":
                            # Binary frames and this command arrive in order. Final turns arrive before Termination.
                            await upstream.send(json.dumps({"type": "ForceEndpoint"}))
                            await upstream.send(json.dumps({"type": "Terminate"}))
                            stopping = True
                            deadline = monotonic() + 10
                        else:
                            raise VoiceError("The microphone sent an unexpected message. Start again to continue.")
                        browser_task = asyncio.create_task(socket.receive())
            finally:
                tasks = [task for task in (upstream_task, browser_task) if task]
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                if not stopping:
                    with suppress(ConnectionClosed, TimeoutError):
                        await asyncio.wait_for(upstream.send(json.dumps({"type": "Terminate"})), 2)
    except WebSocketDisconnect:
        return
    except (VoiceError, InvalidStatus, ConnectionClosed, TimeoutError, OSError) as error:
        if isinstance(error, VoiceError):
            message = str(error)
        elif isinstance(error, InvalidStatus) and error.response.status_code in (401, 403):
            message = VOICE_UNAVAILABLE
        else:
            message = "The connection to AssemblyAI ended. Start again to continue."
        with suppress(WebSocketDisconnect, RuntimeError, OSError):
            await socket.send_json({"type": "error", "message": message, "draft": draft[:4000]})
    finally:
        with suppress(WebSocketDisconnect, RuntimeError, OSError):
            await socket.close()
