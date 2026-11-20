export type SpeakerId = 'A' | 'B';

export type ArgumentRole =
  | 'Claim'
  | 'Reason / evidence'
  | 'Rebuttal'
  | 'Question'
  | 'Agreement'
  | 'Other contribution';

export type ExampleMode =
  | 'drift'
  | 'attack'
  | 'speaking-time'
  | 'argument-trail'
  | 'report';

export interface DebateTurn {
  id: number;
  turnNumber: string;
  speaker: SpeakerId;
  speakerName: string;
  timestamp: string;
  text: string;
  role: ArgumentRole;
  secondaryRole?: ArgumentRole;
  linksToTurn?: number;
  linkLabel?: string;
  flag?: 'attack' | 'drift';
}

export const DEBATE_QUESTION =
  'Should schools require students to wear uniforms?';

export const SCRIPTED_TURNS: DebateTurn[] = [
  {
    id: 1,
    turnNumber: '01',
    speaker: 'A',
    speakerName: 'Speaker A',
    timestamp: '00:14',
    text: 'School uniforms can reduce pressure to buy expensive clothes.',
    role: 'Claim',
  },
  {
    id: 2,
    turnNumber: '02',
    speaker: 'B',
    speakerName: 'Speaker B',
    timestamp: '00:38',
    text: 'I disagree because a uniform can cost more than clothes families already own.',
    role: 'Rebuttal',
    secondaryRole: 'Reason / evidence',
    linksToTurn: 1,
    linkLabel: 'May challenge turn 01',
  },
  {
    id: 3,
    turnNumber: '03',
    speaker: 'A',
    speakerName: 'Speaker A',
    timestamp: '01:02',
    text: 'What evidence supports that claim about uniform costs?',
    role: 'Question',
    linksToTurn: 2,
    linkLabel: 'Follow-up on turn 02',
  },
  {
    id: 4,
    turnNumber: '04',
    speaker: 'B',
    speakerName: 'Speaker B',
    timestamp: '01:21',
    text: 'You are a stupid idiot.',
    role: 'Other contribution',
    flag: 'attack',
  },
  {
    id: 5,
    turnNumber: '05',
    speaker: 'A',
    speakerName: 'Speaker A',
    timestamp: '01:36',
    text: 'The uniform policy could protect families from unexpected costs.',
    role: 'Reason / evidence',
    linksToTurn: 1,
    linkLabel: 'Supports turn 01',
  },
  {
    id: 6,
    turnNumber: '06',
    speaker: 'B',
    speakerName: 'Speaker B',
    timestamp: '01:58',
    text: 'My neighbour is learning to play the saxophone.',
    role: 'Other contribution',
    flag: 'drift',
  },
  {
    id: 7,
    turnNumber: '07',
    speaker: 'A',
    speakerName: 'Speaker A',
    timestamp: '02:19',
    text: 'The saxophone in his band needs a new mouthpiece.',
    role: 'Other contribution',
    flag: 'drift',
  },
];

export interface IllustrativeParticipation {
  speaker: SpeakerId;
  label: string;
  duration: string;
  percentage: number;
}

export const ILLUSTRATIVE_PARTICIPATION: IllustrativeParticipation[] = [
  {
    speaker: 'A',
    label: 'Speaker A',
    duration: '1:32',
    percentage: 58,
  },
  {
    speaker: 'B',
    label: 'Speaker B',
    duration: '1:08',
    percentage: 42,
  },
];

export interface ArgumentNodeItem {
  id: string;
  turnId: number;
  turnNumber: string;
  role: ArgumentRole;
  secondaryRole?: ArgumentRole;
  speaker: SpeakerId;
  excerpt: string;
  relationLabel?: string;
  relatedToNodeId?: string;
  note: string;
}

export const ARGUMENT_MAP_NODES: ArgumentNodeItem[] = [
  {
    id: 'node-1',
    turnId: 1,
    turnNumber: '01',
    role: 'Claim',
    speaker: 'A',
    excerpt: 'School uniforms can reduce pressure to buy expensive clothes.',
    note: 'Central position introduced in Turn 01, directly anchored to the debate question.',
  },
  {
    id: 'node-2',
    turnId: 2,
    turnNumber: '02',
    role: 'Rebuttal',
    secondaryRole: 'Reason / evidence',
    speaker: 'B',
    excerpt:
      'I disagree because a uniform can cost more than clothes families already own.',
    relationLabel: 'May challenge turn 01',
    relatedToNodeId: 'node-1',
    note: 'Suggested rebuttal with an unverified cost reason linked back to Turn 01.',
  },
  {
    id: 'node-3',
    turnId: 3,
    turnNumber: '03',
    role: 'Question',
    speaker: 'A',
    excerpt: 'What evidence supports that claim about uniform costs?',
    relationLabel: 'Follow-up on turn 02',
    relatedToNodeId: 'node-2',
    note: 'Flagged in the session report as a question with "No answer linked" for moderator follow-up.',
  },
  {
    id: 'node-5',
    turnId: 5,
    turnNumber: '05',
    role: 'Reason / evidence',
    speaker: 'A',
    excerpt:
      'The uniform policy could protect families from unexpected costs.',
    relationLabel: 'Supports turn 01',
    relatedToNodeId: 'node-1',
    note: 'Suggested supporting rationale reinforcing the initial economic claim.',
  },
];

export interface FaqItem {
  question: string;
  answer: string;
}

export const FAQ_ITEMS: FaqItem[] = [
  {
    question: 'What does Where’s your argument? do?',
    answer:
      'It helps a human moderator follow a two-person English debate through live transcription, suggested personal-attack and topic-drift alerts, an argument trail, and a source-linked session report.',
  },
  {
    question: 'Do I have to select the speaker every time?',
    answer:
      'During a recording, speaker labels (A and B) are detected automatically. If attribution is uncertain or appears as Unconfirmed speaker, you can correct a recorded turn and related alerts and speaking-time measurements update as well. Typed turns are assigned manually.',
  },
  {
    question: 'Does it decide who wins?',
    answer:
      'No. The moderator makes the decisions. The workspace offers suggestions and source context to support human review; it does not declare a winner, assign moral scores, or judge ideas.',
  },
  {
    question: 'Does it check facts or verify evidence?',
    answer:
      'No. Argument roles and links are experimental suggestions derived from linguistic rules and semantic similarity. References to evidence are not fact-checked or independently verified.',
  },
  {
    question: 'Which conversations does the current version support?',
    answer:
      'The current prototype is designed for two speakers taking turns in English through a shared microphone, with a human moderator following the workspace.',
  },
  {
    question: 'What happens to microphone audio?',
    answer:
      'During an active recording in the application, audio is streamed to AssemblyAI STT 3.7 Realtime for transcription and speaker labeling. The current app analyzes the resulting text locally and saves session records on the computer running the service. Visiting this landing page never activates your microphone.',
  },
  {
    question: 'Can I export the session, and does feedback retrain the model immediately?',
    answer:
      'You can download an extractive Markdown report with internal turn links, export the complete session as JSON, and export saved moderator assessments as JSONL. Saved assessments are stored for future evaluation and training—they do not retrain the model immediately.',
  },
];

export const CAPABILITY_COMPARISON = {
  availableNow: [
    'A two-voice English debate with a human moderator',
    'Recording through a shared microphone in the workspace',
    'Automatic speaker labels (A / B) with manual correction',
    'Suggested alerts for personal attacks and sustained topic drift',
    'Suggested argument roles and tentative source links',
    'Speaking time measured from finalized word timestamps',
    'Extractive Markdown & JSON reports plus JSONL assessment exports',
    'Local SQLite persistence on the computer running the app',
    'Individual accounts with private saved debates and moderator reviews',
  ],
  notClaimed: [
    'Multilingual conversations or unlimited participants',
    'Remote audio/video calling rooms or meeting invite links',
    'Identity verification or persistent voice ID across sessions',
    'Fact-checking, study quality grading, or declaring a winner',
    'Tone, emotion, or lie detection',
    'Comprehensive detection of every fallacy or subtle sarcasm',
    'Immediate, automatic model retraining from every click',
    'Cloud accounts, team permissions, or cross-device sync',
  ],
};
