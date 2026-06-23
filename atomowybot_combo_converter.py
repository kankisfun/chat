#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import re
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

# ============================================================
# 1) ATOMOWYBOT TXT -> TWITCHDOWNLOADER CHAT.JSON
#    Logika przeniesiona z Atomowybot_chat_converter.
# ============================================================

# Atomowybot format:
# [2:18:59] polawdomu: mniej golda za kill
LINE_RE = re.compile(
    r"^\[(?P<time>\d{1,3}:\d{2}:\d{2})\]\s+(?P<user>[^:]+):\s*(?P<msg>.*)$"
)

# Kick/Atomowy emote format: [emote:37226:KEKW]
EMOTE_RE = re.compile(r"\[emote:(\d+):([^\]]+)\]")

FORCED_STREAMER = {
    "name": "xntentacion",
    "login": "xntentacion",
    "id": 461774409,
}

BUILTIN_TEMPLATE = {
    "FileInfo": {
        "Version": {"Major": 1, "Minor": 4, "Patch": 0},
        "CreatedAt": "",
        "UpdatedAt": "0001-01-01T00:00:00",
    },
    "streamer": {
        "name": "",
        "login": "",
        "id": 0,
    },
    "clipper": None,
    "video": {
        "title": "Atomowybot chat (converted)",
        "description": None,
        "id": "",
        "created_at": "",
        "start": 0,
        "end": 0,
        "length": 0,
        "viewCount": 0,
        "game": "Just Chatting",
        "chapters": [],
    },
    "comments": [],
    "embeddedData": None,
}


def iso_now_local():
    return datetime.now().astimezone().isoformat()


def parse_hms_to_seconds(value: str) -> int:
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def fake_created_at_from_offset(offset_seconds: int) -> str:
    """
    TwitchDownloader chce created_at jako datetime.
    Atomowybot daje tylko czas VOD-a, więc robimy stabilną sztuczną datę.
    Najważniejsze dla renderu jest content_offset_seconds.
    """
    base = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=int(offset_seconds))).isoformat().replace("+00:00", "Z")


def stable_user_id(username: str) -> str:
    """
    Atomowybot nie daje ID użytkownika, więc robimy deterministyczne ID z nicku.
    Dzięki temu ten sam nick ma zawsze to samo _id.
    """
    digest = hashlib.sha1(username.encode("utf-8", errors="ignore")).hexdigest()
    return str(int(digest[:12], 16))


def build_body_and_fragments(content: str):
    if content is None:
        content = ""

    def repl(m):
        name = m.group(2)
        return f" {name} "

    body = EMOTE_RE.sub(repl, content)
    body = re.sub(r"\s+", " ", body).strip()

    return body, [{"text": body, "emoticon": None}], []


def parse_atomowybot_text(text: str, ignored_users=None):
    """
    Zwraca listę:
    {
      "raw_time": "2:18:59",
      "offset": 8339,
      "username": "polawdomu",
      "content": "mniej golda za kill"
    }

    Linie niepasujące do formatu są traktowane jako kontynuacja poprzedniej wiadomości.
    """
    messages = []
    ignored = parse_ignored_users(ignored_users)
    skipping_ignored_message = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n\r")
        if not line.strip():
            continue

        match = LINE_RE.match(line)
        if match:
            raw_time = match.group("time")
            username = match.group("user").strip()
            content = match.group("msg")
            skipping_ignored_message = username.lower() in ignored

            if skipping_ignored_message:
                continue

            if username.lower() in ignored:
                continue

            messages.append({
                "raw_time": raw_time,
                "offset": parse_hms_to_seconds(raw_time),
                "username": username,
                "content": content,
            })
        else:
            # Awaryjnie: gdy jakaś wiadomość złamie się do kolejnej linii.
            # Jeśli poprzednia poprawnie sparsowana linia była od ignorowanego
            # użytkownika, ignorujemy wszystkie jej kontynuacje aż do kolejnej
            # linii z timestampem i nickiem.
            if messages and not skipping_ignored_message:
                messages[-1]["content"] += "\n" + line

    return messages


def convert_atomowybot_to_twitch(text: str, ignored_users=None):
    atom_messages = parse_atomowybot_text(text, ignored_users)

    tpl = json.loads(json.dumps(BUILTIN_TEMPLATE))
    tpl["FileInfo"]["CreatedAt"] = iso_now_local()

    tpl["streamer"]["name"] = FORCED_STREAMER["name"]
    tpl["streamer"]["login"] = FORCED_STREAMER["login"]
    tpl["streamer"]["id"] = int(FORCED_STREAMER["id"])

    streamer_id = int(FORCED_STREAMER["id"])

    # Sztuczna data startu, bo Atomowybot format nie zawiera daty.
    video_created = "1970-01-01T00:00:00Z"
    tpl["video"]["created_at"] = video_created
    tpl["video"]["id"] = "0"

    comments = []

    for msg in atom_messages:
        offset = int(msg["offset"])
        username = msg["username"]
        user_id = stable_user_id(username)

        body, fragments, emoticons = build_body_and_fragments(msg["content"])

        comment = {
            "_id": str(uuid.uuid4()),
            "created_at": fake_created_at_from_offset(offset),
            "channel_id": str(streamer_id),
            "content_type": "video",
            "content_id": tpl["video"]["id"],
            "content_offset_seconds": offset,
            "commenter": {
                "display_name": username,
                "_id": user_id,
                "name": username.lower(),
                "bio": None,
                "created_at": video_created,
                "updated_at": video_created,
                "logo": None,
            },
            "message": {
                "body": body,
                "bits_spent": 0,
                "fragments": fragments,
                "user_badges": [],
                "user_color": None,
                "emoticons": emoticons,
            },
            "source_metadata": {
                "source": "Atomowybot",
                "raw_time": msg["raw_time"],
            },
        }

        comments.append(comment)

    comments.sort(key=lambda c: c["content_offset_seconds"])
    tpl["comments"] = comments

    tpl["video"]["start"] = 0
    if comments:
        last = int(comments[-1]["content_offset_seconds"])
        tpl["video"]["end"] = last
        tpl["video"]["length"] = last
    else:
        tpl["video"]["end"] = 0
        tpl["video"]["length"] = 0

    return tpl, len(atom_messages)


# ============================================================
# 2) CENZURA TWITCHDOWNLOADER CHAT.JSON
#    Logika przeniesiona z twitch_chat_censor_gui_v3.
# ============================================================

REPLACEMENTS = [
    ("pedofil", "PDF"),
    ("cwel", "spell"),
    ("czarnu", "*****"),
    ("ciota", "*****"),
]

SIMILAR = {
    "a": "aA4@ąĄ",
    "c": "cCćĆ",
    "d": "dD",
    "e": "eE3ęĘ",
    "f": "fF",
    "i": "iI1!|lL",
    "l": "lL1!|iI",
    "n": "nNńŃ",
    "o": "oO0óÓ",
    "p": "pP",
    "r": "rR",
    "t": "tT7+",
    "u": "uU",
    "w": "wWvV",
    "z": "zZ2żŻźŹ",
}


def make_pattern(word: str) -> re.Pattern:
    """
    Tworzy regex wykrywający słowo także z podobnymi znakami.
    Przykład: cwel złapie cwel, cw3l, cw!l, CWEL, fcwely.
    """
    parts = []
    for ch in word:
        chars = SIMILAR.get(ch.lower(), ch)
        parts.append("[" + re.escape(chars) + "]")

    return re.compile("".join(parts), re.IGNORECASE)


PATTERNS = [(make_pattern(src), repl) for src, repl in REPLACEMENTS]


def censor_text(value):
    if not isinstance(value, str):
        return value

    out = value
    for pattern, replacement in PATTERNS:
        out = pattern.sub(replacement, out)

    return out


def censor_commenter(commenter: dict):
    if not isinstance(commenter, dict):
        return

    for key in [
        "display_name",
        "name",
        "login",
        "user_name",
        "username",
    ]:
        if key in commenter:
            commenter[key] = censor_text(commenter[key])


def censor_message(message: dict):
    if not isinstance(message, dict):
        return

    if "body" in message:
        message["body"] = censor_text(message["body"])

    # TwitchDownloader najczęściej renderuje fragments[].text,
    # więc to też trzeba obowiązkowo ruszać.
    fragments = message.get("fragments", [])
    if isinstance(fragments, list):
        for frag in fragments:
            if isinstance(frag, dict) and "text" in frag:
                frag["text"] = censor_text(frag["text"])


def process_chat(data):
    if not isinstance(data, dict):
        raise ValueError("To nie wygląda jak TwitchDownloader Chat.json — główny obiekt nie jest JSON object.")

    comments = data.get("comments")
    if not isinstance(comments, list):
        raise ValueError("Nie znaleziono listy comments w JSON-ie.")

    changed_comments = 0

    for comment in comments:
        if not isinstance(comment, dict):
            continue

        before = json.dumps(comment, ensure_ascii=False, sort_keys=True)

        censor_commenter(comment.get("commenter", {}))
        censor_message(comment.get("message", {}))

        # Awaryjnie: gdyby jakiś wariant trzymał nick/tekst na górnym poziomie komentarza.
        for key in ["display_name", "name", "login", "username", "body", "text"]:
            if key in comment:
                comment[key] = censor_text(comment[key])

        after = json.dumps(comment, ensure_ascii=False, sort_keys=True)
        if before != after:
            changed_comments += 1

    return data, changed_comments, len(comments)


# ============================================================
# 3) REAKCJE Z TWITCHDOWNLOADER CHAT.JSON
#    Logika przeniesiona z reakcje_gui.
# ============================================================

KEYWORDS = ["xd", "KEKW", "cinema", "sad", "oh", "sus", "kekleo", "okurwa"]
SHOT_DURATION = 30  # seconds
COOLDOWN = 30       # seconds
DEFAULT_IGNORED_USERS = ["BotRix"]


def parse_ignored_users(value):
    """Return a normalized set of ignored user names from text/list input."""
    if value is None:
        users = DEFAULT_IGNORED_USERS
    elif isinstance(value, str):
        users = re.split(r"[,\n;]+", value)
    else:
        users = value

    return {str(user).strip().lower() for user in users if str(user).strip()}


def get_comment_username(comment):
    if not isinstance(comment, dict):
        return ""

    commenter = comment.get("commenter", {})
    if isinstance(commenter, dict):
        for key in ["display_name", "name", "login", "user_name", "username"]:
            value = commenter.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    for key in ["display_name", "name", "login", "user_name", "username"]:
        value = comment.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def emotes_to_plain_text(content):
    if content is None:
        return ""

    def repl(m):
        return " " + m.group(2) + " "

    out = EMOTE_RE.sub(repl, str(content))
    out = re.sub(r"\s+", " ", out).strip()
    return out


def twitch_message_to_plain_text(message):
    """
    TwitchDownloader Chat.json:
    comments[].message.body
    comments[].message.fragments[].text
    """
    if not isinstance(message, dict):
        return ""

    body = message.get("body")
    if isinstance(body, str) and body.strip():
        return emotes_to_plain_text(body)

    fragments = message.get("fragments", [])
    parts = []

    if isinstance(fragments, list):
        for frag in fragments:
            if isinstance(frag, dict):
                txt = frag.get("text")
                if isinstance(txt, str):
                    parts.append(txt)

    return emotes_to_plain_text("".join(parts))


def get_time_difference_sec(t1, t2):
    if t1 is None or t2 is None:
        return 99999
    return float(t1) - float(t2)


def format_days_hms(seconds):
    """
    Format zgodny z Twoimi programami:
    days:HH:MM:SS
    np. 0:03:56:12
    """
    total = int(max(0, seconds))
    days = total // 86400
    rem = total % 86400
    hh = rem // 3600
    mm = (rem % 3600) // 60
    ss = rem % 60
    return f"{days}:{hh:02d}:{mm:02d}:{ss:02d}"


def parse_time_to_seconds(value):
    """
    Przyjmuje m.in.:
    - puste pole -> None
    - sekundy: 1234 albo 1234.5
    - MM:SS, HH:MM:SS, days:HH:MM:SS
    """
    value = str(value).strip()
    if not value:
        return None

    if re.fullmatch(r"\d+(\.\d+)?", value):
        return float(value)

    parts = value.split(":")
    if not 2 <= len(parts) <= 4:
        raise ValueError("Podaj czas jako sekundy, MM:SS, HH:MM:SS albo days:HH:MM:SS.")

    try:
        nums = [float(p.strip()) for p in parts]
    except Exception as exc:
        raise ValueError("Czas może zawierać tylko liczby i dwukropki.") from exc

    if any(n < 0 for n in nums):
        raise ValueError("Czas nie może być ujemny.")

    if len(nums) == 2:
        minutes, seconds = nums
        return minutes * 60 + seconds
    if len(nums) == 3:
        hours, minutes, seconds = nums
        return hours * 3600 + minutes * 60 + seconds

    days, hours, minutes, seconds = nums
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def load_twitch_chat_json_from_data(data, ignored_users=None):
    if not isinstance(data, dict):
        raise ValueError("To nie wygląda jak TwitchDownloader Chat.json — główny JSON nie jest obiektem.")

    comments = data.get("comments")
    if not isinstance(comments, list):
        raise ValueError("Nie znaleziono listy comments w JSON-ie.")

    messages = []
    ignored = parse_ignored_users(ignored_users)

    for comment in comments:
        if not isinstance(comment, dict):
            continue

        username = get_comment_username(comment)
        if username.lower() in ignored:
            continue

        offset = comment.get("content_offset_seconds")
        if offset is None:
            continue

        try:
            t = float(offset)
        except Exception:
            continue

        text = twitch_message_to_plain_text(comment.get("message", {}))

        messages.append({
            "time": t,
            "text": text,
        })

    messages.sort(key=lambda x: x["time"])
    return messages


def load_twitch_chat_json(path, ignored_users=None):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return load_twitch_chat_json_from_data(data, ignored_users)


def filter_messages_by_range(messages, start_sec=None, end_sec=None):
    if start_sec is not None and end_sec is not None and start_sec > end_sec:
        raise ValueError("Czas 'od' nie może być większy niż czas 'do'.")

    filtered = []
    for msg in messages:
        t = msg["time"]
        if start_sec is not None and t < start_sec:
            continue
        if end_sec is not None and t > end_sec:
            continue
        filtered.append(msg)
    return filtered


def analyze_reactions(messages):
    if not messages:
        return []

    times = []
    reaction_array = []
    reactions_array = []

    for msg in messages:
        text = msg["text"]
        t = msg["time"]
        times.append(t)

        if any(k.lower() in text.lower() for k in KEYWORDS):
            reaction_array.append(1)
            reactions_array.append(1)
        else:
            reaction_array.append(0)
            reactions_array.append(0)

    line_count = len(messages)
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

    highest = max(reactions_array) if reactions_array else 0
    work = reactions_array[:]
    results = []

    reaction_moments = 0
    current = highest

    while current > 0:
        for i in range(line_count):
            if work[i] == current:
                work[i] = 0
                reaction_moments += 1

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

                reaction_time = times[i] - half
                if reaction_time < 0:
                    reaction_time = 0

                results.append({
                    "index": reaction_moments,
                    "formatted": format_days_hms(reaction_time),
                    "reactions": current,
                })

        current -= 1

    return results


def make_reactions_output_path(input_path):
    folder = os.path.dirname(input_path)
    base = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(folder, f"Reakcje_{base}.txt")


def write_results(out_path, results):
    with open(out_path, "w", encoding="utf-8") as out:
        for item in results:
            out.write(f"{item['index']}. {item['formatted']} /// Reakcje: {item['reactions']}\n")


# ============================================================
# 4) POŁĄCZONY GUI
# ============================================================


def default_json_path_from_txt(txt_path, censored=False):
    if txt_path:
        folder = os.path.dirname(txt_path)
        base = os.path.splitext(os.path.basename(txt_path))[0]
        suffix = "_cenz" if censored else ""
        return os.path.join(folder, f"{base}{suffix}.json")
    return "Chat_cenz.json" if censored else "Chat.json"


class ComboApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Atomowybot TXT -> Twitch JSON + cenzura + reakcje")
        self.geometry("960x720")
        self.minsize(820, 560)

        self.input_path = tk.StringVar(value="")
        self.censor_var = tk.BooleanVar(value=False)
        self.reactions_var = tk.BooleanVar(value=False)
        self.start_var = tk.StringVar(value="")
        self.end_var = tk.StringVar(value="")
        self.ignored_users_var = tk.StringVar(value=", ".join(DEFAULT_IGNORED_USERS))

        self._build_gui()

    def _build_gui(self):
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 6))

        tk.Label(top, text="Plik chatu Atomowybota (.txt):").pack(anchor="w")

        row = tk.Frame(top)
        row.pack(fill="x", pady=(4, 0))

        tk.Entry(row, textvariable=self.input_path).pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Button(row, text="Wybierz plik…", command=self.pick_file).pack(side="left")
        tk.Button(row, text="Wczytaj do pola", command=self.load_to_textbox).pack(side="left", padx=(8, 0))

        tk.Label(
            self,
            text=(
                "Możesz też wkleić chat ręcznie poniżej. "
                "Timestampy są brane bezpośrednio z linii, np. [2:18:59] = 8339 sekund."
            ),
            fg="gray",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        self.textbox = scrolledtext.ScrolledText(self, wrap="word", height=25)
        self.textbox.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        options = tk.LabelFrame(self, text="Opcje")
        options.pack(fill="x", padx=10, pady=(0, 8))

        tk.Checkbutton(
            options,
            text="Ocenzoruj — zapisze ocenzurowany JSON ZAMIAST nieocenzurowanego",
            variable=self.censor_var,
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(8, 4))

        tk.Checkbutton(
            options,
            text="Stwórz reakcje — zapisze plik Reakcje_*.txt RAZEM z plikiem JSON",
            variable=self.reactions_var,
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 6))

        tk.Label(options, text="Ignorowani użytkownicy:").grid(row=2, column=0, sticky="w", padx=(10, 4), pady=(0, 8))
        tk.Entry(options, textvariable=self.ignored_users_var, width=40).grid(row=2, column=1, columnspan=3, sticky="we", padx=(0, 10), pady=(0, 8))

        tk.Label(options, text="Zakres reakcji od:").grid(row=3, column=0, sticky="w", padx=(10, 4), pady=(0, 8))
        tk.Entry(options, textvariable=self.start_var, width=16).grid(row=3, column=1, sticky="w", padx=(0, 14), pady=(0, 8))
        tk.Label(options, text="do:").grid(row=3, column=2, sticky="w", padx=(0, 4), pady=(0, 8))
        tk.Entry(options, textvariable=self.end_var, width=16).grid(row=3, column=3, sticky="w", padx=(0, 10), pady=(0, 8))

        tk.Label(
            options,
            text="Zakres możesz zostawić pusty. Format: sekundy, MM:SS, HH:MM:SS albo days:HH:MM:SS.",
            fg="gray",
        ).grid(row=4, column=0, columnspan=4, sticky="w", padx=10, pady=(0, 8))

        options.grid_columnconfigure(1, weight=1)

        bottom = tk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=(0, 10))

        tk.Button(
            bottom,
            text="Konwertuj i zapisz",
            height=2,
            command=self.convert_and_save,
        ).pack(side="left")

        tk.Label(
            bottom,
            text="Streamer: xntentacion | Format wejścia: [H:MM:SS] nick: wiadomość",
            fg="gray",
        ).pack(side="left", padx=14)

    def pick_file(self):
        path = filedialog.askopenfilename(
            title="Wybierz plik chatu Atomowybota",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.input_path.set(path)
            self.load_to_textbox()

    def load_to_textbox(self):
        path = self.input_path.get().strip()
        if not path:
            messagebox.showerror("Błąd", "Najpierw wybierz plik.")
            return

        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                text = f.read()
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się wczytać pliku:\n{e}")
            return

        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text)

    def _get_input_text(self):
        text = self.textbox.get("1.0", "end").strip()

        if not text:
            # Jeśli pole puste, spróbuj wczytać wybrany plik.
            path = self.input_path.get().strip()
            if path:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                    text = f.read()

        return text

    def convert_and_save(self):
        try:
            text = self._get_input_text()
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się wczytać pliku:\n{e}")
            return

        if not text.strip():
            messagebox.showerror("Błąd", "Brak tekstu do konwersji.")
            return

        try:
            ignored_users = parse_ignored_users(self.ignored_users_var.get())
            out_data, parsed_count = convert_atomowybot_to_twitch(text, ignored_users)
        except Exception as e:
            messagebox.showerror("Błąd", f"Konwersja nieudana:\n{e}")
            return

        if parsed_count == 0:
            messagebox.showerror(
                "Błąd",
                "Nie znaleziono żadnych wiadomości w formacie:\n[H:MM:SS] nick: wiadomość",
            )
            return

        changed = None
        total = None
        if self.censor_var.get():
            try:
                # Kopia przez JSON zachowuje czyste rozdzielenie danych.
                out_data, changed, total = process_chat(json.loads(json.dumps(out_data)))
            except Exception as e:
                messagebox.showerror("Błąd", f"Cenzura nieudana:\n{e}")
                return

        default_path = default_json_path_from_txt(self.input_path.get().strip(), self.censor_var.get())
        save_path = filedialog.asksaveasfilename(
            title="Zapisz Twitch Chat.json",
            defaultextension=".json",
            initialdir=os.path.dirname(default_path) if os.path.dirname(default_path) else None,
            initialfile=os.path.basename(default_path),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )

        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(out_data, f, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się zapisać pliku:\n{e}")
            return

        reactions_info = ""
        if self.reactions_var.get():
            try:
                start_sec = parse_time_to_seconds(self.start_var.get())
                end_sec = parse_time_to_seconds(self.end_var.get())
                messages = load_twitch_chat_json_from_data(out_data, ignored_users)
                if not messages:
                    raise ValueError("Nie znaleziono żadnych wiadomości z content_offset_seconds.")
                selected_messages = filter_messages_by_range(messages, start_sec, end_sec)
                if not selected_messages:
                    raise ValueError("W podanym zakresie nie ma żadnych wiadomości z content_offset_seconds.")
                results = analyze_reactions(selected_messages)
                reactions_path = make_reactions_output_path(save_path)
                write_results(reactions_path, results)
                reactions_info = (
                    f"\n\nReakcje: {len(results)} momentów"
                    f"\nPrzeanalizowano wiadomości: {len(selected_messages)} z {len(messages)}"
                    f"\nZapisano reakcje:\n{reactions_path}"
                )
            except Exception as e:
                messagebox.showerror(
                    "Błąd",
                    f"JSON został zapisany, ale tworzenie reakcji nieudane:\n{e}",
                )
                return

        censor_info = ""
        if self.censor_var.get() and changed is not None:
            censor_info = f"\nOcenzurowane komentarze: {changed}/{total}"

        messagebox.showinfo(
            "Gotowe",
            f"Zapisano:\n{save_path}\n\nWiadomości: {len(out_data['comments'])}"
            f"\nOstatni offset: {out_data['video']['end']} sekund"
            f"\nIgnorowani użytkownicy: {', '.join(sorted(ignored_users)) or 'brak'}"
            f"{censor_info}{reactions_info}",
        )


if __name__ == "__main__":
    ComboApp().mainloop()
