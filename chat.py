import os
import tkinter as tk
from tkinter import filedialog

def get_time_difference(time1, time2):
    if not time1 or not time2:
        return 99999  # bardzo duża różnica, więc zostanie pominięta
    """
    Calculate the difference in seconds between two time strings (format "HH:MM:SS").
    If time2 is later than time1, it assumes time1 belongs to the next day.
    """
    h1, m1, s1 = map(int, time1.split(':'))
    h2, m2, s2 = map(int, time2.split(':'))
    seconds1 = h1 * 3600 + m1 * 60 + s1
    seconds2 = h2 * 3600 + m2 * 60 + s2
    if seconds2 > seconds1:
        seconds1 += 86400  # add one day (24 hours) if necessary
    return seconds1 - seconds2

def main():
    # Use Tkinter to prompt for a file
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    filePath = filedialog.askopenfilename(
        title="Select a chat text file",
        filetypes=[("Text Files", "*.txt")]
    )
    
    # If no file is selected, exit the program
    if not filePath:
        print("No file selected. Exiting.")
        return

    # Construct the output file path in the same directory
    filePath2 = os.path.join(os.path.dirname(filePath), "xd2.txt")
    
    # Define keywords and constants
    arrayToBeSearched = ["xd", "KEKW", "cinema", "sad", "oh", "sus", "sraka", "cinema"]
    # arrayToBeSearched = ["rosol"]
    shotDuration = 30  # in seconds
    cooldown = 30      # in seconds

    # Read all lines from the chat file
    with open(filePath, "r", encoding="utf-8") as f:
        chatLines = f.readlines()

    lineCount = len(chatLines)
    print(f"Ok, plik ma {lineCount} linii")
    
    # Initialize arrays for marking reactions and storing times
    reactionArray = [0] * lineCount
    reactionsArray = [0] * lineCount
    times = [""] * lineCount

    # Clear the output file (xn.txt)
    with open(filePath2, "w", encoding="utf-8") as f:
        pass
    output_file = open(filePath2, "a", encoding="utf-8")

    # Process each line to determine if it contains a reaction keyword.
    # We split each line into 3 parts: [time], username, and the remaining message.
    import re

    for i in range(lineCount):
        line = chatLines[i].strip()
        
        # Szukamy linii zaczynającej się od [HH:MM:SS]
        match = re.match(r"\[(\d{1,2}:\d{2}:\d{2})\] ([^:]+): (.*)", line)
        if match:
            times[i] = match.group(1)
            message = match.group(3)
        else:
            # jeśli nie pasuje — zostaw puste i omiń
            times[i] = ""
            reactionArray[i] = 0
            reactionsArray[i] = 0
            continue
        
        # Szukanie słów-kluczy w wiadomości
        if any(keyword.lower() in message.lower() for keyword in arrayToBeSearched):
            reactionArray[i] = 1
            reactionsArray[i] = 1
        else:
            reactionArray[i] = 0
            reactionsArray[i] = 0


    # Calculate sliding window reaction counts for each line.
    # The window is shotDuration/2 seconds before and after the current line.
    for i in range(lineCount):
        # Backward window
        j = 0
        while (i - j) >= 0:
            diff = get_time_difference(times[i], times[i - j])
            if diff < (shotDuration / 2):
                reactionsArray[i] += reactionArray[i - j]
                j += 1
            else:
                break

        # Forward window
        j = 0
        while (i + j) < lineCount:
            diff = get_time_difference(times[i + j], times[i])
            if diff < (shotDuration / 2):
                reactionsArray[i] += reactionArray[i + j]
                j += 1
            else:
                break

        print(f"wczytuję chat: {i} / {lineCount}")

    highestReactionCount = max(reactionsArray)
    
    print("znalazłem wszystkie shoty")
    print("Sortowanie shotów...")

    reaction_moments = 0

    # Loop over decreasing reaction counts.
    # For each reaction shot found, clear adjacent lines within shotDuration + cooldown seconds.
    current_highest = highestReactionCount
    while current_highest > 0:
        for i in range(lineCount):
            if reactionsArray[i] == current_highest:
                reactionsArray[i] = 0
                reaction_moments += 1

                # Clear reactions in the backward window (shotDuration + cooldown seconds)
                j = 0
                while (i - j) >= 0:
                    diff = get_time_difference(times[i], times[i - j])
                    if diff < (shotDuration + cooldown):
                        reactionsArray[i - j] = 0
                        j += 1
                    else:
                        break

                # Clear reactions in the forward window (shotDuration + cooldown seconds)
                j = 0
                while (i + j) < lineCount:
                    diff = get_time_difference(times[i + j], times[i])
                    if diff < (shotDuration + cooldown):
                        reactionsArray[i + j] = 0
                        j += 1
                    else:
                        break

                # Adjust the reaction time by subtracting shotDuration/2 seconds from the current time
                h, m, s = map(int, times[i].split(":"))
                total_seconds = h * 3600 + m * 60 + s
                reaction_time_seconds = total_seconds - (shotDuration // 2)
                days = reaction_time_seconds // 86400
                remainder = reaction_time_seconds % 86400
                hours = remainder // 3600
                minutes = (remainder % 3600) // 60
                seconds_val = remainder % 60
                reaction_time_formatted = f"{days}:{hours:02d}:{minutes:02d}:{seconds_val:02d}"
                output_line = f"{reaction_moments}. {reaction_time_formatted} /// Reakcje: {current_highest}"
                print(output_line)
                output_file.write(output_line + "\n")
        current_highest -= 1

    output_file.close()

if __name__ == "__main__":
    main()
