"""Bundled Mara and Len experiment seed."""

FIXTURE = {
    "id": "mara-len", "version": 1, "name": "The chair and the bowl",
    "actors": [
        {"id": "mara", "name": "Mara", "goals": ["understand Len's leaving"],
         "conceptual_model": {"version": 1, "concepts": ["care", "repair"]}},
        {"id": "len", "name": "Len", "goals": ["leave without explanation"],
         "conceptual_model": {"version": 1, "concepts": ["care", "avoidance"]}},
    ],
    "entities": [
        {"id": "kitchen", "name": "Kitchen", "kind": "place"},
        {"id": "chair", "name": "Rocking chair", "kind": "object", "motif": True},
        {"id": "bowl", "name": "Blue bowl", "kind": "object", "motif": True},
        {"id": "note", "name": "Folded note", "kind": "object"},
        {"id": "bag", "name": "Travel bag", "kind": "object"},
    ],
    "initial_facts": ["Mara and Len share the kitchen"],
    "style": {"focalizer": "mara", "distance": "close", "rhythm": "restrained",
              "explanation_ceiling": "low"},
}

CONTRACT = {
    "id": "bounded-epiphany", "version": 1,
    "required_story_conditions": ["Len leaves", "Mara finds the note"],
    "forbidden_story_conditions": ["Len's exact motive is known"],
    "facts_that_must_be_clear": ["Len leaves"],
    "questions_that_must_remain_open": ["Was the repair care or avoidance?"],
    "prose_bounds": {"min_words": 700, "max_words": 1100},
    "strain_threshold_bp": 6500,
}

STORY = [
    {"title": "Len repairs the chair", "kind": "action", "actor_ids": ["len"], "entity_ids": ["chair"],
     "description": "Len tightened the chair's loose joint before Mara came home.",
     "world_facts": ["Len repairs the chair"], "strain_bp": 700},
    {"title": "Len replaces the bowl", "kind": "action", "actor_ids": ["len"], "entity_ids": ["bowl"],
     "description": "He set the chipped bowl back in its usual place.",
     "world_facts": ["Len replaces the bowl"], "strain_bp": 900},
    {"title": "Len writes a note", "kind": "action", "actor_ids": ["len"], "entity_ids": ["note"],
     "description": "The note remained folded beneath the bowl.",
     "world_facts": ["Len writes a note"], "strain_bp": 1300},
    {"title": "Len gives an ordinary reason", "kind": "utterance", "actor_ids": ["len"], "observed_by": ["mara"],
     "description": "He told Mara he would be late.", "world_facts": ["Len gives an ordinary reason"],
     "interpretations": [{"observer_id": "mara", "model_version": 1, "claim": "The repairs are care", "confidence_bp": 7800}],
     "strain_bp": 1400},
    {"title": "Len leaves; the chair rocks", "kind": "action", "actor_ids": ["len"], "entity_ids": ["chair", "bag"],
     "observed_by": ["mara"], "description": "After Len left, the chair rocked once in the empty kitchen.",
     "world_facts": ["Len leaves"], "strain_bp": 2600},
    {"title": "Mara finds the note", "kind": "observation", "actor_ids": ["mara"], "observed_by": ["mara"],
     "access_path": "perception", "entity_ids": ["note", "bowl"],
     "description": "Mara lifted the bowl and found the folded note.",
     "world_facts": ["Mara finds the note"], "strain_bp": 4200},
    {"title": "The note names deferred departures", "kind": "observation", "actor_ids": ["mara"],
     "observed_by": ["mara"], "access_path": "perception", "entity_ids": ["note"],
     "description": "The note listed dates when Len had almost left before.",
     "world_facts": ["The note lists deferred departures"], "strain_bp": 7400},
    {"title": "Mara remembers the repairs", "kind": "recollection", "actor_ids": ["mara"],
     "observed_by": ["mara"], "entity_ids": ["chair", "bowl"],
     "description": "The mended chair and the replaced bowl returned to Mara as two possible explanations.",
     "strain_bp": 8200},
    {"title": "Mara cannot choose one meaning", "kind": "crisis", "actor_ids": ["mara"],
     "description": "Neither meaning canceled the other.", "strain_bp": 8800,
     "conceptual_revision": {"observer_id": "mara", "concepts": ["care", "avoidance"],
                             "migration_map": {"care": ["care", "avoidance"]},
                             "unresolved_terms": ["care", "avoidance"]},
     "interpretations": [
         {"observer_id": "mara", "model_version": 2, "claim": "The chair repair could be care or avoidance",
          "status": "suspended", "confidence_bp": 5000, "target_story_sequences": [1]},
         {"observer_id": "mara", "model_version": 2, "claim": "The bowl replacement could be care or avoidance",
          "status": "suspended", "confidence_bp": 5000, "target_story_sequences": [2]},
     ]},
    {"title": "Mara moves the bowl", "kind": "action", "actor_ids": ["mara"], "entity_ids": ["bowl"],
     "description": "Mara placed the bowl somewhere it had never stood before.",
     "world_facts": ["Mara moves the bowl"], "strain_bp": 6000},
]

DISCOURSE = [
    {"title": "The rocking chair", "mode": "scene", "story_index": 4,
     "text": "After Len left, the chair rocked once. Mara watched it come to rest.", "cue": ["something has changed"]},
    {"title": "The routine reason", "mode": "scene", "story_index": 3,
     "text": "He had said he would be late. She had believed him, as she had believed the small repairs.",
     "withhold": ["The note lists deferred departures"]},
    {"title": "The partial note", "mode": "scene", "story_index": 5,
     "text": "Under the bowl, a folded note waited. Mara opened it at the kitchen table."},
    {"title": "The repaired chair", "mode": "memory", "story_index": 0,
     "text": "She remembered the chair's loose joint, and how quietly Len had fixed it."},
    {"title": "The replaced bowl", "mode": "memory", "story_index": 1,
     "text": "Then the bowl: the chipped rim turned toward the wall, as always."},
    {"title": "Two meanings held", "mode": "pause", "story_index": 8,
     "text": "She could call it care. She could call it practice for leaving. The bowl stayed between her hands."},
    {"title": "The bowl elsewhere", "mode": "scene", "story_index": 9,
     "text": "Mara moved the bowl to the other side of the table."},
]

CONDITION_SUFFIXES = {
    "C0": [
        {"title": "Mara reads the final line", "kind": "observation", "actor_ids": ["mara"],
         "observed_by": ["mara"], "access_path": "perception", "entity_ids": ["note"],
         "description": "At the bottom, Len had written that he had signed a lease across town.",
         "world_facts": ["Len signed a lease across town"], "strain_bp": 6100},
        {"title": "Mara accepts the new fact", "kind": "decision", "actor_ids": ["mara"],
         "description": "The note settled the question of where Len would go, though it explained little else.",
         "strain_bp": 4800},
        STORY[9],
    ],
    "C1": [
        STORY[7],
        {"title": "Mara revises one belief", "kind": "revision", "actor_ids": ["mara"],
         "description": "She no longer took the repairs as proof that Len meant to stay.",
         "belief_revision": {"observer_id": "mara", "claim": "The repairs are care",
                             "status": "rejected", "confidence_bp": 2700, "evidence_story_sequence": 7},
         "strain_bp": 6400},
        STORY[9],
    ],
    "C2": [
        STORY[7],
        {"title": "Mara admits another possibility", "kind": "revision", "actor_ids": ["mara"],
         "description": "A repair could belong to someone who meant to leave, as well as someone who meant to stay.",
         "modal_revision": {"observer_id": "mara", "add_scenarios": ["care and departure coexist"],
                            "allow_rivals": True},
         "strain_bp": 7200},
        STORY[9],
    ],
}

CONDITION_PAUSES = {
    "C0": "The last line gave her an address and a date. Mara set the note down and looked at the bowl.",
    "C1": "She had mistaken the repairs for a promise. It was a smaller correction than she expected, and still it hurt.",
    "C2": "He could have cared and planned to leave. The two possibilities remained beside each other on the table.",
    "C3": DISCOURSE[5]["text"],
}


def supports_expanded_sample(fixture: dict, story: list[dict]) -> bool:
    """Keep authored expansion off branches whose canon or fixture changed."""
    if {key: value for key, value in fixture.items() if key != "content_hash"} != FIXTURE:
        return False
    defaults = {"description": "", "actor_ids": [], "entity_ids": [], "observed_by": [],
                "world_facts": [], "interpretations": [], "preconditions": [], "strain_bp": 0}
    actual = []
    for event in story:
        actual.append({key: value for key, value in event["payload"].items()
                       if key != "causal_parents" and (key not in defaults or value != defaults[key])})
    variants = [STORY] + [STORY[:7] + CONDITION_SUFFIXES[condition] for condition in ("C0", "C1", "C2")]
    return actual in variants

# The offline demo uses authored prose for the seeded beats. The realizer selects
# a passage only while its matching discourse cue remains unchanged; an author's
# edited cue takes precedence. This also expands projects created before v2.
SAMPLE_PROSE = {
    "The rocking chair": (
        "After Len left, the chair rocked once. Mara watched it come to rest. "
        "He had taken his travel bag through the doorway, but the chair stood "
        "well clear of it. She waited for a second movement, the small answering "
        "rock that would make the first one ordinary. None came. The kitchen was "
        "exactly as he had left it: the blue bowl on the table, the chair angled "
        "toward the window, the light holding on the worn places in the floor. "
        "She put a hand on the chair's back. It was still. Whatever had set it "
        "moving had already finished, and the room offered her no way to ask."),
    "The routine reason": (
        "He had said he would be late. She had believed him, as she had believed "
        "the small repairs. Earlier, the sentence had passed between them without "
        "either of them stopping over it. Now she tried to hear its exact weight: "
        "late for what, and late by how much? The words did not answer. They were "
        "the kind of words people used while reaching for a coat, too familiar "
        "to hold in memory until something else made them strange. Mara could "
        "remember the shape of his voice and the place where she had stood. "
        "She could not remember a promise. That absence seemed important only "
        "after he was gone; she distrusted the timing of her own attention."),
    "The partial note": (
        "Under the bowl, a folded note waited. Mara opened it at the kitchen table. "
        "The paper had been pressed flat beneath the bowl's base, its crease "
        "sharp enough to catch her thumb. She did not read at once. For a moment "
        "she watched the empty space the bowl had covered, as though the table "
        "might keep an impression of the words. Then she turned the page into "
        "the light. Len's narrow hand ran down it in short, careful lines. "
        "She could have read them all at once. Instead she let her eye rest "
        "on the fold and on the blue shadow the bowl cast beside it. She had "
        "lifted the bowl to find something; now that something was in front of "
        "her, she was slow to let it become a sentence."),
    "The repaired chair": (
        "She remembered the chair's loose joint, and how quietly Len had fixed it. "
        "For weeks it had clicked whenever anyone leaned back. Then one evening "
        "Mara came home and the click was gone. She had sat down without testing "
        "it and only noticed the silence after she stood. She had taken that "
        "silence as a kind of tenderness. It had asked for no thanks and made "
        "the room easier to inhabit. Looking at the chair now, she could still "
        "feel that first relief. She could also see how little the repair itself "
        "said. The joint held. Its steadiness was real, even if the meaning she "
        "had set upon it was beginning to shift."),
    "The replaced bowl": (
        "Then the bowl: the chipped rim turned toward the wall, as always. Len "
        "had set it in its place, the blue glaze bright "
        "where the morning light reached. Mara had noticed the gesture because "
        "he never turned the chip outward. She had made a small private story "
        "of that habit, one in which care was proved by remembering a detail "
        "too slight for anyone else to see. The bowl in her hands was the same "
        "weight as before. Its rough edge met her finger in the same place. "
        "Nothing about the object had changed, yet she could no longer look "
        "at it without seeing the effort it took to keep it familiar."),
    "The bowl elsewhere": (
        "Mara moved the bowl to the other side of the table. The motion was "
        "small enough that someone entering the kitchen might not have noticed. "
        "She noticed. From this side the chip faced the window, and the blue "
        "glaze gathered a different strip of light. The chair remained by the "
        "wall; the note lay open where she had left it. She did not put either "
        "one away. She stood for a while with both palms against the table, "
        "allowing the room to stay unsettled. When the chair failed to move "
        "again, she did not take its stillness for an answer. She left the bowl "
        "where she had placed it."),
}

CONDITION_PROSE = {
    "C0": (
        "The last line gave her an address and a date. Len had signed a lease "
        "across town. Mara read the line again, then set the note down and "
        "looked at the bowl. At least one question had become plain: she knew "
        "where he meant to go. The discovery had the hard edges of a fact, "
        "something she could repeat without changing it. It did not reach back "
        "through the chair or the bowl and tell her what either repair had "
        "meant. She could imagine herself saying the address aloud, as if the "
        "sound of it might make the rest of the note easier to bear. Instead "
        "she folded the paper along its old crease. The table held the bowl, "
        "the note, and the one answer she had been given."),
    "C1": (
        "She had mistaken the repairs for a promise. It was a smaller correction "
        "than she expected, and still it hurt. The chair no longer proved that "
        "Len intended to stay; the bowl could not testify for him either. She "
        "had asked those ordinary things to carry more than they could bear. "
        "Mara put the note beside the bowl and tried the sentence again: a "
        "repair is a repair. It did not undo the relief she had felt when the "
        "chair stopped clicking. It did not turn the bowl into a trick. But the "
        "conclusion she had drawn from them had become impossible to hold. She "
        "could let that one belief go without claiming to know what would "
        "replace it."),
    "C2": (
        "He could have cared and planned to leave. The two possibilities "
        "remained beside each other on the table. Mara had been treating them "
        "as rivals, as if one account of Len would cancel the other. The note "
        "did not require that choice. She looked from its dates to the chair, "
        "then to the bowl, letting each thing keep the shape it had always "
        "had. A person might make a room easier for someone and still walk "
        "out of it. She did not know whether that was Len's story. She knew "
        "only that it was a story she had not allowed herself to imagine. The "
        "room seemed wider for a moment, though nothing in it had moved."),
    "C3": (
        "She could call it care. She could call it practice for leaving. The "
        "bowl stayed between her hands. The dates on the note sent her back "
        "through the small acts she had already named: the joint made firm, "
        "the chipped rim turned from view. Each memory remained sharp, but the "
        "word she had used to gather them no longer held in one piece. Care "
        "could not be made to mean only staying. Avoidance could not explain "
        "away the work of fixing a chair. She felt the two readings pressing "
        "against each other without becoming one. It was not that she had "
        "forgotten what happened. She could recall the objects and their places "
        "exactly. What she could not recover was the old certainty that knowing "
        "those details meant knowing what they were for."),
}


def expanded_sample_text(title: str, text: str) -> str | None:
    """Use authored sample prose only for unchanged seeded discourse cues."""
    if title == "Two meanings held":
        for condition, cue in CONDITION_PAUSES.items():
            if text == cue:
                return CONDITION_PROSE[condition]
        return None
    for act in DISCOURSE:
        if act["title"] == title and act["text"] == text:
            return SAMPLE_PROSE.get(title)
    return None
