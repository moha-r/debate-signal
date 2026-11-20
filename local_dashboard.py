"""Serve the local debate dashboard and its in-memory moderation sessions."""

from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from moderation_session import analyze_turn, correct_voice_speaker, new_session, review_alert
from voice_gateway import has_voice_key, serve_voice
from conversation_insights import apply_feedback, correct_argument, session_insights
from session_store import SessionStore, SessionConflict, feedback_records
from fastapi.responses import Response, FileResponse, RedirectResponse, JSONResponse
from fastapi.requests import HTTPConnection
from auth_store import AuthStore, AuthError, COOKIE_NAME, REMEMBER_SECONDS
import json
import os

MAX_CONCURRENT_VOICE = int(os.getenv('MAX_CONCURRENT_VOICE','2'))
if not 1 <= MAX_CONCURRENT_VOICE <= 8:
    raise ValueError('MAX_CONCURRENT_VOICE must be between 1 and 8.')

app = FastAPI(title="Moderator workspace", docs_url=None, redoc_url=None, openapi_url=None)
sessions = OrderedDict()
lock = Lock()
voice_sessions = set()
voice_owners = {}
store = SessionStore()
auth_store = AuthStore(store.path)
example_topic = "Should schools require students to wear uniforms?"
example_turns = (
    ("A", "School uniforms can reduce pressure to buy expensive clothes."),
    ("B", "I disagree because a uniform can cost more than clothes families already own."),
    ("A", "Schools could make uniforms optional for families who cannot afford them."),
    ("B", "You are a stupid idiot."),
    ("A", "The uniform policy could protect families from unexpected costs."),
    ("B", "My neighbour is learning to play the saxophone."),
    ("A", "The saxophone in his band needs a new mouthpiece."),
)


class SessionInput(BaseModel):
    topic: str = Field(default=example_topic, max_length=300)
    example: bool = False
    participants: dict[Literal['A','B'], str] = Field(default_factory=dict)


class TurnInput(BaseModel):
    speaker: Literal["A", "B"]
    text: str = Field(min_length=1, max_length=4000)
    revision: int = Field(ge=0)


class ReviewInput(BaseModel):
    decision: Literal["Reviewed", "Dismissed"]
    revision: int = Field(ge=0)


class SpeakerInput(BaseModel):
    speaker: Literal["A", "B"]


class ArgumentInput(BaseModel):
    role: Literal['claim','reason','rebuttal','question','agreement','unclassified']
    target: int | None = Field(default=None,ge=1)
    relation: Literal['support','attack','answers'] | None = None
    reason: str = Field(default='',max_length=1000)
    revision: int = Field(ge=0)


class FeedbackInput(BaseModel):
    verdict: Literal['correct', 'incorrect']
    reason: str = Field(default='', max_length=1000)
    revision: int = Field(ge=0)


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    remember: bool = True


class RegisterInput(LoginInput):
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)


def current_user(connection: HTTPConnection):
    user = auth_store.user_for_token(connection.cookies.get(COOKIE_NAME))
    if not user:
        raise HTTPException(401, 'Sign in to open your workspace.')
    return user


def public_origin(connection: HTTPConnection):
    """Use a configured external origin when TLS terminates at a trusted proxy."""
    configured=os.getenv('PUBLIC_ORIGIN','').strip().rstrip('/')
    if configured:
        parsed=urlsplit(configured)
        if (parsed.scheme not in ('http','https') or not parsed.netloc or parsed.path
                or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise RuntimeError('PUBLIC_ORIGIN must be an http(s) origin without a path or credentials.')
        return configured
    scheme='https' if connection.scope.get('scheme') in ('https','wss') else 'http'
    return f'{scheme}://{connection.url.netloc}'


@app.middleware('http')
async def protect_account_requests(request: Request, call_next):
    if request.url.path.startswith('/api/'):
        if request.method in ('POST','PUT','PATCH','DELETE'):
            origin = request.headers.get('origin')
            if origin and origin != public_origin(request):
                return JSONResponse({'detail':'This request must come from your workspace.'},status_code=403)
            if request.headers.get('sec-fetch-site') == 'cross-site':
                return JSONResponse({'detail':'Cross-site requests are not allowed.'},status_code=403)
            if request.url.path in ('/api/auth/register','/api/auth/login') and request.headers.get('content-type','').split(';')[0] != 'application/json':
                return JSONResponse({'detail':'Send account details as JSON.'},status_code=415)
        response = await call_next(request)
        response.headers['Cache-Control']='no-store'
        return response
    return await call_next(request)


def signed_in_response(user, request, remember, status=200):
    previous=request.cookies.get(COOKIE_NAME)
    auth_store.revoke(previous)
    token=auth_store.issue_session(user['id'],remember)
    response=JSONResponse({'user':user},status_code=status)
    response.set_cookie(COOKIE_NAME,token,httponly=True,samesite='lax',secure=public_origin(request).startswith('https://'),
                        max_age=REMEMBER_SECONDS if remember else None,path='/')
    return response


@app.get('/api/auth/me')
def account_status(request: Request):
    return {'user':auth_store.user_for_token(request.cookies.get(COOKIE_NAME)),
            'setup_required':auth_store.setup_required()}


@app.post('/api/auth/register',status_code=201)
def register_account(body: RegisterInput, request: Request):
    try:
        user=auth_store.register(body.name,body.email,body.password)
        return signed_in_response(user,request,body.remember,201)
    except AuthError as error:
        raise HTTPException(error.status,str(error)) from error


@app.post('/api/auth/login')
def login_account(body: LoginInput, request: Request):
    try:
        user=auth_store.authenticate(body.email,body.password,request.client.host if request.client else 'local')
        return signed_in_response(user,request,body.remember)
    except AuthError as error:
        raise HTTPException(error.status,str(error)) from error


@app.post('/api/auth/logout')
def logout_account(request: Request):
    auth_store.revoke(request.cookies.get(COOKIE_NAME))
    response=JSONResponse({'user':None})
    response.delete_cookie(COOKIE_NAME,path='/')
    return response


def snapshot(state):
    return {**{key: value for key, value in state.items() if key not in ("monitor",'owner_id')},
            'insights': session_insights(state)}


def retain(state, expected_revision=None):
    try:
        store.save(state,expected_revision=expected_revision)
    except SessionConflict as error:
        sessions.pop(state['id'],None)
        raise HTTPException(409,'This session changed. Refresh its state and try again.') from error
    sessions[state['id']] = state
    if len(sessions) > 64:
        # Active voice sessions must never be evicted mid-recording.
        victim = next((key for key in sessions if key not in voice_sessions), None)
        if victim is not None:
            sessions.pop(victim)


def session_at(session_id, revision=None, owner_id=None):
    # SQLite is authoritative; another process may have advanced the revision.
    state = store.load(session_id)
    if state is None or (owner_id is not None and state.get('owner_id') != owner_id):
        raise HTTPException(404, "This session has expired. Start a new session.")
    if revision is not None and state["revision"] != revision:
        raise HTTPException(409, "This session changed. Refresh its state and try again.")
    sessions[session_id] = state
    sessions.move_to_end(session_id)
    return state


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/sessions", status_code=201)
def create_session(request: SessionInput, user=Depends(current_user)):
    with lock:
        try:
            state = new_session(example_topic if request.example else request.topic)
            if request.example:
                for speaker, text in example_turns:
                    state = analyze_turn(state, speaker, text)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        state["revision"] = 0
        state['owner_id']=user['id']
        state['participants'] = {s: str(request.participants.get(s, f'Speaker {s}')).strip()[:80] or f'Speaker {s}' for s in ('A','B')}
        state['example'] = request.example
        retain(state)
        return snapshot(state)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: UUID, user=Depends(current_user)):
    with lock:
        return snapshot(session_at(str(session_id),owner_id=user['id']))


@app.get('/api/sessions')
def list_sessions(user=Depends(current_user)):
    with lock:
        return [snapshot(state) for state in store.list(user['id'])]


@app.post("/api/sessions/{session_id}/turns")
def add_turn(session_id: UUID, request: TurnInput, user=Depends(current_user)):
    return save_turn(str(session_id), request.speaker, request.text, request.revision,owner_id=user['id'])


def save_turn(key, speaker, text, revision=None, source="text", timing=None, owner_id=None):
    with lock:
        state = session_at(key, revision,owner_id)
        if len(state["turns"]) >= 250:
            raise HTTPException(422, "Export this transcript and start a new session to continue.")
        try:
            updated = analyze_turn(state, speaker, text)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        updated["turns"][-1]["source"] = source
        if timing is not None:
            updated['turns'][-1]['voice_timing'] = timing
        updated["revision"] = state["revision"] + 1
        retain(updated,expected_revision=state['revision'])
        return snapshot(updated)


@app.patch("/api/sessions/{session_id}/turns/{number}/speaker")
def correct_speaker(session_id: UUID, number: int, request: SpeakerInput, user=Depends(current_user)):
    key = str(session_id)
    with lock:
        state = session_at(key,owner_id=user['id'])
        try:
            updated = correct_voice_speaker(state, number, request.speaker)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        updated["revision"] = state["revision"] + 1
        retain(updated,expected_revision=state['revision'])
        return snapshot(updated)


@app.patch("/api/sessions/{session_id}/alerts/{alert_id}")
def update_alert(session_id: UUID, alert_id: str, request: ReviewInput, user=Depends(current_user)):
    key = str(session_id)
    with lock:
        state = session_at(key, request.revision,user['id'])
        try:
            updated = review_alert(state, alert_id, request.decision)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        updated["revision"] = state["revision"] + 1
        retain(updated,expected_revision=state['revision'])
        return snapshot(updated)


@app.patch('/api/sessions/{session_id}/turns/{number}/argument')
def annotate_argument(session_id: UUID, number: int, request: ArgumentInput, user=Depends(current_user)):
    with lock:
        state=session_at(str(session_id),request.revision,user['id'])
        try:
            updated=correct_argument(state,number,request.role,request.target,request.relation,request.reason)
        except ValueError as error:
            raise HTTPException(422,str(error)) from error
        updated['revision']=state['revision']+1
        retain(updated,expected_revision=state['revision'])
        return snapshot(updated)


@app.patch('/api/sessions/{session_id}/alerts/{alert_id}/feedback')
def label_alert(session_id: UUID, alert_id: str, request: FeedbackInput, user=Depends(current_user)):
    with lock:
        state = session_at(str(session_id), request.revision,user['id'])
        try:
            updated = apply_feedback(state, alert_id, request.verdict, request.reason)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        updated['revision'] = state['revision'] + 1
        retain(updated,expected_revision=state['revision'])
        return snapshot(updated)


@app.get('/api/sessions/{session_id}/feedback')
def export_feedback(session_id: UUID, user=Depends(current_user)):
    with lock:
        records = feedback_records(session_at(str(session_id),owner_id=user['id']))
        return Response(''.join(json.dumps(row) + '\n' for row in records), media_type='application/x-ndjson',
                        headers={'Content-Disposition': 'attachment; filename="moderator-feedback.jsonl"'})


@app.get("/api/voice/config")
def voice_config(user=Depends(current_user)):
    return {"configured": has_voice_key()}


@app.websocket("/api/sessions/{session_id}/voice")
async def voice(socket: WebSocket, session_id: UUID):
    origin = socket.headers.get("origin", "")
    # Exact origin validation also applies to HTTPS/WSS and the configured public host.
    if origin != public_origin(socket):
        await socket.close(code=1008)
        return
    key = str(session_id)
    token=socket.cookies.get(COOKIE_NAME)
    user=auth_store.user_for_token(token)
    if not user:
        await socket.close(code=1008)
        return
    with lock:
        try:
            session_at(key,owner_id=user['id'])
            exists = True
        except HTTPException:
            exists = False
        message=None
        if exists:
            if key in voice_sessions:
                message='This session already has an open voice connection.'
            elif user['id'] in voice_owners.values():
                message='Use one recording at a time per moderator. Stop your other recording first.'
            elif len(voice_sessions)>=MAX_CONCURRENT_VOICE:
                message='All recording slots are in use. Try again after another recording ends.'
            else:
                voice_sessions.add(key)
                voice_owners[key]=user['id']
    if not exists:
        await socket.close(code=1008)
        return
    if message:
        await socket.accept()
        await socket.send_json({"type": "error", "message": message})
        await socket.close()
        return
    def commit(speaker,text,timing):
        if not auth_store.user_for_token(token):
            raise HTTPException(401,'Your sign-in expired. Sign in again to continue.')
        return save_turn(key,speaker,text,source='voice',timing=timing,owner_id=user['id'])
    try:
        await socket.accept()
        await serve_voice(socket, commit)
    finally:
        with lock:
            voice_sessions.discard(key)
            voice_owners.pop(key,None)


dist = Path(__file__).resolve().parent / "frontend" / "dist"
landing_dist = Path(__file__).resolve().parent / 'landing' / 'dist'


@app.get('/login')
@app.get('/signup')
def account_page():
    return FileResponse(landing_dist/'index.html',headers={'Cache-Control':'no-store'})


@app.get('/app')
@app.get('/app/')
def workspace_page(request: Request):
    if not auth_store.user_for_token(request.cookies.get(COOKIE_NAME)):
        return RedirectResponse('/login?next=%2Fapp%2F',status_code=303)
    return FileResponse(dist/'index.html',headers={'Cache-Control':'no-store'})


app.mount('/app',StaticFiles(directory=dist,html=True,check_dir=False),name='dashboard')
app.mount('/',StaticFiles(directory=landing_dist,html=True,check_dir=False),name='landing')
