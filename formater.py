import re
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

# Pasuje do: [H:MM:SS], [HH:MM:SS AM], [HH:MM:SS PM] (AM/PM opcjonalne, case-insensitive)
TS_RE = re.compile(r'\[(\d{1,2}):([0-5]\d):([0-5]\d)(?:\s*(AM|PM))?\]', re.IGNORECASE)

def parse_to_seconds(h, m, s, ampm):
    """Zwraca sekundy od północy (0..86399), uwzględnia AM/PM (12 AM=0h, 12 PM=12h)."""
    h = int(h); m = int(m); s = int(s)
    if ampm:
        ampm = ampm.upper()
        h = h % 12
        if ampm == "PM":
            h += 12
    return h*3600 + m*60 + s

def format_hms(total_seconds):
    """Zwraca H:MM:SS bez wiodącego zera w godzinie."""
    h = total_seconds // 3600
    rem = total_seconds % 3600
    m = rem // 60
    s = rem % 60
    return f"{h}:{m:02d}:{s:02d}"

def main():
    root = tk.Tk()
    root.withdraw()

    in_path = filedialog.askopenfilename(
        title="Wybierz plik z logiem",
        filetypes=[("Pliki tekstowe", "*.txt;*.log"), ("Wszystkie pliki", "*.*")]
    )
    if not in_path:
        return

    base, ext = os.path.splitext(in_path)
    out_path = f"{base}_timer{ext or '.txt'}"

    day_offset = 0              # 0, 86400, 172800, ...
    base_abs_seconds = None     # absolutny czas pierwszego stempla
    prev_abs_seconds = None
    changed = 0
    day_rollovers = 0

    try:
        with open(in_path, "r", encoding="utf-8", errors="replace") as fin, \
             open(out_path, "w", encoding="utf-8", newline="") as fout:

            for line in fin:
                m = TS_RE.search(line)
                if not m:
                    fout.write(line)
                    continue

                hh, mm, ss, ampm = m.groups()
                in_seconds = parse_to_seconds(hh, mm, ss, ampm)

                abs_seconds = in_seconds + day_offset

                # Cofnięcie czasu względem poprzedniej linii => nowa doba
                if prev_abs_seconds is not None and abs_seconds < prev_abs_seconds:
                    day_offset += 24 * 3600
                    abs_seconds = in_seconds + day_offset
                    day_rollovers += 1

                if base_abs_seconds is None:
                    # Pierwsza linia staje się T0 (0:00:00), niezależnie czy AM/PM.
                    base_abs_seconds = abs_seconds

                prev_abs_seconds = abs_seconds
                delta = abs_seconds - base_abs_seconds

                replacement = f"[{format_hms(delta)}]"
                # Podmień tylko pierwszy timestamp w linii
                new_line = TS_RE.sub(replacement, line, count=1)
                fout.write(new_line)
                changed += 1

    except Exception as e:
        messagebox.showerror("Błąd", f"Przetwarzanie nie powiodło się:\n{e}")
        return

    messagebox.showinfo(
        "Gotowe",
        f"Zapisano plik z timerem:\n{out_path}\n\n"
        f"Przeliczono wierszy: {changed}\n"
        f"Wykryte przejścia do nowej doby: {day_rollovers}"
    )

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Wystąpił błąd: {e}", file=sys.stderr)
        input("Naciśnij Enter, aby zamknąć...")
