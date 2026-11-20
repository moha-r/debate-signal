import { useEffect, useRef, useState } from 'react';
import { Check, Mic, Square } from 'lucide-react';

export default function MicrophoneCheck({ deviceId, onDevice }: {
  deviceId: string; onDevice: (id: string) => void;
}) {
  const [testing, setTesting] = useState(false);
  const [level, setLevel] = useState(0);
  const [message, setMessage] = useState('Test how clearly your microphone picks up your voice.');
  const [passed, setPassed] = useState(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const release = useRef<() => void>(() => undefined);
  const attempt = useRef(0);
  useEffect(() => () => { attempt.current++; release.current(); }, []);

  async function test() {
    if (testing) { release.current(); return; }
    const current = ++attempt.current;
    setMessage('Waiting for microphone access…');
    let stream: MediaStream | undefined;
    let context: AudioContext | undefined;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: deviceId ? { deviceId: { exact: deviceId } } : true });
      if (attempt.current !== current) { stream.getTracks().forEach((track) => track.stop()); return; }
      context = new AudioContext();
      await context.resume();
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      const samples = new Float32Array(analyser.fftSize);
      let raf = 0;
      let heard = false;
      const endAt = performance.now() + 10000;
      release.current = () => {
        cancelAnimationFrame(raf);
        stream?.getTracks().forEach((track) => track.stop());
        void context?.close().catch(() => undefined);
        setTesting(false);
        setLevel(0);
        setPassed(heard);
        setMessage(heard ? 'Your microphone is picking up speech. You’re ready.'
          : 'Microphone connected. Speak closer or select another input if the meter stays still.');
      };
      const render = () => {
        analyser.getFloatTimeDomainData(samples);
        const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
        if (rms > .012) heard = true;
        setLevel(Math.min(1, rms * 9));
        if (performance.now() > endAt) { release.current(); return; }
        raf = requestAnimationFrame(render);
      };
      setTesting(true);
      setMessage('Say a sentence. This check stays on your device.');
      render();
      navigator.mediaDevices.enumerateDevices().then((items) => {
        if (attempt.current === current) setDevices(items.filter((item) => item.kind === 'audioinput' && item.deviceId));
      }).catch(() => undefined);
    } catch {
      stream?.getTracks().forEach((track) => track.stop());
      void context?.close().catch(() => undefined);
      setMessage('The microphone could not open. Check browser permission and your input device.');
    }
  }

  return <section className="mic-check">
    <div className={`mic-check-symbol ${testing ? 'testing' : passed ? 'passed' : ''}`}>{passed && !testing ? <Check size={25}/> : <Mic size={25}/>}</div>
    <h3>{testing ? 'Let’s hear your voice.' : passed ? 'You sound ready.' : 'A quick sound check.'}</h3>
    <p>{message}</p>
    <div className="check-meter" aria-label="Microphone level" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(level * 100)}>
      {Array.from({length: 30}, (_, index) => <i key={index} className={level * 30 > index ? 'lit' : ''}/>)}
    </div>
    <label>Input device
      <select value={deviceId} onChange={(event) => { onDevice(event.target.value); setPassed(false); }} disabled={testing}>
        <option value="">System default microphone</option>
        {devices.filter((device) => device.deviceId !== 'default').map((device, index) =>
          <option key={device.deviceId} value={device.deviceId}>{device.label || `Microphone ${index + 1}`}</option>)}
      </select>
    </label>
    <button type="button" className="btn secondary" onClick={() => void test()}>
      {testing ? <Square size={13}/> : <Mic size={14}/>} {testing ? 'Stop check' : 'Test microphone'}
    </button>
  </section>;
}
