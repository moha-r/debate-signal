import { useEffect, useRef, useState } from 'react';
import { AudioLines, CircleAlert, KeyRound, LoaderCircle, Mic, Settings2, Square, X } from 'lucide-react';
import { speakerName, type Session, type TurnSpeaker } from './types';

type Phase = 'off' | 'preparing' | 'connecting' | 'recording' | 'finishing';
type Capture = {
  stream: MediaStream;
  context: AudioContext;
  source: MediaStreamAudioSourceNode;
  worklet: AudioWorkletNode;
};
type VoiceEvent =
  | { type: 'ready' }
  | { type: 'transcript'; text: string }
  | { type: 'turn_added'; session: Session; speaker: TurnSpeaker; text: string }
  | { type: 'stopped'; count: number; draft: string; reason?: 'duration_limit' | null }
  | { type: 'error'; message: string; draft: string };

interface Props {
  sessionId?: string;
  blocked: boolean;
  onBusy: (busy: boolean) => void;
  onUpdate: (session: Session) => void;
  onRecover: (draft: string) => void;
  onStart: () => void;
  onFinish: () => void;
  initialDeviceId?: string;
  names: { A: string; B: string };
}

const labels: Record<Phase, string> = {
  off: 'Mic off', preparing: 'Opening microphone', connecting: 'Connecting',
  recording: 'Listening', finishing: 'Finalizing',
};

const zeroBars = Array<number>(25).fill(0);

function clock(seconds: number) {
  return [Math.floor(seconds / 60), seconds % 60].map((value) => String(value).padStart(2, '0')).join(':');
}

export default function VoiceConsole(props: Props) {
  const { sessionId, blocked, onStart } = props;
  const callbacks = useRef(props);
  callbacks.current = props;
  const [phase, setPhase] = useState<Phase>('off');
  const phaseRef = useRef<Phase>('off');
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [key, setKey] = useState('');
  const [editKey, setEditKey] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [confirmedSpeaker, setConfirmedSpeaker] = useState<TurnSpeaker | null>(null);
  const [message, setMessage] = useState('');
  const [problem, setProblem] = useState(false);
  const [bars, setBars] = useState(zeroBars);
  const [seconds, setSeconds] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState(props.initialDeviceId || '');
  const [microphoneName, setMicrophoneName] = useState('');
  const socket = useRef<WebSocket | null>(null);
  const audio = useRef<Capture | null>(null);
  const clockStart = useRef(0);
  const draft = useRef('');
  const attempt = useRef(0);
  const waitFlush = useRef<number | null>(null);

  function transition(next: Phase) {
    phaseRef.current = next;
    setPhase(next);
    callbacks.current.onBusy(next !== 'off');
  }

  function show(text: string, isProblem = false) {
    setMessage(text);
    setProblem(isProblem);
  }

  function releaseCapture() {
    if (waitFlush.current !== null) {
      window.clearTimeout(waitFlush.current);
      waitFlush.current = null;
    }
    const capture = audio.current;
    audio.current = null;
    if (!capture) return;
    capture.stream.getTracks().forEach((track) => track.stop());
    capture.source.disconnect();
    capture.worklet.port.onmessage = null;
    capture.worklet.disconnect();
    void capture.context.close().catch(() => undefined);
  }

  function disconnect() {
    attempt.current++;
    releaseCapture();
    const active = socket.current;
    socket.current = null;
    if (active && active.readyState < WebSocket.CLOSING) active.close();
    transition('off');
    setBars(zeroBars);
  }

  function recover(text: string) {
    if (text) callbacks.current.onRecover(text);
    draft.current = '';
  }

  useEffect(() => {
    let cancelled = false;
    fetch('/api/voice/config')
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then(({ configured }) => { if (!cancelled) setConfigured(Boolean(configured)); })
      .catch(() => { if (!cancelled) setConfigured(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (phaseRef.current === 'off') setDeviceId(props.initialDeviceId || '');
  }, [props.initialDeviceId]);

  useEffect(() => {
    if (!settingsOpen || !navigator.mediaDevices?.enumerateDevices) return;
    let cancelled = false;
    navigator.mediaDevices.enumerateDevices()
      .then((items) => { if (!cancelled) setDevices(items.filter((item) => item.kind === 'audioinput')); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [settingsOpen]);

  useEffect(() => {
    draft.current = '';
    setTranscript('');
    setConfirmedSpeaker(null);
    setSeconds(0);
    show('');
    return disconnect;
  }, [sessionId]);

  useEffect(() => {
    if (phase !== 'recording') return;
    const timer = window.setInterval(() => setSeconds(Math.floor((performance.now() - clockStart.current) / 1000)), 150);
    return () => window.clearInterval(timer);
  }, [phase]);

  function sendStop(active: WebSocket) {
    if (socket.current !== active || phaseRef.current !== 'finishing' || !audio.current) return;
    releaseCapture();
    if (active.readyState === WebSocket.OPEN) active.send(JSON.stringify({ type: 'stop' }));
  }

  function stop() {
    const active = socket.current;
    const capture = audio.current;
    if (phaseRef.current !== 'recording' || !active || !capture) return;
    transition('finishing');
    show('Finishing the last speaking turn.');
    capture.stream.getTracks().forEach((track) => track.stop());
    capture.source.disconnect();
    capture.worklet.port.postMessage('flush');
    waitFlush.current = window.setTimeout(() => sendStop(active), 600);
  }

  async function start() {
    if (!sessionId || phaseRef.current !== 'off') return;
    if ((editKey || !configured) && !key.trim()) {
      setSettingsOpen(true);
      show('Enter your AssemblyAI key to start.', true);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.AudioContext || !window.AudioWorkletNode) {
      show('Open this local dashboard in Chrome or Safari to use the microphone.', true);
      return;
    }
    const current = ++attempt.current;
    transition('preparing');
    setSeconds(0);
    setBars(zeroBars);
    draft.current = '';
    setTranscript('');
    setConfirmedSpeaker(null);
    show('');
    let context: AudioContext | undefined;
    let stream: MediaStream | undefined;
    try {
      try {
        context = new AudioContext({ latencyHint: 'interactive', sampleRate: 16000 });
      } catch {
        context = new AudioContext({ latencyHint: 'interactive' });
      }
      await context.resume();
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true,
          ...(deviceId ? { deviceId: { exact: deviceId } } : {}) },
      });
      await context.audioWorklet.addModule(`${import.meta.env.BASE_URL}voice-processor.js`);
      if (attempt.current !== current) {
        stream.getTracks().forEach((track) => track.stop());
        await context.close();
        return;
      }
      setMicrophoneName(stream.getAudioTracks()[0]?.label || 'Default microphone');
      setSettingsOpen(false);
      const source = context.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(context, 'debate-voice', { channelCount: 1, channelCountMode: 'explicit' });
      const silence = context.createGain();
      silence.gain.value = 0;
      worklet.connect(silence).connect(context.destination);
      audio.current = { stream, context, source, worklet };

      const url = new URL(`/api/sessions/${sessionId}/voice`, location.href);
      url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const active = new WebSocket(url);
      socket.current = active;
      transition('connecting');
      active.onopen = () => {
        if (socket.current === active) active.send(JSON.stringify({ type: 'connect', key: key.trim() }));
      };
      active.onmessage = ({ data }) => {
        if (socket.current !== active) return;
        const event = JSON.parse(data) as VoiceEvent;
        switch (event.type) {
          case 'ready':
            setEditKey(false);
            if (configured && !editKey) setKey('');
            source.connect(worklet);
            clockStart.current = performance.now();
            transition('recording');
            show('Share the microphone and take turns speaking.');
            break;
          case 'transcript':
            draft.current = event.text;
            setTranscript(event.text);
            setConfirmedSpeaker(null);
            break;
          case 'turn_added':
            draft.current = '';
            setTranscript(event.text);
            setConfirmedSpeaker(event.speaker);
            callbacks.current.onUpdate(event.session);
            break;
          case 'stopped':
            recover(event.draft);
            disconnect();
            show(event.reason === 'duration_limit' ? 'Recording time limit reached. Completed turns are saved; start another recording to continue.' : event.draft ? 'The last phrase was recovered in the text draft.'
              : event.count ? 'Debate ended. All completed turns are in the transcript.'
              : 'Debate ended. No speech was detected.');
            callbacks.current.onFinish();
            break;
          case 'error':
            recover(event.draft || draft.current);
            if (event.message.toLowerCase().includes('key')) {
              setEditKey(true);
              setSettingsOpen(true);
            }
            disconnect();
            show(event.message, true);
            break;
        }
      };
      active.onclose = () => {
        if (socket.current !== active) return;
        recover(draft.current);
        disconnect();
        show('Voice connection closed. Start again to continue.', true);
      };

      worklet.port.onmessage = ({ data }) => {
        if (socket.current !== active || active.readyState !== WebSocket.OPEN) return;
        if (data.type === 'flushed') sendStop(active);
        if (data.type !== 'audio' || !['recording', 'finishing'].includes(phaseRef.current)) return;
        if (active.bufferedAmount > 32000) {
          recover(draft.current);
          disconnect();
          show('The connection could not keep up with the microphone. Start again to continue.', true);
          return;
        }
        active.send(data.pcm as ArrayBuffer);
        const level = Math.min(1, Math.sqrt(Number(data.rms) || 0) * 2.6);
        setBars((previous) => [...previous.slice(1), level]);
      };
      worklet.onprocessorerror = () => {
        if (socket.current !== active) return;
        recover(draft.current);
        disconnect();
        show('The microphone processor stopped. Start again to record.', true);
      };
      stream.getAudioTracks().forEach((track) => {
        track.onended = () => {
          if (socket.current !== active) return;
          if (phaseRef.current === 'recording') stop();
          else if (phaseRef.current === 'connecting') {
            disconnect();
            show('The microphone disconnected. Check your device and start again.', true);
          }
        };
      });
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop());
      if (context && audio.current?.context !== context) void context.close().catch(() => undefined);
      if (attempt.current !== current) return;
      disconnect();
      const denied = error instanceof DOMException && error.name === 'NotAllowedError';
      show(denied ? 'Microphone access was denied. Allow it in your browser and try again.'
        : 'The microphone could not start. Check your device and try again.', true);
    }
  }

  const recording = phase === 'recording';
  const waiting = phase !== 'off' && !recording;
  const action = !sessionId ? onStart : recording ? stop : start;
  const actionLabel = !sessionId ? 'Start a session' : recording ? 'End recording' : waiting ? labels[phase] : 'Start recording';
  const icon = recording ? <Square size={22} fill="currentColor" />
    : waiting ? <LoaderCircle className="spinner" size={27}/>
    : <Mic size={31} strokeWidth={1.65}/>;

  return <section className={`voice-banner phase-${phase}`} aria-label="Recording controls">
    <div className="voice-banner-top">
      <span className="voice-state" role="status"><i/>{labels[phase]}</span>
      <span className="voice-auto"><AudioLines size={13}/> Automatic speaker detection</span>
      <div className="voice-banner-actions">
        <time aria-label="Recording time">{clock(seconds)}</time>
        <button type="button" className="btn icon" aria-label="Audio settings" aria-expanded={settingsOpen}
          onClick={() => setSettingsOpen((open) => !open)}><Settings2 size={17}/></button>
        <button type="button" className={`btn ${recording ? 'stop-recording' : 'primary'}`}
          disabled={waiting || (!recording && (blocked || configured === null))} onClick={() => void action()}>
          {icon}<span>{actionLabel}</span>
        </button>
        {(phase === 'preparing' || phase === 'connecting') && <button type="button" className="btn icon"
          onClick={() => { disconnect(); show('Recording cancelled.'); }} aria-label="Cancel voice connection"><X size={15}/></button>}
      </div>
    </div>
    <div className="voice-live-line">
      <div className="voice-wave" aria-hidden="true">
        {bars.map((height, index) => <i key={index} style={{ height: `${4 + (recording ? height * 30 : 0)}px` }}/>)}
      </div>
      <p className={`live-caption ${transcript ? 'has-text' : ''}`}>
        {confirmedSpeaker && <strong>{confirmedSpeaker === 'Unknown' ? 'Speaker unconfirmed' : props.names[confirmedSpeaker]} </strong>}
        {transcript || (recording ? 'Listening. Your next thought will appear here…' : 'When you’re ready, let the conversation begin.')}
      </p>
    </div>
    <p className={`voice-notice ${problem ? 'problem' : ''}`} role={problem ? 'alert' : undefined}>
      {problem ? <CircleAlert size={12}/> : <Mic size={12}/>}
      {message || 'Audio is sent to AssemblyAI while recording. Your transcript is analyzed locally.'}
      {microphoneName && <span>{microphoneName}</span>}
    </p>
    {settingsOpen && <div className="voice-settings-panel" role="region" aria-label="Audio settings panel">
      <div className="small-heading"><h3>Audio settings</h3><button type="button" className="btn icon" aria-label="Close audio settings" onClick={() => setSettingsOpen(false)}><X size={15}/></button></div>
      <label>Microphone<select value={deviceId} disabled={phase !== 'off'} onChange={(event) => setDeviceId(event.target.value)}>
        <option value="">System default microphone</option>
        {devices.filter((device) => device.deviceId && device.deviceId !== 'default').map((device, index) =>
          <option key={device.deviceId} value={device.deviceId}>{device.label || `Microphone ${index + 1}`}</option>)}
      </select></label>
      {phase !== 'off' && <p>End the recording to change your microphone.</p>}
      {phase === 'off' && <label><span><KeyRound size={12}/> AssemblyAI API key</span>
        <input type="password" value={key} onChange={(event) => { setKey(event.target.value); setEditKey(true); }}
          placeholder={configured ? 'Server key configured' : 'Enter your API key'} maxLength={256} autoComplete="off"/>
      </label>}
    </div>}
  </section>;
}
