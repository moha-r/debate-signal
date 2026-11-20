"""Candidate relevance monitor with bounded, directly grounded conversation anchors."""

from collections import deque
import re

import numpy as np

from topic_relevance import TopicMonitor, is_conversation_management, topic_content


class BoundedTopicMonitor(TopicMonitor):
    """Context survives acknowledgements but expires and cannot reinforce itself forever."""

    def __init__(self,topic,threshold,context_window=4,link_threshold=.3,encoder=None):
        super().__init__(topic,threshold,backend="minilm",use_context=False,encoder=encoder)
        if context_window not in (2,3,4) or not 0 < link_threshold < 1:
            raise ValueError("Use a context window of 2–4 turns and a link threshold between zero and one")
        self.context_window=context_window
        self.link_threshold=link_threshold
        self.history=deque(maxlen=context_window)

    def process(self,text):
        if not isinstance(text,str):
            raise TypeError("Utterances must be strings")
        text=re.sub(r"\s+"," ",text).strip()
        normalized=re.sub(r"[^\w\s]","",text.casefold()).strip()
        management=is_conversation_management(text)
        if not normalized or management:
            self.history.append(None)
            result={"state":"unclear","score":None,"direct_score":None,"used_context":False,
                    "alert":False,"off_topic_count":self.off_topic_count}
            if management:
                result["reason"]="conversation_management"
            return result
        vector=self.encoder.encode(topic_content(text),normalize_embeddings=True)
        direct=float(np.dot(self.topic_vector,vector))
        score=direct
        used_context=False
        if direct < self.threshold and not self.alert_active:
            for anchor in self.history:
                if anchor is None:
                    continue
                link=float(np.dot(vector,anchor["vector"]))
                if link < self.link_threshold:
                    continue
                contextual=self.similarity(anchor["text"]+" "+text)
                if contextual > score:
                    score=contextual
                    used_context=True
        state="on_topic" if score >= self.threshold else "off_topic"
        alert=False
        if state=="on_topic":
            self.off_topic_count=0
            self.alert_active=False
        else:
            self.off_topic_count+=1
            alert=self.off_topic_count>=2 and not self.alert_active
            self.alert_active=self.alert_active or alert
        # Only directly related turns become anchors. Inherited relevance cannot renew the chain.
        self.history.append({"text":text,"vector":vector} if direct>=self.threshold else None)
        self.previous_text=text
        self.previous_relevant=direct>=self.threshold
        return {"state":state,"score":score,"direct_score":direct,"used_context":used_context,
                "alert":alert,"off_topic_count":self.off_topic_count}
