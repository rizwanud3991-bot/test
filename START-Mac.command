#!/bin/bash
# Double-click this file on a Mac to use the BRD Solution Agent.
cd "$(dirname "$0")" || exit 1
HERE="$(pwd)"
KEYFILE="$HOME/.config/brd_agent/key"
VPY="$HERE/.venv/bin/python"

echo
echo " =========================================="
echo "    BRD SOLUTION AGENT"
echo " =========================================="
echo

# 1. Make sure Python is installed
if ! command -v python3 >/dev/null 2>&1; then
    echo " Python is not installed on this Mac."
    echo " A web page will open. Download and install Python, then double-click START again."
    open "https://www.python.org/downloads/" 2>/dev/null
    read -r -p " Press Enter to close..." _
    exit 1
fi

# 2. First time only: install what the agent needs
if [ ! -f "$HERE/.venv/installed.txt" ]; then
    echo " First time setup. Please wait, this can take a few minutes..."
    if python3 -m venv "$HERE/.venv" && "$VPY" -m pip install --disable-pip-version-check -q -r "$HERE/requirements.txt"; then
        echo done > "$HERE/.venv/installed.txt"
        echo " Setup finished."
    else
        rm -rf "$HERE/.venv"
        echo " Setup failed. Check your internet connection and double-click START again."
        read -r -p " Press Enter to close..." _
        exit 1
    fi
fi

# 3. Claude key (asked once, then remembered)
ask_key() {
    while true; do
        echo
        echo " Paste your Claude key and press Enter. (It starts with sk-ant- . To paste: Cmd+V)"
        read -r -p "  Key: " key
        key="$(echo "$key" | tr -d '[:space:]')"
        if [[ "$key" == sk-ant-* ]]; then
            mkdir -p "$(dirname "$KEYFILE")"
            (umask 077; printf '%s\n' "$key" > "$KEYFILE")
            export ANTHROPIC_API_KEY="$key"
            echo " Key saved. You will not be asked again."
            return
        fi
        echo " That does not look like a Claude key. It must start with sk-ant- . Try again."
    done
}
if [ -z "$ANTHROPIC_API_KEY" ] && [ -f "$KEYFILE" ]; then
    export ANTHROPIC_API_KEY="$(head -n 1 "$KEYFILE")"
fi
[ -z "$ANTHROPIC_API_KEY" ] && ask_key

failed() {
    echo
    echo " Something went wrong. Please read the message above."
    echo " If it says \"Authentication failed\", your Claude key is wrong or has no credit."
    echo " If the internet stopped, just try again: finished parts are kept."
    read -r -p " Do you want to enter a new Claude key? Type y (yes) or n (no): " yn
    [[ "$yn" == [yY]* ]] && ask_key
}

make_pack() {
    mkdir -p "$HERE/brds"
    while [ -z "$(find "$HERE/brds" -maxdepth 1 -type f ! -name '.*' | head -n 1)" ]; do
        echo
        echo " The \"brds\" folder is empty."
        echo " A folder window will open now. Copy your requirement documents into it"
        echo " (Word, PDF or text files). Then come back here and press Enter."
        open "$HERE/brds" 2>/dev/null
        read -r -p " Press Enter when done..." _
    done
    echo
    echo " Working... This can take 20 to 40 minutes. You can use your computer meanwhile."
    echo " Do NOT close this window."
    echo
    if "$VPY" -m brd_agent run -i "$HERE/brds" -o "$HERE/output"; then
        echo
        echo " =========================================="
        echo "    DONE! Your solution pack is opening now."
        echo " =========================================="
        open "$HERE/output/solution_pack.html" 2>/dev/null
        open "$HERE/output" 2>/dev/null
    else
        failed
    fi
}

ask_question() {
    if [ ! -f "$HERE/output/solution_pack.html" ]; then
        echo
        echo " First make the solution pack (press 1), then you can ask questions."
        return
    fi
    echo
    echo " Who should the answer be for?"
    echo "   1 = Boss / executive"
    echo "   2 = Business team (simple words)"
    echo "   3 = Technical team"
    read -r -p "  Type 1, 2 or 3 and press Enter: " a
    case "$a" in 1) aud=executive ;; 2) aud=business ;; *) aud=technical ;; esac
    echo
    echo " Type your question and press Enter. Press Enter on an empty line to go back."
    "$VPY" -m brd_agent ask -i "$HERE/brds" -o "$HERE/output" --audience "$aud" || failed
}

# 4. Menu
while true; do
    echo
    echo " What do you want to do?"
    echo
    echo "   1 = Make the solution pack from my documents"
    echo "   2 = Ask a question about my project"
    echo "   3 = Change my Claude key"
    echo "   4 = Close"
    echo
    read -r -p "  Type 1, 2, 3 or 4 and press Enter: " choice
    case "$choice" in
        1) make_pack ;;
        2) ask_question ;;
        3) ask_key ;;
        4) exit 0 ;;
    esac
done
