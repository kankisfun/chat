import os
import json
import re
import tkinter as tk
from tkinter import filedialog

# ----------------------------
# KONFIG (jak w Twoim skrypcie)
# ----------------------------
KEYWORDS = ["xd", "KEKW", "cinema", "sad", "oh", "sus", "kekleo"]
SHOT_DURATION = 30  # seconds
COOLDOWN = 30       # seconds

# Kick emote: [emote:12345:NAME]
EMOTE_RE = re.compile(r"\[emote:(\d+):([^\]]+)\]")


def parse_iso_z(ts: str):
    """
    Kick daje np: '2026-02-18T14:27:24Z'
    Zwraca datetime w UTC.
    """
    from datetime import datetime, timezone

    if not ts or not isinstance(ts, str):
        return None
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(ts).astimezone(timezone.utc)
    except Exception:
        return None


def kick_content_to_plain_text(content: str) -> str:
    """
    Na potrzeby detekcji reakcji:
    - zamieniamy kickowe [emote:..:NAME] na sam tekst NAME z odstępami
      (żeby np. [emote:..:POLICE][emote:..:POLICE] stało się 'POLICE POLICE')
    """
    if content is None:
        return ""

    def repl(m):
        name = m.group(2)
        return f" {name} "

    out = EMOTE_RE.sub(repl, content)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def get_time_difference_sec(t1, t2):
    """
    Różnica w sekundach: t1 - t2
    (t1/t2 to float/int sekundy od startu)
    """
    if t1 is None or t2 is None:
        return 99999
    return float(t1) - float(t2)


def main():
    # Tkinter: wybór pliku Kick JSON
    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Select a Kick chat JSON file",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
    )
    if not file_path:
        print("No file selected. Exiting.")
        return

    # output obok pliku
    out_path = os.path.join(os.path.dirname(file_path), "xd2.txt")

    # wczytaj Kick JSON
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("ERROR: Kick JSON should be an array of messages.")
        return

    # Zbuduj listę rekordów (czas, tekst)
    # Kick: { content, createdAt, userId, username }
    messages = []
    for item in data:
        if not isinstance(item, dict):
            continue
        created = parse_iso_z(item.get("createdAt"))
        if created is None:
            continue
        content = item.get("content", "")
        text = kick_content_to_plain_text(content)
        messages.append((created, text))

    if not messages:
        print("No valid messages with createdAt found.")
        return

    # Sortuj po czasie (na wszelki)
    messages.sort(key=lambda x: x[0])

    # bazowy czas = pierwsza wiadomość
    base_time = messages[0][0]

    # czasy w sekundach od startu
    times = []
    reaction_array = []
    reactions_array = []

    for created, text in messages:
        t = (created - base_time).total_seconds()
        times.append(t)

        # keyword match (case-insensitive)
        if any(k.lower() in text.lower() for k in KEYWORDS):
            reaction_array.append(1)
            reactions_array.append(1)
        else:
            reaction_array.append(0)
            reactions_array.append(0)

    line_count = len(messages)
    print(f"Ok, Kick JSON ma {line_count} wiadomości (valid).")

    # Sliding window: +/- SHOT_DURATION/2
    half = SHOT_DURATION / 2.0

    for i in range(line_count):
        # backward
        j = 0
        while (i - j) >= 0:
            diff = get_time_difference_sec(times[i], times[i - j])
            if diff < half:
                reactions_array[i] += reaction_array[i - j]
                j += 1
            else:
                break

        # forward
        j = 0
        while (i + j) < line_count:
            diff = get_time_difference_sec(times[i + j], times[i])
            if diff < half:
                reactions_array[i] += reaction_array[i + j]
                j += 1
            else:
                break

        if i % 200 == 0 or i == line_count - 1:
            print(f"Analiza: {i+1} / {line_count}")

    highest = max(reactions_array) if reactions_array else 0
    print("Znalazłem wszystkie shoty. Sortowanie...")

    # Zapis
    with open(out_path, "w", encoding="utf-8") as out:
        reaction_moments = 0
        current = highest

        # Kopia robocza, bo będziemy zerować
        work = reactions_array[:]

        # wybieramy od największych pików
        while current > 0:
            for i in range(line_count):
                if work[i] == current:
                    work[i] = 0
                    reaction_moments += 1

                    # zeruj w oknie SHOT_DURATION + COOLDOWN
                    radius = SHOT_DURATION + COOLDOWN

                    # backward clear
                    j = 0
                    while (i - j) >= 0:
                        diff = get_time_difference_sec(times[i], times[i - j])
                        if diff < radius:
                            work[i - j] = 0
                            j += 1
                        else:
                            break

                    # forward clear
                    j = 0
                    while (i + j) < line_count:
                        diff = get_time_difference_sec(times[i + j], times[i])
                        if diff < radius:
                            work[i + j] = 0
                            j += 1
                        else:
                            break

                    # moment = time - half window (jak u Ciebie)
                    reaction_time = times[i] - half
                    if reaction_time < 0:
                        reaction_time = 0

                    # format: days:HH:MM:SS (jak wcześniej)
                    total = int(reaction_time)
                    days = total // 86400
                    rem = total % 86400
                    hh = rem // 3600
                    mm = (rem % 3600) // 60
                    ss = rem % 60

                    formatted = f"{days}:{hh:02d}:{mm:02d}:{ss:02d}"
                    line = f"{reaction_moments}. {formatted} /// Reakcje: {current}"
                    print(line)
                    out.write(line + "\n")

            current -= 1

    print(f"Gotowe. Zapisano: {out_path}")


if __name__ == "__main__":
    main()