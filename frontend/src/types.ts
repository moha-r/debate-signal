export type Speaker = 'A' | 'B';
export type TurnSpeaker = Speaker | 'Unknown';
export const speakerName = (speaker: TurnSpeaker) =>
  speaker === 'Unknown' ? 'Speaker unconfirmed' : `Speaker ${speaker}`;
export type AlertKind = 'Personal attack' | 'Topic drift';
export type AlertStatus = 'Pending' | 'Reviewed' | 'Dismissed';

export interface Turn {
  number: number;
  speaker: TurnSpeaker;
  text: string;
  processed_text: string;
  time: string;
  attack_probability: number;
  personal_attack: boolean;
  topic: {
    state: 'on_topic' | 'off_topic' | 'unclear';
    score: number | null;
    used_context: boolean;
    alert: boolean;
    reason?: 'conversation_management';
  };
  latency_ms: number;
  source?: 'text' | 'voice';
  argument?: Omit<ArgumentNode, 'turn' | 'speaker' | 'text'>;
  attack_context?: { suppressed: boolean; reason: string | null; context_turns: number[] };
}

export interface ModeratorAlert {
  id: string;
  kind: AlertKind;
  speaker: TurnSpeaker;
  turn: number;
  text: string;
  time: string;
  status: AlertStatus;
  feedback?: { verdict: 'correct' | 'incorrect'; reason: string; time: string };
}

export interface Session {
  id: string;
  topic: string;
  started_at: string;
  revision: number;
  turns: Turn[];
  alerts: ModeratorAlert[];
  participants?: Record<Speaker, string>;
  example?: boolean;
  insights?: {
    version: string;
    arguments: ArgumentNode[];
    participation: {
      seconds: Record<TurnSpeaker, number>;
      shares: Record<TurnSpeaker, number | null>;
      timed_turns: number;
      untimed_turns: number;
      dominant_speaker: Speaker | null;
      policy: { dominance_share: number; minimum_speech_seconds: number };
      measurement: string;
    };
    report: {
      claims: number[]; reasons: number[]; agreements: number[]; disagreements: number[];
      questions: { turn: number; text: string; answer_turns: number[]; evidence_requested: boolean; status?: string; responses?: { turn: number; status: string; confidence: number | null; answer_span?: { text: string; start: number; end: number } }[] }[];
      limitations: string;
    };
  };
}

export interface ArgumentNode {
  turn: number;
  speaker: TurnSpeaker;
  text: string;
  role: 'claim' | 'reason' | 'rebuttal' | 'question' | 'agreement' | 'unclassified';
  cue: string;
  link: { turn: number; similarity: number | null; tentative: boolean; relation?: 'support' | 'attack' | 'answers'; confidence?: number | null } | null;
  role_confidence?: number | null;
  annotation_source?: string;
  review?: { reason: string; time: string };
  evidence_requested: boolean;
  roles?: string[];
}

export interface ArgumentCorrection {
  role: ArgumentNode['role']; target: number | null; relation: 'support' | 'attack' | 'answers' | null; reason: string;
}
