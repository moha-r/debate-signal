"""Text-first Gradio workspace for the human conversation moderator."""

from datetime import datetime
import html

import gradio as gr

from moderation_session import analyze_turn, new_session, review_alert


CSS = """
.gradio-container {max-width: 1440px !important; background: #f5f7fc; color: #172344;}
.workspace-panel .prose, .turn p, .alert p, .alert-head, .session-line span {color: #172344 !important;}
#masthead {padding: 24px 4px 20px; border-bottom: 1px solid #d7dfef; margin-bottom: 16px;}
#masthead h1 {font-family: 'Bricolage Grotesque', 'Arial', sans-serif; font-size: 34px; line-height: 1.1; margin: 0;}
#masthead p {color: #52617d; margin: 7px 0 0; font-size: 14px;}
.workspace-panel {background: #fff; border: 1px solid #d7dfef; border-radius: 16px; padding: 18px !important;}
.conversation {height: 390px; overflow-y: auto; padding-right: 5px;}
.turn {display: grid; grid-template-columns: 44px 1fr; gap: 12px; margin: 0 0 18px;}
.speaker {width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; border-radius: 11px; font-weight: 700; background: #e7eefb; color: #305a96;}
.speaker.b {background: #efe9ff; color: #6950a0;}
.turn-meta {font-family: 'IBM Plex Mono', monospace; color: #66718a; font-size: 11px; margin-bottom: 6px;}
.turn p {margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6;}
.empty {padding: 45px 16px; color: #66718a; line-height: 1.7;}
.queue {min-height: 230px; max-height: 520px; overflow-y: auto;}
.alert {border: 1px solid #e6cda5; border-left: 4px solid #ad6d12; background: #fffbf2; border-radius: 10px; padding: 14px; margin-bottom: 12px;}
.alert.attack {border-color: #e7bfc8; border-left: 4px solid #a63758; background: #fff7f9;}
.alert.reviewed {opacity: .65; background: #f5f7fc; border-color: #d7dfef; border-left-color: #8390aa;}
.alert-head {display: flex; gap: 10px; justify-content: space-between; font-weight: 650; font-size: 13px;}
.alert p {line-height: 1.5; margin: 10px 0 8px; overflow-wrap: anywhere; white-space: pre-wrap;}
.alert small {color: #59657b;}
.session-line {display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; font-size: 13px; line-height: 1.6;}
.session-line strong {color: #263e8e;}
button:focus-visible, textarea:focus-visible {outline: 3px solid #8497f0 !important; outline-offset: 3px;}
@media(max-width: 700px) {.conversation {height: 300px;} #masthead h1 {font-size: 28px;}}
"""
HEAD = '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=IBM+Plex+Mono&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">'


def relative_time(session, timestamp):
    elapsed = max(0, int((datetime.fromisoformat(timestamp) - datetime.fromisoformat(session["started_at"])).total_seconds()))
    return f"{elapsed // 60:02d}:{elapsed % 60:02d}"


def render_session(session):
    if session is None:
        return (
            '<div class="session-line">Set the topic and start a session.</div>',
            '<div class="conversation empty">Completed turns from speakers A and B will appear here.</div>',
            '<div class="queue empty">Alerts for the moderator will appear here.</div>',
            gr.Dropdown(choices=[], value=None, interactive=False),
        )
    escape = html.escape
    pending = [a for a in session["alerts"] if a["status"] == "Pending"]
    status = (
        f'<div class="session-line"><strong>{escape(session["topic"])}</strong>'
        f'<span>{len(session["turns"])} turns · {len(pending)} pending alerts</span></div>'
    )
    cards = []
    for turn in session["turns"]:
        labels = []
        if turn["personal_attack"]:
            labels.append("Possible personal attack")
        if turn["topic"]["alert"]:
            labels.append("Topic drift")
        details = f' · {escape(" / ".join(labels))}' if labels else ""
        cards.append(
            f'<article class="turn"><div class="speaker {turn["speaker"].lower()}">{turn["speaker"]}</div>'
            f'<div><div class="turn-meta">{relative_time(session, turn["time"])} · Turn {turn["number"]}{details}</div>'
            f'<p>{escape(turn["text"])}</p></div></article>'
        )
    transcript = '<div class="conversation">' + (
        "".join(cards) or '<div class="empty">Choose a speaker and enter the first turn below.</div>'
    ) + "</div>"
    alerts = []
    for item in reversed(session["alerts"]):
        style = "attack" if item["kind"] == "Personal attack" else "drift"
        if item["status"] != "Pending":
            style += " reviewed"
        alerts.append(
            f'<article class="alert {style}"><div class="alert-head"><span>{item["id"]} · {item["kind"]}</span>'
            f'<span>{item["status"]}</span></div><p>{escape(item["text"])}</p>'
            f'<small>Speaker {item["speaker"]} · Turn {item["turn"]} · {relative_time(session, item["time"])}</small></article>'
        )
    queue = '<div class="queue">' + (
        "".join(alerts) or '<div class="empty">No alerts in this session. Keep following the discussion.</div>'
    ) + "</div>"
    choices = [(f'{a["id"]} · {a["kind"]} · Speaker {a["speaker"]}', a["id"]) for a in pending]
    return status, transcript, queue, gr.Dropdown(
        choices=choices, value=pending[0]["id"] if pending else None, interactive=bool(pending)
    )


def start_session(topic):
    try:
        session = new_session(topic)
    except ValueError as error:
        raise gr.Error(str(error)) from error
    return session, *render_session(session), "", {}, "", ""


def submit_turn(session, speaker, text):
    try:
        updated = analyze_turn(session, speaker, text)
    except ValueError as error:
        raise gr.Error(str(error)) from error
    turn = updated["turns"][-1]
    probability = turn["attack_probability"]
    topic = turn["topic"]
    descriptions = {
        "on_topic": "Related to the discussion",
        "off_topic": "Away from the discussion",
        "unclear": "Not enough topic content",
    }
    topic_text = descriptions[topic["state"]]
    if topic["score"] is not None:
        topic_text += f' · Similarity {topic["score"]:.2f}'
    if topic["used_context"]:
        topic_text += " · Previous turn considered"
    return (
        updated, *render_session(updated), turn["processed_text"],
        {"Personal attack": probability, "No personal attack": 1 - probability},
        topic_text, "",
    )


def act_on_alert(session, alert_id, decision):
    try:
        updated = review_alert(session, alert_id, decision)
    except ValueError as error:
        raise gr.Error(str(error)) from error
    return updated, *render_session(updated)


def build_app():
    empty = render_session(None)
    with gr.Blocks(title="DebateSignal · Moderator workspace") as demo:
        state = gr.State(None)
        gr.HTML(
            '<header id="masthead"><h1>DebateSignal</h1>'
            '<p>Moderator workspace · English discussion</p></header>'
        )
        with gr.Row(equal_height=False):
            with gr.Column(scale=7, elem_classes="workspace-panel"):
                with gr.Row():
                    topic_input = gr.Textbox(
                        label="Discussion topic", value="Should schools require students to wear uniforms?",
                        placeholder="Enter the question being debated", scale=5,
                    )
                    start = gr.Button("Start / reset session", variant="secondary", scale=2)
                status = gr.HTML(empty[0])
                transcript = gr.HTML(empty[1])
                speaker = gr.Radio(["A", "B"], value="A", label="Speaker")
                utterance = gr.Textbox(
                    label="Completed turn", lines=3,
                    placeholder="Type what the participant said, then add the turn.",
                )
                send = gr.Button("Analyze and add turn", variant="primary")
            with gr.Column(scale=5, elem_classes="workspace-panel"):
                gr.Markdown("### Moderator alerts")
                queue = gr.HTML(empty[2])
                selection = gr.Dropdown(choices=[], label="Alert to review", interactive=False)
                with gr.Row():
                    reviewed = gr.Button("Mark reviewed", variant="secondary")
                    dismissed = gr.Button("Dismiss", variant="secondary")
                gr.Markdown("Alerts suggest human review. Topic monitoring is experimental.")
                with gr.Accordion("Latest turn analysis", open=True):
                    probabilities = gr.Label(label="Personal attack probabilities", num_top_classes=2)
                    topic_result = gr.Textbox(label="Topic relevance", interactive=False)
                    processed = gr.Textbox(label="Text after preprocessing", lines=2, interactive=False)
        shared = [state, status, transcript, queue, selection]
        all_outputs = [*shared, processed, probabilities, topic_result, utterance]
        event_options = {"concurrency_id": "moderation", "concurrency_limit": 1}
        start.click(start_session, inputs=topic_input, outputs=all_outputs, **event_options)
        send.click(submit_turn, inputs=[state, speaker, utterance], outputs=all_outputs, **event_options)
        reviewed.click(
            lambda s, a: act_on_alert(s, a, "Reviewed"),
            inputs=[state, selection], outputs=shared, **event_options,
        )
        dismissed.click(
            lambda s, a: act_on_alert(s, a, "Dismissed"),
            inputs=[state, selection], outputs=shared, **event_options,
        )
    return demo


if __name__ == "__main__":
    build_app().queue().launch(
        server_name="127.0.0.1", server_port=7860,
        css=CSS, head=HEAD, theme=gr.themes.Base(
            primary_hue="indigo", neutral_hue="slate", font=["Inter", "Arial", "sans-serif"]
        ).set(
            body_background_fill_dark="#f5f7fc",
            body_text_color_dark="#172344",
            body_text_color_subdued_dark="#52617d",
            block_background_fill_dark="#ffffff",
            block_border_color_dark="#d7dfef",
            block_label_text_color_dark="#52617d",
            block_label_background_fill_dark="#f5f7fc",
            block_title_text_color_dark="#172344",
            input_background_fill_dark="#f8faff",
            input_border_color_dark="#d7dfef",
            input_placeholder_color_dark="#71809e",
            button_secondary_background_fill_dark="#edf1f9",
            button_secondary_text_color_dark="#263e8e",
        ),
    )
