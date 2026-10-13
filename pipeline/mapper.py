def map_speakers_dominance(turns: list) -> dict:
    """Audio-only fallback: podcasts follow a power-law — the host/dominant
    voice gets Camera 1, everyone else Camera 2. Use --swap if a guest
    out-talks the host."""
    print("  ┌─ SPEECH-DOMINANCE MAPPING")
    speaker_totals = {}
    for t in turns:
        speaker_totals[t["speaker"]] = speaker_totals.get(t["speaker"], 0.0) + t["duration"]

    if not speaker_totals:
        print("  └─ WARNING: no speakers detected!")
        return {}

    ranked = sorted(speaker_totals.items(), key=lambda x: x[1], reverse=True)
    mapping = {ranked[0][0]: 1}
    for spk, _ in ranked[1:]:
        mapping[spk] = 2

    for spk, total in ranked:
        print(f"  │ {spk}: {total:8.1f}s speech -> Camera {mapping[spk]}")
    print("  └─ dominant speaker assigned to Camera 1")
    return mapping


def apply_swap(mapping: dict) -> dict:
    """Flips every camera assignment (1<->2)."""
    print("  ⇄ --swap active: reversing all camera assignments")
    return {spk: (2 if cam == 1 else 1) for spk, cam in mapping.items()}
