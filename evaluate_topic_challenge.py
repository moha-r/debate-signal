"""Score extra authored conversations using the locked topic policy."""

import json
from pathlib import Path

import pandas as pd

from evaluate_topic_relevance import EmbeddingCache, event_metrics, score_sessions


def main():
    source = json.loads(Path("data/topic_challenge.json").read_text())
    policy = json.loads(Path("results/topic_policy.json").read_text())
    encoder = EmbeddingCache()
    turns, events = score_sessions(
        source["sessions"], policy["threshold"], policy["backend"],
        policy["use_context"], encoder,
    )
    metrics = {
        **event_metrics(turns, events),
        "sessions": len(source["sessions"]),
        "turns": len(turns),
        "provenance": source["provenance"],
        "policy_threshold": policy["threshold"],
    }
    Path("results/topic_challenge_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    turns.to_csv("results/topic_challenge_turns.csv", index=False)
    print(pd.Series(metrics).drop("provenance").to_string())
    print("False alerts or missed off-topic turns")
    problematic = turns[
        (turns["alert"] & turns["reference"].ne("off_topic"))
        | (turns["reference"].eq("off_topic") & turns["state"].ne("off_topic"))
    ]
    print(problematic[["session", "turn", "text", "state", "alert"]].to_string(index=False))


if __name__ == "__main__":
    main()
