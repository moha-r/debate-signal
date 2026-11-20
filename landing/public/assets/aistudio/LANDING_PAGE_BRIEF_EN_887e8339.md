# Project Landing Page Design and Development Handoff Brief

## Where’s your argument?

**For the landing page designer and developer**  
**Current version documented: November 18, 2026**  
**Language of this document: English. Proposed landing page language: English, consistent with the application's current interface and supported conversations.**

This document describes the product, brand identity, user experience, and required content so that you can build the landing page without seeing the project or referring to team conversations. The deliverable is a product introduction and exploration page. It can be developed separately from the application, with integration coordinated afterward. The proposed section order and copy below are implementation suggestions; the feature descriptions, limitations, and visual direction serve as the project's reference specifications.

---

## 1. Read This Summary First

**Where’s your argument? is a workspace that helps a human moderator follow a two-person debate in English, transcribe speech with speaker attribution, flag possible personal attacks and sustained topic drift, and review arguments, participation, and outcomes with a way to trace every observation back to its source.**

The core scenario involves **two people having a discussion while a human moderator follows along on screen**. The moderator sets the debate question and starts recording once. The two participants take turns speaking into a shared microphone. Their turns appear on screen while the moderator monitors alerts, speaking time, and the argument trail. When recording ends, the moderator proceeds to the session report and review.

The value we want visitors to grasp immediately is:

> I can focus on the discussion itself while using a workspace that shows who said what, what may need my intervention, and where I can go back to verify it.

**Central landing page idea:** Space for every voice, and a debate that is easier to follow and review.

**Visual tone:** Calm, clear, considered, and deliberately interactive. Very light backgrounds, subtle lavender, dark primary buttons, generous spacing, and a small pearlescent 3D accent.

**The three most important messages in the first screen:**

1. The product assists with moderating live debates.
2. The two speakers are detected automatically, and observations link back to the original speech.
3. There is an obvious button to open the workspace and an easy way to understand the product through an example.

---

## 2. Why We Built This Project

During a debate, a moderator's attention is divided among following the ideas, remembering what each person said, noticing when the discussion becomes personal, recognizing when it goes off topic, and watching for one participant taking most of the speaking time. Afterward, producing a useful review is much harder without an organized record.

The project addresses these challenges in one workspace:

| Moderator challenge | What the project provides | Practical benefit |
|---|---|---|
| Remembering who said each statement | An organized transcript with speaker labels | Quickly return to a particular turn |
| Missing an offensive remark during discussion | A possible-personal-attack alert with context | Help the moderator decide when to intervene |
| The discussion drifting into a side topic | Tracking how turns relate to the question and alerting on sustained drift | Redirect the discussion toward its main topic |
| Difficulty following how ideas and responses develop | A suggested map of claims, reasons, and rebuttals | Understand how the argument evolved |
| Uneven participation | Speaking time measured from audio for each speaker | Give the other participant a clearer opportunity to contribute |
| Difficulty reviewing what happened afterward | A report, source references, and export options | Make use of the discussion later |

Do not reduce the product to detecting offensive language. Debate moderation is the main story; detecting personal attacks is one capability within it.

## 3. Who Is the Product For?

The most relevant audience includes moderators of educational debates, university debate clubs, teachers facilitating discussions between two students, and debate trainees who want to review their sessions.

These are **suggested use cases**. They do not imply existing customers, partnerships, or formal university endorsements. The current version is an experimental academic project that runs locally, and the page should present it transparently as such.

The product's value can be framed around three actions:

- **Follow:** See who is speaking and what is being said.
- **Notice:** Identify moments that deserve a closer look.
- **Reflect:** Review arguments and participation after the debate.

## 4. The Human Role in the Experience

The human moderator makes the decisions. The system presents signals and suggestions; the moderator reads the context and decides how to respond. The application does not declare a winner, assign moral scores to participants, or make final judgments about their ideas.

This matters both to the page's messaging and its visual presentation. Visitors should see actions such as **Review context**, **Mark reviewed**, and **Dismiss**. Making the moderator's power to review visible is more compelling than an exaggerated promise that AI decides everything.

Suggested copy:

> **You’re in the moderator’s seat.**  
> Suggestions bring moments into focus. The judgment stays with you.

---

## 5. How Someone Uses the Project, Start to Finish

### Step One — Open the Workspace

An Overview page provides a clear starting point to create a debate, explore a prepared example, and access previous sessions. The prepared example lets someone understand the experience without turning on the microphone.

### Step Two — Set the Question

The moderator creates a session and enters a topic as a debatable question, such as:

> Should schools require students to wear uniforms?

This question remains the reference point against which turns are compared during topic monitoring.

### Step Three — Identify the Participants

The experience is configured for two voices. Labels A and B are detected automatically within a recording session, and optional display names can be added to make the turns clearer to the moderator.

**A and B are labels for two voices; they do not automatically indicate a supporting side and an opposing side.** A person may agree on one point and disagree on another. The system also does not verify real-world identity or guarantee persistent recognition of the same person across separate recordings.

### Step Four — Optionally Check the Audio

Before the session, the moderator can select a microphone and test audio input locally. Merely visiting the landing page must not start a real recording or transmit audio.

### Step Five — Run the Debate

The moderator selects **Start recording** and grants microphone access. Audio is streamed to AssemblyAI for transcription and speaker labeling. Draft text appears during speech; when a turn is finalized, it is saved to the session record and analyzed locally.

During the debate, the moderator sees:

- A running transcript with the speaker and turn number.
- Alerts that may need attention.
- Measured speaking time and participation for each voice.
- A concise trail of arguments and responses.

### Step Six — Review Flagged Moments

The moderator can jump to the statement associated with an alert and read the preceding and following turns. They can choose Reviewed or Dismissed to organize the review queue, and separately save an assessment of whether an alert is correct or incorrect, optionally providing a reason.

### Step Seven — End the Recording and Review Results

The moderator selects **End recording**. Processing of the final speech is completed, and the session report opens. The moderator can review the transcript, argument map, and observations, and download the report or data. The session and its assessments remain stored locally after the service restarts.

---

## 6. Feature Guide — What Each Feature Does, Why It Matters, and How to Show It

### 6.1 Live Transcription and Automatic Speaker Detection

**Available capability:** Audio is captured from the browser, English speech is transcribed using AssemblyAI STT 3.7 Realtime, and turns are attributed to A or B. Provisional text appears as someone speaks, and finalized turns become part of the session transcript and analysis.

**Benefit:** Both people can keep talking without manually selecting a speaker for every turn, and the moderator can revisit what each participant said.

**Important detail:** A voice may appear as Unconfirmed speaker when attribution is uncertain. The moderator can correct the speaker of a recorded turn, and the associated alert labels and speaking-time measurements update as well. Automatic detection requires two distinct voices; it does not guarantee accurate separation of overlapping speech.

**Suggested visual:** Two speaker cards with short turns revealing themselves in sequence between or underneath them. Speaker names and turn numbers communicate more than an excess of technical indicators.

**Suggested copy:**

> **Two voices. One clear transcript.**  
> Follow an English debate with automatic speaker labels and a transcript you can return to.

### 6.2 Topic Tracking and Sustained Drift Alerts

**Available capability:** Spoken contributions are compared with the session question, with limited use of nearby context for short follow-ups related to a clearly on-topic turn. An alert is triggered after two turns classified as off topic, and repeated sustained-drift alerts are suppressed until the discussion returns to the topic.

**Benefit:** Helps the moderator spot a tangent that may warrant redirecting the conversation, while keeping the original question in view.

**Important detail:** Short or ambiguous statements may be labeled Unclear. The context mechanism is not a comprehensive memory that understands every nuance of the discussion. The inference is experimental and may be wrong, particularly for indirect connections.

**Suggested visual:** A fixed question at the top of a small scene, followed by two turns moving away from it and a subtle amber card labeled Topic drift with a Review context button.

**Suggested copy:**

> **Keep the original question in view.**  
> Spot possible sustained topic drift and inspect the turns behind the suggestion.

### 6.3 Personal Attack Alerts

**Available capability:** A text classifier assigns a score for the likelihood of a personal attack and generates an alert when the decision threshold is exceeded. Limited handling is provided for cases such as discussing a quoted offensive expression or narrowly denying a previous accusation, while retaining the model's original score and an explanation of the handling.

**Benefit:** Draws attention to moments when discussion shifts from addressing ideas to targeting a person.

**Important detail:** The system does not guarantee detection of all sarcasm, implicit abuse, insults, or fallacies. It does not provide general-purpose detection of every ethical violation.

**Suggested visual:** A highlighted statement in the debate transcript next to a Possible personal attack card, followed by the surrounding context and review actions. One short example is enough; do not make offensive wording the largest text in the hero.

**Suggested copy:**

> **Notice when the debate gets personal.**  
> Review possible personal attacks alongside the conversation that led to them.

### 6.4 Nearby Context and Source Links

**Available capability:** A statement can be reviewed alongside surrounding turns. The current context-handling process uses no more than the previous four turns and requires the reference turn to be directly relevant to the topic. Items in the argument map and session report open the original turn.

**Benefit:** Moderators can inspect the basis of a suggestion instead of manually searching the entire transcript.

**Suggested visual:** A one-click interaction on Turn 04 shifts focus to the fourth turn and highlights it gently. This is one of the strongest meaningful interactions to demonstrate on the landing page.

**Suggested copy:**

> **Every suggestion has somewhere to look.**  
> Move from a flagged moment or argument link straight to the source turn.

### 6.5 Argument Map

**Available capability:** The system suggests roles for individual turns and displays possible links between nearby contributions. The roles are:

| Label | Meaning |
|---|---|
| Claim | A statement presenting a position or central idea relevant to the topic |
| Reason / evidence | A reason or reference to evidence or an example; the evidence has not been verified |
| Rebuttal | An objection or challenge to an earlier idea |
| Question | A question that may need follow-up |
| Agreement | An explicit expression of agreement |
| Other contribution | A turn with no clearly suitable role |

A rebuttal can also be classified as Reason / evidence. Links use tentative language such as May challenge turn 1. The map can be filtered by role, and users can navigate back to each source turn.

**Benefit:** View how ideas, objections, and reasons develop instead of reading only a long block of text.

**Critical detail for marketing copy:** This version uses linguistic rules and semantic similarity to suggest roles and links. There is currently no separately trained model that guarantees an analysis of every argument's structure. The system does not verify whether evidence is true, comprehensively score the quality of reasoning, or detect all fallacies. It also does not automatically perform comprehensive classification into pro and con teams.

**Suggested visual:** A clear vertical trail or small connected groups showing a Claim, a linked Rebuttal, and a reason. Avoid a crowded network of dozens of nodes. HTML cards and clear links are well suited to this feature; it does not require a 3D scene.

**Suggested copy:**

> **See how ideas connect.**  
> Explore suggested claims, reasons, rebuttals and questions, with links back to the conversation.

### 6.6 Participation and Speaking Time

**Available capability:** Speaking intervals are calculated from finalized, timestamped words received from AssemblyAI for each speaker and each recording, excluding silence and avoiding duplicate counting of overlapping intervals. Participation percentages are based on this measured duration; intervals with unconfirmed speaker attribution remain separate.

**Benefit:** See how much opportunity each voice has had to contribute and give the moderator a signal to invite the less active participant to speak.

**When does an alert appear?** Once at least 30 seconds of measured speech is available, both voices have recorded speaking time, and one voice accounts for more than 70% of the total measured speech. This is an assistive alert policy, not a scientific determination that someone is dominating the conversation.

**Important detail:** Speaking time is approximate because it relies on speech-recognition timestamps. It is not inferred from word counts or number of turns. Typed turns and older recordings without saved timing data appear without durations; do not invent times for them.

**Suggested visual:** A split participation bar showing lavender for speaker A and peach for speaker B, with clear durations and percentages. If mockups use numbers, label them as illustrative and do not present them as product performance statistics.

**Suggested copy:**

> **Make room for both voices.**  
> Compare measured speaking time and notice when one voice takes most of the space.

### 6.7 Session Report

**Available capability:** An extractive report groups quotations from the session under claims, reasons, agreements, disagreements, and questions, alongside participation measurements and links to source turns. It can be downloaded as Markdown containing the full transcript and internal links, and the session can be exported as JSON.

**Benefit:** Review what was said, prepare for a later session, or discuss participant performance using a clear record.

**How should questions be described?** A question with no linked answer is displayed with wording such as No answer linked. This prompts the moderator to review it; it does not prove nobody answered it. Likewise, labeling a turn Reason / evidence does not mean that a source was actually presented or that its accuracy was established.

**Suggested visual:** A well-organized report preview with Main claims, Expressed disagreement, and Questions to follow up, plus a download button and references such as Turn 01 and Turn 03.

**Suggested copy:**

> **Leave with a conversation you can revisit.**  
> Review source-linked claims, responses and follow-up questions, then export the session.

### 6.8 Moderator Assessment of Alerts

**Available capability:** The moderator can assess an alert as correct or incorrect, add an optional reason, and update that assessment later. The assessment is saved with the session, and assessments can be exported as JSONL with the text, context, and detector information for future evaluation or training.

There are two different actions in the experience:

- **Reviewed / Dismissed:** Organize the moments the moderator has looked at.
- **Alert is correct / Alert is incorrect:** Record an assessment of the alert's accuracy.

**Benefit:** Preserve useful corrections that can be revisited and build review data to help improve the project in the future.

**Important detail:** Saving an assessment does not immediately train the model, and the system does not automatically learn at the moment a button is clicked.

**Suggested copy:**

> **Make your review useful beyond the moment.**  
> Save whether an alert was accurate, add context and export assessments for future evaluation.

### 6.9 Saved Sessions, Prepared Example, and Typed Input

- Sessions, turns, alerts, names, and assessments remain stored locally in the current version.
- My debates provides a way to revisit sessions.
- A prepared example lets users understand the application without recording audio.
- Users can add a typed turn and manually assign it to A or B. Manual assignment here applies to user-entered text and does not replace automatic speaker detection during recording.
- If the audio connection fails, available draft words can be recovered into the text editor for further review and addition to the session.

These are useful supporting capabilities and can be grouped in a smaller section rather than competing with the core features at the top of the page.

---

## 7. A Clear Picture of the Current Version's Limits

| Available now | Do not present as an existing feature |
|---|---|
| A two-voice English debate with a human moderator | Multilingual conversations or meetings with unlimited participants |
| Recording through a shared microphone | Remote audio/video calling rooms or meeting invitation links |
| Automatic speaker labels with optional correction | Identity verification or persistent recognition across recordings |
| Alerts for personal attacks and sustained topic drift | Comprehensive monitoring of all fallacies, manipulation, or interruptions |
| Suggested argument roles and possible links | Fact-checking, evaluation of study quality, or declaring a winner |
| Speaking time measured from word timestamps | Tone or emotion analysis, or lie detection |
| An extractive report linked to sources | Perfect AI-generated minutes that understand every detail without errors |
| Saved assessments for later review and training | Immediate, automatic learning from every click |
| Local storage and exports | Cloud accounts, team management, permissions, or cross-device synchronization |
| An existing locally running application | A production-ready public deployment, paid subscriptions, or guaranteed enterprise reliability |

Do not add prices, plans, user counts, star ratings, customer testimonials, or university logos. Do not publish general accuracy or latency figures; current lab measurements relate to specific tests and do not establish performance across all real-world conversations.

---

## 8. Our Chosen Visual Direction

### Selected Reference

The project owner chose a **Coreto.AI**-inspired direction. The specific reference is [Coreto.AI — AI Note Taking Dashboard, by Nija Design / Nija Works on Dribbble](https://dribbble.com/shots/26420583-Coreto-AI-AI-Note-Taking-Dashboard).

Use it as a reference for a calm, considered productivity-product aesthetic. The approved interpretation for this project is defined by the specifications below and the application's existing interface. The exact colors and fonts listed here come from the application itself and may differ from the reference. Preserve our name and identity, and create original components and illustrations; do not copy the reference's images, logo, or text into our page.

### Desired Impression

Opening the page should feel like entering a calm workspace with a clear, dependable interface. The product should feel contemporary, polished, gently distinctive, and conducive to focus.

Words that describe the direction:

**Calm · Considered · Airy · Human · Tactile · Clear**

Lavender is a restrained brand accent, paired with generous white and very light spaces. Depth comes from lighting, borders, subtle shadows, and a limited 3D presence, within a visual hierarchy led by the concept and the interface.

### Colors

| Role | Value | Usage |
|---|---|---|
| Main background | `#F9F9FC` | Page background and breathing space |
| Light alternate background | `#FCFCFE` | Gentle variation between sections |
| Surfaces | `#FFFFFF` | Cards, previews, and fields |
| Primary text | `#24232B` | Headings and important content |
| Current secondary text | `#85818F` | Secondary labels; check contrast during implementation |
| Borders and dividers | `#EEECF2` | Soft separation of surfaces |
| Brand accent | `#8F6AC5` | Links, selected states, and short heading accents |
| Soft lavender surface | `#F3EDFB` | Subtle backgrounds and highlights |
| Dark button gradient start | `#29272E` | Subtle primary-button gradient |
| Dark button gradient end | `#1D1B21` | End of primary-button gradient |
| Speaker A | `#A58AC7` | Voice markers and participation bar |
| Speaker B | `#E8BC9C` | Peach distinction for the second voice |
| Unconfirmed speaker | `#B5B1BC` | Neutral, unconfirmed state |

Use muted amber for topic-drift alerts and a soft pink for possible personal attacks. A restrained mint green may indicate agreement. Keep text legible against its background; pastel color alone is insufficient to convey status and must be accompanied by a meaningful label or icon.

Suggested starting point for CSS variables:

```css
:root {
  --page: #f9f9fc;
  --page-alt: #fcfcfe;
  --surface: #ffffff;
  --ink: #24232b;
  --muted: #85818f;
  --line: #eeecf2;
  --accent: #8f6ac5;
  --accent-soft: #f3edfb;
  --speaker-a: #a58ac7;
  --speaker-b: #e8bc9c;
  --speaker-unknown: #b5b1bc;
}
```

### Fonts and Typographic Hierarchy

**Approved primary font: DM Sans Variable.** Use it for headings, body copy, and buttons. **Data font: IBM Plex Mono** for timers, turn numbers, and small labels where helpful.

The landing page should use larger type than the dashboard. The following sizes are recommendations for the new page, not a description of the application's current typography:

| Element | Desktop | Mobile |
|---|---|---|
| Hero headline | 56–72px, weight 450–550 | 36–44px |
| Section headings | 32–44px | 27–34px |
| Hero description | 18–20px | 16–18px |
| Body text | 16–18px | 16px |
| Labels | 12–14px | 12–14px |

Keep English headlines short, with moderately tight letter spacing. Aim for a clear two- or three-line hero and comfortable body-text line height. Do not copy the application's small dashboard text sizes into marketing content; readability is the priority.

### Shapes, Surfaces, and Buttons

- Current cards have corners of approximately 11px and light borders. The main hero product preview can use 16–20px corners while preserving a balanced look.
- The primary button is dark with white text, a slight gradient, and a subtle inner top highlight. It rises about 1px on hover and moves down slightly when pressed.
- The secondary button is white with a soft border and muted purple-gray text.
- Shadows should be light and diffuse, giving a sense of layers without heavy edges.
- Use small badges to clarify Claim, Possible attack, or English · Two speakers, but do not turn every line into a badge.
- Use a consistent line-icon style; the application uses Lucide.

### 3D Accent and Motion

The current interface includes a small lavender pearlescent sphere built with Three.js, with soft lighting, a slow floating motion, and a very subtle scale change. It has a CSS-gradient fallback when WebGL is unavailable.

This element could become a distinctive hero detail or a device that visually brings two voices toward a shared discussion space. Keep it restrained and ensure the product preview and copy remain clear. Successful Three.js loading must not be a condition for displaying the headline or buttons.

Suggested page motion:

- Simple element entrances lasting approximately 180–350ms.
- Smooth transitions between example states and when a source link is revealed.
- A small audio waveform inside the example only; label it if simulated.
- Subtle button changes on hover and press.
- Respect `prefers-reduced-motion` and provide an equivalent static experience.

### What Falls Outside the Approved Direction?

Avoid neon-black UI, gaming or combative competition aesthetics, excessive glassmorphism, saturated gradient headings in every section, robots, brain imagery, and oversized generic AI symbols. Also avoid covering the entire page with repetitive rows of identical cards that fail to tell a clear story.

**The landing page must translate the product identity into an independent introductory journey.** Use top navigation and a narrative sequence suited to new visitors; the sidebar and full session tools belong to the application.

---
## 9. Landing Page Concept and Section Sequence

The proposed journey is: **Understand the idea ← See it work in an example ← Discover the benefits ← Understand your role ← Open the workspace.**

### 9.1 Top Navigation

Show the project name with its small brand mark, followed by links for Features, How it works, Example, and FAQ, plus an Open workspace button. Navigation can remain sticky with a light background and subtle border while scrolling.

On mobile, keep navigation simple, touch-friendly, and focused on making the primary action easy to reach.

### 9.2 Hero

Suggested composition: a short centered headline, a description, two buttons, and then a large product scene with a few meaningful elements around it. The pearl is a subtle brand element; the debate preview is what explains the product.

**Suggested content:**

Eyebrow:

> A workspace for thoughtful debates

Headline:

> Space for every voice.  
> Clarity for every debate.

Description:

> Follow a two-person English debate with live transcription, suggested moderation alerts and a source-linked review — while the human moderator stays in control.

Primary CTA:

> Open workspace

Secondary CTA:

> Explore an example

Supporting line:

> English conversations · Two speakers · Human-led moderation

**Inside the product scene:** Show a clear debate question, two turns attributed to the respective voices, a moment worth reviewing, and a small indication that an argument map and report are available. Do not display every feature in full detail inside the hero.

### 9.3 The Problem and the Value

Suggested headline:

> Follow the ideas without losing the thread.

Description:

> Keep track of what was said, notice moments worth reviewing and return to the source when the conversation needs a closer look.

An editorial composition could combine short copy with a visual path from Conversation to Moments to review to Session report.

### 9.4 Interactive Example That Demonstrates the Value

This is the most important interactive element after the hero. Show a short scripted debate with tabs or buttons to select **Topic drift**, **Personal attack**, and **Argument trail**. Selecting a state changes the visible content and reveals why it needs review, along with a link to the source turn.

Clearly label this section **Scripted example** or **Interactive preview**. The scenario is illustrative content within the landing page; it must not imply that the microphone is active or that any numbers result from live analysis of a visitor's speech.

### 9.5 Features in Three Main Scenes

Organize features around the user's journey rather than nine identical tiles:

1. **During the conversation:** Transcript, automatic speaker detection, and alerts, shown in a wide room/workspace view.
2. **See the structure:** The argument trail and participation measurements, arranged as two complementary visuals.
3. **After the debate:** Report, source links, assessment, and export, supported by a clear report preview.

Local storage, typed input, and speaker correction can appear as a compact strip of supporting capabilities.

### 9.6 How It Works

Three steps are enough:

| Step | Title | Suggested copy |
|---|---|---|
| 01 | Set the question | Choose one clear discussion topic and prepare two speakers. |
| 02 | Start the conversation | Record the debate and follow its transcript, participation and suggested alerts. |
| 03 | Review with context | Inspect the source turns, explore the argument trail and export your session. |

### 9.7 Moderator Control and Transparency

Show an alert alongside its context and buttons for Reviewed and Dismissed, followed by a separate Correct / Incorrect assessment. The scene does not need to display technical configuration details.

Headline:

> You make the call.

Description:

> Inspect the context, review the suggestion and record your assessment. Every decision stays with the moderator.

A brief note can explain that argument-analysis and topic-relevance features are experimental and that referenced evidence is not verified.

### 9.8 Use Cases

Three simple examples are enough: Classroom debates, Debate club practice, and Moderated discussions. Present them as possible uses with original visual assets, without organizational logos or fabricated testimonials.

### 9.9 Frequently Asked Questions

Use the ready-made answers in Section 12. Showing five to seven essential questions is enough, with clear explanations of English-language support, the two-speaker limit, the human role, and audio processing.

### 9.10 Final CTA and Footer

Headline:

> Give your next debate a clearer record.

Description:

> Bring two perspectives, set one question and leave with a conversation you can revisit.

Include an Open workspace button and a link back to the on-page example. The footer may show the project name and describe it as an experimental academic project. Include only links with real destinations; do not add placeholder legal, contact, or pricing pages.

### Simplified Page Flow Diagram

```text
┌─────────────────────────────────────────────────────────┐
│ Brand        Features  How it works  FAQ   Open workspace│
├─────────────────────────────────────────────────────────┤
│                    Small pearl                          │
│              Space for every voice.                     │
│              Clarity for every debate.                  │
│             Description + two clear CTAs                │
│                                                         │
│    ┌────────── A focused product preview ───────────┐    │
│    │ Topic · Two voices · Transcript · Review cue   │    │
│    └───────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────┤
│ The problem and the value                               │
│ Interactive scripted example                            │
│ Live conversation → Argument trail → Session report     │
│ Three steps                                             │
│ Human review and transparency                           │
│ Use cases · FAQ                                         │
│ Final CTA · Footer                                      │
└─────────────────────────────────────────────────────────┘
```

This sequence is a content reference. You may combine adjacent sections if it creates a better rhythm, provided the core features remain explained and the primary action stays clear.

---

## 10. Ready-to-Use Scenario for the Interactive Example

**Developer note:** The following example is scripted for illustration. When showing it on the landing page, label it Scripted example. Do not claim these states or numbers are live results from the model.

Question:

> Should schools require students to wear uniforms?

| Turn | Speaker | Text |
|---|---|---|
| 01 | A | School uniforms can reduce pressure to buy expensive clothes. |
| 02 | B | I disagree because a uniform can cost more than clothes families already own. |
| 03 | A | What evidence supports that claim about uniform costs? |
| 04 | B | You are a stupid idiot. |
| 05 | A | The uniform policy could protect families from unexpected costs. |
| 06 | B | My neighbour is learning to play the saxophone. |
| 07 | A | The saxophone in his band needs a new mouthpiece. |

**Argument trail state:** Show 01 as a Claim, 02 as a Rebuttal with a reason and a tentative link to 01, and 03 as a question requesting evidence. Label the link May challenge turn 01; clicking it highlights the first turn.

**Personal attack state:** Highlight 04 and show Possible personal attack. Clicking Review context reveals 03, 04, and 05. If Reviewed / Dismissed buttons work in the preview, update the state only inside the example and provide Reset example.

**Topic drift state:** Highlight the progression to 06 and 07 with the original question displayed above them, then show Topic drift. The concept being demonstrated is a sustained move toward a side topic, with a human reviewing the context.

**Report state:** Show the claim from 01, the disagreement from 02, and the question from 03 with No answer linked, along with references that open the original turns within the example.

You may show illustrative participation figures such as A = 1:32 and B = 1:08, or approximately 58% and 42%. These are mockup figures, not results calculated from the written turns above or measured from their characters. Place them in a clearly labeled preview, or omit timing figures if that makes the example easier to understand.

Do not add an Evidence verified or Debate winner badge to the scene. All visuals must remain consistent with the product's actual limitations.

## 11. Interaction and Visitor Experience Requirements

- Every CTA must lead to a specific, understandable result.
- Explore an example should either scroll to and activate the on-page example or open the workspace where the prepared example is available. Choose one behavior and implement it clearly.
- Selecting a state within the example must change the content and highlighting without reloading the page.
- Clicking a turn number must reveal and highlight that turn in the preview; a decorative arrow is not enough.
- Example tabs and review buttons must be keyboard-accessible and show a visible selected state.
- Main content, headings, and action buttons must work even when WebGL fails or motion is disabled.
- Do not ask for microphone permission when the landing page loads. Real audio recording must begin only after an explicit user action in an actually functional recording experience.
- Do not display Start recording as though it works if the page is only an interactive mockup. An Open live room button may instead link to a real destination within the application.
- On mobile, stack scenes vertically and prioritize copy over decoration. Do not make horizontal dragging necessary to understand the argument map.
- Use comfortable touch targets, visible focus states, adequate contrast, and clear accessible names for icon-only buttons.
- Load secondary Three.js elements progressively with a static fallback so they do not delay the first screen.

---

## 12. Frequently Asked Questions and Ready-to-Use Copy

### What does Where’s your argument? do?

> It helps a human moderator follow a two-person English debate through live transcription, suggested personal-attack and topic-drift alerts, an argument trail and a source-linked session report.

### Do I have to select the speaker every time?

> During a recording, speaker labels are detected automatically. You can correct a recorded turn if its label is wrong or unconfirmed. Typed turns are assigned manually.

### Does it decide who wins?

> The moderator makes the decisions. The workspace offers suggestions and source context to support that review.

### Does it check facts or verify evidence?

> Argument roles and links are suggestions. References to evidence are not fact-checked or independently verified.

### Which conversations does the current version support?

> The current prototype is designed for two speakers taking turns in English through a shared microphone, with a human moderator following the workspace.

### What happens to microphone audio?

> During recording, audio is streamed to AssemblyAI for transcription and speaker labeling. The current app analyzes the resulting text locally and saves session records on the computer running the service.

Do not promise anything about how AssemblyAI retains or deletes audio without checking the actual terms and account settings. Local storage within our project does not mean that all audio processing happens locally.

### Can I export the session?

> You can download a Markdown report, export the complete session as JSON and export saved moderator assessments as JSONL.

### Does feedback retrain the model immediately?

> Assessments are saved for future evaluation and training. They do not change the model immediately.

## 13. Concise Copywriting Guide

Prioritize clear action verbs: Follow, Review, Explore, Return, Export. Use language that helps visitors picture what they will do and demonstrates the benefit of each capability.

| Appropriate wording | Wording that exceeds the project's capabilities |
|---|---|
| Suggested moderation alerts | Detects every harmful statement |
| Automatic speaker labels | Always knows exactly who is speaking |
| Source-linked argument suggestions | Fully understands and scores every argument |
| Measured speaking time | Proven fairness score |
| Questions without a linked answer | Detects every unanswered question |
| English debate workspace | Supports every language and meeting size |
| Assessments for future evaluation | Learns instantly from your feedback |
| Review possible personal attacks | Eliminates bias and toxicity |

Do not make model names and training steps the main landing page copy. A simple mention of NLP or speech transcription is sufficient if it helps visitors understand the product. The next section provides the technical background needed for implementation.

---

## 14. Brief Technical Background for the Designer and Developer

Current workflow:

```text
Microphone
    ↓
AssemblyAI STT 3.7 Realtime
    ↓ text + speaker labels + word timestamps
Local moderation service
    ├─ Personal-attack classification
    ├─ Topic relevance with bounded context
    ├─ Tentative argument roles and semantic links
    ├─ Speaking-time aggregation
    └─ Session report + local persistence + feedback
    ↓
Human moderator workspace
```

- The current frontend uses React + TypeScript + Vite, with Three.js for the pearlescent visual presence and Lucide for icons.
- The backend uses Python / FastAPI and connects audio to real-time transcription over WebSocket.
- The personal-attack detector currently deployed in the application is LinearSVC with score calibration. Topic relevance and semantic links use MiniLM.
- Other training experiments exist, but do not present DistilBERT as the model currently deployed in the application.
- Sessions are stored locally in SQLite. The current workflow has no account registration, subscriptions, or team invitations.
- The marketing page does not need to call any models or AssemblyAI to run its scripted example.

### Connecting the Landing Page to the Application

The application's current local URL is `http://127.0.0.1:7863/`. This address refers to the computer running the project and will not automatically work for a friend or an internet visitor.

Current frontend routes use URL hashes:

| Destination | Route |
|---|---|
| Overview | `/#home` |
| My debates | `/#library` |
| Create session | `/#new` |
| Live room | `/#room` |
| Review and report | `/#review` |

Make the application URL a single configurable value, such as `APP_URL`. The Open workspace button can link to `APP_URL`, or the Start a debate button can link to `APP_URL + '#new'` once the base URL format is standardized. The real application URL will be inserted when the product is deployed.

**Important when implementing the landing page in the same repository:** The current application uses hash-based navigation, so landing page anchors such as `#features` must be kept separate from the application's router. Agree on a distinct landing page path or a separate build output before integration. Do not assume `/app` or `/demo` are existing routes.

There is no `#example` link that automatically creates an example session. Inside the application, an Explore an example button creates the prepared session. The landing page's interactive example can instead use local static data, which is the preferred option for a quick explanation without depending on the server or microphone.

The landing page implementer does not need an AssemblyAI API key. Do not include keys or secrets in page files, images, examples, or published browser code.

### Reference Files If the Repository Is Available

Everything necessary for the design is included in this document. The following are additional references for someone who also receives the repository:

| File | Contents |
|---|---|
| `frontend/src/styles.css` | Current colors, fonts, surfaces, buttons, and UI styling |
| `frontend/src/Presence.tsx` | The 3D pearl and its visual fallback |
| `frontend/src/main.tsx` | Screens and the session creation and review flow |
| `frontend/src/VoiceConsole.tsx` | Recording states and audio display |
| `frontend/src/SessionInsights.tsx` | Participation, argument map, report, and alert assessment |
| `frontend/src/types.ts` | Feature labels and display data types |
| `README.md` | Setup instructions, technical background, and evaluation limitations |

Do not use real user sessions, recordings, or personal outputs as landing page assets. Use the scripted example in this document or clearly labeled original mockups. If screenshots of the application are needed later, capture them from a dedicated demo session.

---

## 15. Landing Page Handoff Deliverables

1. A responsive mobile and desktop page that reflects the visual identity specified in this document.
2. Content explaining debate moderation, automatic speaker detection, alerts, the argument map, participation, reports, and the moderator's role.
3. One compelling original product preview and an understandable interactive example clearly labeled as a simulation.
4. Functional actions and links, with the application URL configured in one place.
5. Accessibility, reduced-motion support, and a fallback for the 3D element.
6. Properly licensed assets, fonts, and icons, plus maintainable implementation.
7. Short instructions for running the page, changing `APP_URL`, and building a production release.

### Quick Acceptance Checklist

- [ ] Visitors understand from the first screen that this is an assistant for a human moderator of a live, two-person debate.
- [ ] The human role and ability to trace observations to their sources remain clear.
- [ ] The design is light and calm, with restrained lavender and dark primary buttons.
- [ ] Fonts and brand identity match the application, with comfortable page typography.
- [ ] Interactions demonstrate real value, such as opening a source turn or changing an example state.
- [ ] All displayed features match the current version and its documented limits.
- [ ] There are no fabricated testimonials, accuracy percentages, customers, or subscription plans.
- [ ] The example does not suggest live recording or nonexistent real-world data.
- [ ] The copy and primary action remain visible even if the 3D scene does not load.
- [ ] Every button has real functionality or a clear route to the application.

## 16. A Direct Message to the Implementer

We want visitors to feel that this page represents a clear, thoughtfully designed product. First understand the moderator's story: the moderator listens to two voices, follows the ideas, notices moments that may need intervention, and returns to an organized record afterward. Let the page tell that story through copy, scenes, and interaction.

When deciding between extra decoration and a scene that demonstrates an actual capability, prioritize the product scene. When writing a marketing promise, connect it to a feature that users can actually find after clicking Open workspace. There is room for creativity in the composition, motion, and presentation, as long as it stays within the visual identity documented here.
