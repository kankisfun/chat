import os
import re
import tkinter as tk
from tkinter import filedialog
from datetime import datetime

KEYWORDS = ["xd", "kekw", "cinema", "sad", "oh", "sus", "sraka"]

SHOT_DURATION = 30
COOLDOWN = 30

EMOTE_RE = re.compile(r"\[emote:(\d+):([^\]]+)\]")
LINE_RE = re.compile(r"\[(.*?)\]\s+[^:]+:\s+(.*)")


def parse_time(ts):
    try:
        return datetime.strptime(ts, "%I:%M:%S %p")
    except:
        return None


def content_to_plain_text(content):

    if content is None:
        return ""

    def repl(m):
        return " " + m.group(2) + " "

    out = EMOTE_RE.sub(repl, content)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def get_time_difference_sec(t1, t2):

    if t1 is None or t2 is None:
        return 99999

    return float(t1) - float(t2)


def main():

    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Select TXT chat file",
        filetypes=[("TXT Files", "*.txt"), ("All Files", "*.*")]
    )

    if not file_path:
        return

    out_path = os.path.join(os.path.dirname(file_path), "xd3.txt")

    messages = []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:

        for line in f:

            m = LINE_RE.match(line)

            if not m:
                continue

            ts = parse_time(m.group(1))
            if ts is None:
                continue

            text = content_to_plain_text(m.group(2))

            messages.append((ts, text))

    if not messages:
        print("No messages parsed.")
        return

    # PIERWSZA WIADOMOŚĆ = 0
    base_time = messages[0][0]

    times = []
    reaction_array = []
    reactions_array = []

    for created, text in messages:

        t = (created - base_time).total_seconds()

        # jeśli przejdzie przez północ
        if t < 0:
            t += 86400

        times.append(t)

        if any(k in text.lower() for k in KEYWORDS):
            reaction_array.append(1)
            reactions_array.append(1)
        else:
            reaction_array.append(0)
            reactions_array.append(0)

    line_count = len(messages)

    print("Parsed:", line_count)

    half = SHOT_DURATION / 2

    for i in range(line_count):

        j = 0
        while (i - j) >= 0:

            diff = get_time_difference_sec(times[i], times[i - j])

            if diff < half:
                reactions_array[i] += reaction_array[i - j]
                j += 1
            else:
                break

        j = 0
        while (i + j) < line_count:

            diff = get_time_difference_sec(times[i + j], times[i])

            if diff < half:
                reactions_array[i] += reaction_array[i + j]
                j += 1
            else:
                break

    highest = max(reactions_array)

    with open(out_path, "w", encoding="utf-8") as out:

        reaction_moments = 0
        current = highest
        work = reactions_array[:]

        while current > 0:

            for i in range(line_count):

                if work[i] == current:

                    work[i] = 0
                    reaction_moments += 1

                    radius = SHOT_DURATION + COOLDOWN

                    j = 0
                    while (i - j) >= 0:

                        diff = get_time_difference_sec(times[i], times[i - j])

                        if diff < radius:
                            work[i - j] = 0
                            j += 1
                        else:
                            break

                    j = 0
                    while (i + j) < line_count:

                        diff = get_time_difference_sec(times[i + j], times[i])

                        if diff < radius:
                            work[i + j] = 0
                            j += 1
                        else:
                            break

                    reaction_time = times[i] - half

                    if reaction_time < 0:
                        reaction_time = 0

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

    print("Saved:", out_path)


if __name__ == "__main__":
    main()