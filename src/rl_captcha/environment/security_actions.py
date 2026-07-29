SECURITY_ACTIONS = {
    0: "allow",
    1: "observe",
    2: "captcha_easy",
    3: "captcha_medium",
    4: "captcha_hard",
    5: "honeypot",
    6: "block",
}

ACTION_LABELS = {
    0: "Allow — trusted session, skip CAPTCHA",
    1: "Observe — collect more behavior data, then reassess",
    2: "Easy CAPTCHA — difficulty 1 (3 Bangla words)",
    3: "Medium CAPTCHA — difficulty 2 (4 Bangla words)",
    4: "Hard CAPTCHA — difficulty 3 (5 Bangla words, heavy distortion)",
    5: "Honeypot — fake CAPTCHA that always rejects (trap bots)",
    6: "Block — deny session entirely",
}

NUM_ACTIONS = len(SECURITY_ACTIONS)


def action_to_difficulty(action: int) -> int:
    mapping = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3, 5: 1, 6: 0}
    return mapping.get(action, 1)


def action_name(action: int) -> str:
    return SECURITY_ACTIONS.get(action, "unknown")
