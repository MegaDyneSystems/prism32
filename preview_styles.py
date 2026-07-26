#!/usr/bin/env python3
"""Visual style previews for Prism32 - run this to see options before applying."""
import os, sys

# ANSI helpers
RST = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
C_PRIMARY = "\x1b[38;5;219m"      # pink
C_BRIGHT = "\x1b[1;95m"           # bright magenta
C_DIM = "\x1b[2;38;5;245m"        # gray
C_ACCENT = "\x1b[38;5;87m"        # cyan
C_WARN = "\x1b[38;5;228m"         # yellow
C_ERR = "\x1b[38;5;203m"          # red
C_GLOW = "\x1b[5;95m"             # blink magenta
C_BAR = "\x1b[48;5;201m"          # bg pink
C_GREEN = "\x1b[38;5;82m"         # neon green
C_AMBER = "\x1b[38;5;214m"        # amber
C_CYAN = "\x1b[38;5;51m"          # cyan
C_PURPLE = "\x1b[38;5;141m"       # purple

def clear():
    os.system('clear' if os.name != 'nt' else 'cls')

def pause():
    input(f"\n{C_DIM}Press Enter to continue...{RST}")

def header(title):
    print(f"\n{C_PRIMARY}{'━'*70}{RST}")
    print(f"  {C_BRIGHT}{title}{RST}")
    print(f"{C_PRIMARY}{'━'*70}{RST}\n")

# ── STYLE 1: Cyberpunk Neon ──────────────────────────────────
def style_cyberpunk():
    header("STYLE 1: CYBERPUNK NEON")

    # Box style
    print(f" {C_CYAN}╔══════════════════════════════════════════════════════════╗{RST}")
    print(f" {C_CYAN}║{RST} {C_BRIGHT}AI ANALYSIS{RST}                                              {C_CYAN}║{RST}")
    print(f" {C_CYAN}╠══════════════════════════════════════════════════════════╣{RST}")
    print(f" {C_CYAN}║{RST} {C_DIM}Investigating network configuration...{RST}                  {C_CYAN}║{RST}")
    print(f" {C_CYAN}║{RST} {C_DIM}Found 3 interfaces: eth0, wlan0, lo{RST}                     {C_CYAN}║{RST}")
    print(f" {C_CYAN}╚══════════════════════════════════════════════════════════╝{RST}")

    print()

    # Status bar
    print(f" {C_CYAN}▓▓▓{RST} {C_BRIGHT}Prism32{RST} {C_DIM}MDS:{RST} {C_AMBER}Ctx 42%{RST} {C_DIM}${0.0042:.4f}{RST} {C_WARN}SA:2{RST} {C_ACCENT}⚡{RST} {C_GREEN}▁{C_GREEN}▂{C_GREEN}▃{C_GREEN}▄{C_GREEN}▅{RST} {C_PURPLE}►{RST}")

    print()

    # Prompt
    print(f" {C_CYAN}◈{RST} {C_BRIGHT}prism32{RST}{C_DIM}>{RST} {C_DIM}type your command here...{RST}")

    print()

    # Step header
    print(f" {C_CYAN}▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰{RST}")
    print(f" {C_BRIGHT}STEP 3/10{RST}  {C_DIM}Diagnose WiFi connectivity issues and upstream routing{RST}")
    print(f" {C_CYAN}▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰{RST}")

    print()

    # Tool call
    print(f" {C_ACCENT}⚡ execute{RST} {C_BRIGHT}iwconfig wlan0{RST}")
    print(f"   {C_GREEN}✓{RST} {C_DIM}wlan0     IEEE 802.11  ESSID:off/any  Mode:Managed...{RST}")

    print()

    # Activity indicator examples
    print(f" {C_DIM}Activity indicators:{RST}")
    print(f"   {C_GREEN}▁▂▃▄▅▆▇█{RST}  (wave)")
    print(f"   {C_CYAN}◐ ◓ ◑ ◒{RST}   (spin)")
    print(f"   {C_AMBER}◢ ◣ ◤ ◥{RST}   (diamond)")

# ── STYLE 2: Retro CRT Green Phosphor ────────────────────────
def style_retro_crt():
    header("STYLE 2: RETRO CRT GREEN PHOSPHOR")

    crt_g = "\x1b[38;5;118m"    # phosphor green
    crt_b = "\x1b[38;5;22m"     # dark green
    crt_dim = "\x1b[38;5;28m"   # dim green

    print(f" {crt_g}++==========================================================++{RST}")
    print(f" {crt_g}||{RST} {crt_g}AI ANALYSIS{RST}                                              {crt_g}||{RST}")
    print(f" {crt_g}||----------------------------------------------------------||{RST}")
    print(f" {crt_g}||{RST} {crt_dim}Investigating network configuration...{RST}                  {crt_g}||{RST}")
    print(f" {crt_g}||{RST} {crt_dim}Found 3 interfaces: eth0, wlan0, lo{RST}                     {crt_g}||{RST}")
    print(f" {crt_g}++==========================================================++{RST}")

    print()

    # Status bar with scanline feel
    print(f" {crt_dim}::{RST} {crt_g}Prism32{RST} {crt_dim}MDS:{RST} {crt_g}Ctx 42%{RST} {crt_dim}${0.0042:.4f}{RST} {crt_g}SA:2{RST} {crt_dim}[Q]{RST} {crt_g}▃{RST} {crt_g}>{RST}")

    print()

    # Prompt
    print(f" {crt_g}>>{RST} {crt_dim}type your command here...{RST}")

    print()

    # Step header with phosphor glow
    print(f" {crt_g}======================================================================{RST}")
    print(f" {crt_g}STEP 3/10{RST}  {crt_dim}Diagnose WiFi connectivity issues and upstream routing{RST}")
    print(f" {crt_g}======================================================================{RST}")

    print()

    # Tool call
    print(f" {crt_g}[EXEC]{RST} {crt_g}iwconfig wlan0{RST}")
    print(f"   {crt_g}[OK]{RST} {crt_dim}wlan0     IEEE 802.11  ESSID:off/any  Mode:Managed...{RST}")

    print()

    print(f" {crt_dim}Activity indicators:{RST}")
    print(f"   {crt_g}* - * - *{RST}  (pulse)")
    print(f"   {crt_g}[=   ] [==  ] [=== ] [====]{RST}  (progress)")
    print(f"   {crt_g}{chr(0x2580)}{chr(0x2584)}{chr(0x2580)}{chr(0x2584)}{RST}  (crt flicker)")

# ── STYLE 3: Matrix Terminal ─────────────────────────────────
def style_matrix():
    header("STYLE 3: MATRIX TERMINAL")

    mx = "\x1b[38;5;82m"       # matrix green
    mx_bright = "\x1b[1;38;5;82m"
    mx_dim = "\x1b[38;5;28m"
    mx_accent = "\x1b[38;5;46m"

    print(f" {mx}┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓{RST}")
    print(f" {mx}┃{RST} {mx_bright}AI ANALYSIS{RST}                                              {mx}┃{RST}")
    print(f" {mx}┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫{RST}")
    print(f" {mx}┃{RST} {mx_dim}Investigating network configuration...{RST}                  {mx}┃{RST}")
    print(f" {mx}┃{RST} {mx_dim}Found 3 interfaces: eth0, wlan0, lo{RST}                     {mx}┃{RST}")
    print(f" {mx}┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛{RST}")

    print()

    # Status bar
    print(f" {mx_dim}>>>{RST} {mx_bright}Prism32{RST} {mx_dim}|{RST} {mx}Ctx 42%{RST} {mx_dim}|{RST} ${0.0042:.4f} {mx_dim}|{RST} {mx}SA:2{RST} {mx_dim}|{RST} {mx_accent}010{RST}{mx_accent}Q{RST} {mx}▇{RST} {mx}>{RST}")

    print()

    # Prompt
    print(f" {mx_accent}λ{RST} {mx_dim}type your command here...{RST}")

    print()

    # Step header
    print(f" {mx}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RST}")
    print(f" {mx_bright}[STEP 3/10]{RST}  {mx_dim}Diagnose WiFi connectivity issues and upstream routing{RST}")
    print(f" {mx}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RST}")

    print()

    # Tool call
    print(f" {mx_accent}>> execute{RST} {mx_bright}iwconfig wlan0{RST}")
    print(f"   {mx}[OK]{RST} {mx_dim}wlan0     IEEE 802.11  ESSID:off/any  Mode:Managed...{RST}")

    print()

    print(f" {mx_dim}Activity indicators:{RST}")
    print(f"   {mx}01010101{RST}  (binary)")
    print(f"   {mx}↓ ↑ ↓ ↑{RST}   (rain)")
    print(f"   {mx}▓▒░▒▓{RST}     (density)")

# ── STYLE 4: Synthwave / Vapor ───────────────────────────────
def style_synthwave():
    header("STYLE 4: SYNTHWAVE / VAPOR")

    sw_pink = "\x1b[38;5;213m"    # hot pink
    sw_cyan = "\x1b[38;5;51m"     # electric cyan
    sw_purp = "\x1b[38;5;141m"    # purple
    sw_amber = "\x1b[38;5;214m"   # amber
    sw_dim = "\x1b[38;5;240m"

    print(f" {sw_pink}▛▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▜{RST}")
    print(f" {sw_pink}▌{RST} {sw_cyan}▞▞▞ AI ANALYSIS ▞▞▞{RST}                                     {sw_pink}▌{RST}")
    print(f" {sw_pink}▌{RST}{sw_purp}──────────────────────────────────────────────────────────{RST}{sw_pink}▌{RST}")
    print(f" {sw_pink}▌{RST} {sw_dim}Investigating network configuration...{RST}                  {sw_pink}▌{RST}")
    print(f" {sw_pink}▌{RST} {sw_dim}Found 3 interfaces: eth0, wlan0, lo{RST}                     {sw_pink}▌{RST}")
    print(f" {sw_pink}▙▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▟{RST}")

    print()

    # Status bar
    print(f" {sw_pink}▓▓▓{RST} {sw_cyan}Prism32{RST} {sw_dim}◈{RST} {sw_amber}Ctx 42%{RST} {sw_dim}◈{RST} ${0.0042:.4f} {sw_dim}◈{RST} {sw_purp}SA:2{RST} {sw_dim}◈{RST} {sw_cyan}◈{RST} {sw_pink}▂{RST} {sw_cyan}▶{RST}")

    print()

    # Prompt
    print(f" {sw_cyan}▶{RST} {sw_dim}type your command here...{RST}")

    print()

    # Step header
    print(f" {sw_pink}▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬{RST}")
    print(f" {sw_cyan}◢ STEP 3/10 ◣{RST}  {sw_dim}Diagnose WiFi connectivity issues and upstream routing{RST}")
    print(f" {sw_pink}▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬{RST}")

    print()

    # Tool call
    print(f" {sw_cyan}◈ execute{RST} {sw_cyan}iwconfig wlan0{RST}")
    print(f"   {sw_pink}✓{RST} {sw_dim}wlan0     IEEE 802.11  ESSID:off/any  Mode:Managed...{RST}")

    print()

    print(f" {sw_dim}Activity indicators:{RST}")
    print(f"   {sw_pink}▁{sw_cyan}▂{sw_purp}▃{sw_amber}▄{sw_pink}▅{sw_cyan}▆{sw_purp}▇{sw_amber}█{RST}  (rainbow wave)")
    print(f"   {sw_cyan}◢ ◣ ◤ ◥{RST}   (diamond spin)")
    print(f"   {sw_pink}◐ ◓ ◑ ◒{RST}   (moon phases)")

# ── STYLE 5: Minimal Hacker ──────────────────────────────────
def style_minimal_hacker():
    header("STYLE 5: MINIMAL HACKER (clean & sharp)")

    h_white = "\x1b[1;37m"
    h_gray = "\x1b[38;5;245m"
    h_green = "\x1b[38;5;40m"
    h_red = "\x1b[38;5;160m"
    h_blue = "\x1b[38;5;39m"

    print(f" {h_gray}┌──────────────────────────────────────────────────────────┐{RST}")
    print(f" {h_gray}│{RST} {h_white}AI ANALYSIS{RST}                                              {h_gray}│{RST}")
    print(f" {h_gray}├──────────────────────────────────────────────────────────┤{RST}")
    print(f" {h_gray}│{RST} {h_gray}Investigating network configuration...{RST}                  {h_gray}│{RST}")
    print(f" {h_gray}│{RST} {h_gray}Found 3 interfaces: eth0, wlan0, lo{RST}                     {h_gray}│{RST}")
    print(f" {h_gray}└──────────────────────────────────────────────────────────┘{RST}")

    print()

    # Status bar - minimal separators
    print(f" {h_gray}•{RST} {h_white}Prism32{RST} {h_gray}mdst{RST} {h_green}ctx:42%{RST} {h_gray}${0.0042:.4f}{RST} {h_red}sa:2{RST} {h_blue}q{RST} {h_green}*{RST} {h_white}>{RST}")

    print()

    # Prompt
    print(f" {h_white}>{RST} {h_gray}type your command here...{RST}")

    print()

    # Step header
    print(f" {h_gray}──────────────────────────────────────────────────────────────────────{RST}")
    print(f" {h_white}[3/10]{RST} {h_gray}Diagnose WiFi connectivity issues and upstream routing{RST}")
    print(f" {h_gray}──────────────────────────────────────────────────────────────────────{RST}")

    print()

    # Tool call
    print(f" {h_blue}$ {RST}{h_white}iwconfig wlan0{RST}")
    print(f"   {h_green}ok{RST} {h_gray}wlan0     IEEE 802.11  ESSID:off/any  Mode:Managed...{RST}")

    print()

    print(f" {h_gray}Activity indicators:{RST}")
    print(f"   {h_green}→ → →{RST}  (arrow)")
    print(f"   {h_green}[│││  ] [││││ ] [│││││]{RST}  (bar)")
    print(f"   {h_green}● ○ ○ ● ○{RST}  (dot)")

# ── STYLE 6: Glitch / Corruption ─────────────────────────────
def style_glitch():
    header("STYLE 6: GLITCH / DIGITAL DECAY")

    g_red = "\x1b[38;5;196m"
    g_yellow = "\x1b[38;5;226m"
    g_green = "\x1b[38;5;82m"
    g_white = "\x1b[1;97m"
    g_dim = "\x1b[38;5;240m"

    print(f" {g_red}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{RST}")
    print(f" {g_yellow}!!! AI ANALYSIS !!!{RST}")
    print(f" {g_red}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{RST}")
    print(f" {g_dim}Investigating network configuration...{RST}")
    print(f" {g_dim}Found 3 interfaces: eth0, wlan0, lo{RST}")
    print(f" {g_red}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{RST}")

    print()

    # Status bar with corruption aesthetic
    print(f" {g_red}[!]{RST} {g_white}Prism32{RST} {g_dim}|{RST} {g_yellow}Ctx:42%{RST} {g_dim}|{RST} ${0.0042:.4f} {g_dim}|{RST} {g_red}SA:2{RST} {g_dim}|{RST} {g_yellow}[Q]{RST} {g_red}▓{RST} {g_white}>{RST}")

    print()

    # Prompt
    print(f" {g_red}!>{RST} {g_dim}type your command here...{RST}")

    print()

    # Step header
    print(f" {g_red}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{RST}")
    print(f" {g_yellow}STEP [3/10]{RST} {g_dim}Diagnose WiFi connectivity issues and upstream routing{RST}")
    print(f" {g_red}▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓{RST}")

    print()

    # Tool call
    print(f" {g_yellow}[EXEC]{RST} {g_white}iwconfig wlan0{RST}")
    print(f"   {g_green}[OK]{RST} {g_dim}wlan0     IEEE 802.11  ESSID:off/any  Mode:Managed...{RST}")

    print()

    print(f" {g_dim}Activity indicators:{RST}")
    print(f"   {g_red}█▓▒░▒▓█{RST}  (decay)")
    print(f"   {g_yellow}!!! !!!{RST}  (alert)")
    print(f"   {g_red}▓░▓░▓░▓{RST}  (static)")

# ── MAIN ─────────────────────────────────────────────────────
if __name__ == "__main__":
    clear()
    print(f"\n{C_BRIGHT}Prism32 Visual Style Previews{C_DIM} — run any of these, pick your favorite, then tell me which one (or mix elements).{RST}\n")

    style_cyberpunk()
    print("\n" + "="*70 + "\n")

    style_retro_crt()
    print("\n" + "="*70 + "\n")

    style_matrix()
    print("\n" + "="*70 + "\n")

    style_synthwave()
    print("\n" + "="*70 + "\n")

    style_minimal_hacker()
    print("\n" + "="*70 + "\n")

    style_glitch()

    print(f"\n{C_PRIMARY}{'━'*70}{RST}")
    print(f"  {C_BRIGHT}Done!{RST} Which style do you prefer? Tell me:")
    print(f"  {C_DIM}• A number (1-6) for the whole style{RST}")
    print(f"  {C_DIM}• Mix: e.g. 'borders from 1, prompt from 4, colors from 3'{RST}")
    print(f"  {C_DIM}• Or describe your own look and I'll build it{RST}")
    print(f"{C_PRIMARY}{'━'*70}{RST}\n")
