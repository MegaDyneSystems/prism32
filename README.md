PRISM32(TM) V6.7 - INTERACTIVE TERMINAL AGENT
MEGADYNE SYSTEMS (MDS) - LICENSED SOFTWARE

                      (C) COPYRIGHT 2026
           MEGADYNE SYSTEMS - ALL RIGHTS RESERVED

                      DOCUMENT NO. MDS-P32-67
                    FIRST EDITION (JUNE 2026)


                        -----------------
                        PRISM32(TM) V6.7
                        -----------------

                   MEGADYNE SYSTEMS CORPORATION

                     OPERATOR'S GUIDE AND
                 SYSTEM PROGRAMMING REFERENCE



                                                       MDS-P32-67

PRISM32(TM) V6.7 OPERATOR'S GUIDE

                               TABLE OF CONTENTS

  SECTION                                                           PAGE
  -------                                                           ----

  1.0  SYSTEM OVERVIEW ............................................. 1
  2.0  PROGRAM REQUIREMENTS ........................................ 2
  3.0  INSTALLATION PROCEDURE ...................................... 3
  4.0  OPERATOR COMMANDS ........................................... 5
  5.0  AUTONOMOUS GOAL MODE ........................................ 9
  5.5  ACTIVE TASK MODE ............................................ 10
  6.0  COMMAND LINE PARAMETERS ..................................... 11
  7.0  COLOR THEMES ............................................... 12
  8.0  CONFIGURATION FILE .......................................... 13
  9.0  API PROVIDER CONFIGURATION .................................. 14
10.0 PLUGIN PROGRAMMING INTERFACE ............................... 15
   10.1 PLUGIN REGISTRATION ....................................... 15
   10.2 LIFECYCLE HOOKS ........................................... 15
   10.3 EXAMPLE ................................................... 16
   10.4 PLUGIN COMMANDS IN EXECUTE BLOCKS ......................... 16
   10.5 AI PLUGIN GENERATION PROMPT ............................... 16
   10.6 EXAMPLE USAGE ............................................. 16
   11.0 QUANTUM ENTANGLEMENT SHARED CONTEXT ............................ 17
  12.0 RESTRICTIONS AND LIMITATIONS ............................... 18
  13.0 SYSTEM MESSAGES ............................................ 19
  14.0 INDEX ...................................................... 20


                                                               PAGE 1
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

1.0  SYSTEM OVERVIEW
     ===============

     PRISM32 IS AN INTERACTIVE ARTIFICIAL INTELLIGENCE TERMINAL
     AGENT.  THE SYSTEM PROVIDES REAL-TIME CONVERSATIONAL ACCESS
     TO LARGE LANGUAGE MODELS (LLMS) THROUGH A STANDARD
     OPENAI-COMPATIBLE APPLICATION PROGRAMMING INTERFACE.
     THE OPERATOR COMMUNICATES WITH THE AI SUBSYSTEM USING
     NATURAL LANGUAGE INPUT FROM A STANDARD TERMINAL.

THE SYSTEM OPERATES ON THE FOLLOWING PLATFORMS:

           - LINUX (ALL DISTRIBUTIONS)
           - MACOS
           - FREEBSD / NETBSD / OPENBSD
           - MICROSOFT WINDOWS (PARTIAL SUPPORT)
           - WSL / WSL2
           - CHROMEOS / CROSTINI LINUX CONTAINERS
           - ANDROID / TERMUX
           - DOCKER / PODMAN / KUBERNETES / CI RUNNERS
           - PROXMOX VE
           - TRUENAS / FREENAS
           - PFSENSE / OPNSENSE
           - UNRAID
           - OPENMEDIAVAULT
           - STEAMOS / STEAM DECK
           - FEDORA COREOS / SILVERBLUE / KINOITE
           - CLEAR LINUX
           - PHOTON OS / VMWARE APPLIANCES
           - NIXOS / GUIX SYSTEM
           - IRIX (IRIS-ANSI TERMINAL)
           - HP-UX (HPTERM)
           - AIX (AIXTERM)
           - SUNOS / ORACLE SOLARIS (XTERM, SPARC OR X86)
           - ORACLE LINUX
           - ILLUMOS / OPENINDIANA / OMNIOS / SMARTOS
           - OPENWRT / BUSYBOX / ENTWARE EMBEDDED LINUX
           - SYNOLOGY DSM / QNAP NAS SHELLS (BEST EFFORT)
           - HAIKU
           - QNX NEUTRINO
           - MINIX
           - CYGWIN / MSYS2 / MINGW
           - ISH / JAILBROKEN IOS (BEST EFFORT)
           - IBM Z/OS AND IBM I PASE (EXPERIMENTAL)
           - OPENVMS (EXPERIMENTAL)
           - TRU64 (XTERM)
           - ANY VT100/VT220/VT320 COMPATIBLE TERMINAL

          NOTE: THE SYSTEM REQUIRES PYTHON VERSION 3.7 OR LATER.

     PRINCIPAL FUNCTIONS:

     A. INTERACTIVE DIALOGUE - THE OPERATOR ENGAGES IN
        CONVERSATIONAL EXCHANGE WITH THE LANGUAGE MODEL.
        THE AI SUBSYSTEM PROCESSES INPUT AND GENERATES
        RESPONSES.

     B. ACTIVE TASK EXECUTION - WHEN THE AI RESPONDS WITH
        SHELL COMMANDS, THEY ARE EXECUTED AUTOMATICALLY AND
        THE RESULTS ARE FED BACK TO THE AI.  THE PROCESS
        REPEATS UNTIL THE TASK IS COMPLETE.

     C. AUTONOMOUS GOAL MODE - HIGH-LEVEL TASK DESCRIPTIONS
        ARE DECOMPOSED INTO MULTI-STEP EXECUTION SEQUENCES
        WITHOUT OPERATOR INTERVENTION.

D. OPERATOR INTERJECTION - DURING AI STREAMING, THE
         OPERATOR MAY TYPE AT ANY TIME.  THE PROMPT CHANGES
         TO "INTERJECT>" AND THE TYPED TEXT APPEARS IN THE
         FOOTER.  THE LEFT/RIGHT ARROW KEYS MOVE THE CURSOR
         WITHIN THE TEXT.  THE UP/DOWN ARROW KEYS CYCLE
         THROUGH PREVIOUS INTERJECTIONS.  PRESSING ENTER
         INTERRUPTS THE AI AND SENDS THE MESSAGE AS NEW
         INPUT.  BACKSPACE, HOME, END, AND CTRL-C ARE
         SUPPORTED.

     E. PLUGIN EXTENSION - EXTERNAL MODULES MAY REGISTER
        COMMANDS, PROVIDERS, THEMES, AND LIFECYCLE HOOKS.

F. SELF-EVOLVING MEMORY - THE SYSTEM TRACKS COMMAND
         USAGE PATTERNS AND INJECTS CONTEXT INTO THE AI
         SYSTEM PROMPT.

     G. QUANTUM ENTANGLEMENT CONTEXT - AGENTS SHARE A
         SYNCHRONIZED CONTEXT BUS.  THE CAPTAIN AGENT
         DELEGATES TO SUBAGENT TEAMS; ALL AGENTS READ AND
         WRITE TO A SHARED QUANTUM CONTEXT THAT IS
         INJECTED INTO EVERY SYSTEM PROMPT.

     H. PROMPTSHARD SYSTEM - MODULAR JOB ASSIGNMENT FILES
         WITH STRUCTURED FIELDS: OBJECTIVE, AGENT TYPE,
         MODEL CAPABILITIES, TOOLS, DOMAIN PROMPT,
         SECRETS, AND STATUS.  SHARDS ARE TEMPORARY AND
         EXPIRE ON COMPLETION.

     I. PLUGIN COMMANDS IN EXECUTE BLOCKS - PLUGIN
         COMMANDS LISTED IN BUILD_CONTEXT() AND CALLABLE
         BY AI AGENTS THROUGH STANDARD EXECUTE BLOCKS.


                                                               PAGE 2
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

2.0  PROGRAM REQUIREMENTS
     ====================

     2.1  HARDWARE REQUIREMENTS

          +--------------------------------------------------+
          | COMPONENT   | MINIMUM       | RECOMMENDED        |
          |-------------+---------------+--------------------|
          | PROCESSOR   | 486           | pentium            |
          |             | OR EQUIVALENT |                    |
          |-------------+---------------+--------------------|
          | MEMORY      | 16 MB         | 64 MB              |
          |-------------+---------------+--------------------|
          | DISK        | 2 MB          | 64 MB              |
          |-------------+---------------+--------------------|
          | TERMINAL    | ANSI (VT100)  | ANSI (VT220)       |
          |             | OR EQUIVALENT | OR EQUIVALENT      |
          +--------------------------------------------------+

      NOTE: FOR SYSTEMS WITH LIMITED PROCESSING CAPACITY
                  USE THE --SLOW-CPU FLAG.  THIS DISABLES THE
                  SPINNER THREAD, RESPONSE STREAMING, AND AUTO
                  MEMORY FLUSHING FOR REDUCED CPU OVERHEAD.

     2.2  SOFTWARE REQUIREMENTS

- PYTHON INTERPRETER, VERSION 3.7 OR LATER
           - NETWORK CONNECTION TO THE AI MODEL API ENDPOINT
           - BASH SHELL (FOR UNIX INSTALLER) OR POWERSHELL (WINDOWS)
           - Optional: Paramiko (for remote SSH functions)

                                                               PAGE 3
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

3.0  INSTALLATION PROCEDURE
     ======================

     3.1  OBTAINING THE PROGRAM

          THE PROGRAM IS DISTRIBUTED VIA GIT:

               $ git clone https://github.com/your-org/prism32.git
               $ cd prism32

     3.2  EXECUTING THE INSTALLER

          ISSUE THE FOLLOWING COMMAND AT THE SHELL PROMPT:

               $ bash install.sh

          THE INSTALLER PROGRAM SHALL:

          A. VALIDATE PYTHON SYNTAX.
          B. VERIFY THE OPERATING SYSTEM PLATFORM.
          C. BACK UP ANY EXISTING INSTALLATION.
          D. CREATE A SYMLINK AT /USR/LOCAL/BIN/PRISM32.
          E. CREATE THE RUNTIME DIRECTORY ~/.PRISM32/.
          F. PROMPT FOR API PROVIDER AND MODEL SELECTION.
          G. TEST API CONNECTIVITY.
          H. WRITE THE CONFIGURATION FILE.
          I. REFRESH STARTUP MEMORY, HARNESS SCAN, AND EVOLVE BASELINE.
          J. VERIFY INSTALLATION.

          THE INSTALLER PROMPTS FOR THE FOLLOWING:

          - ROOT PASSWORD (FOR SYMLINK CREATION)
          - API PROVIDER (1-8)
          - API ENDPOINT URL
          - MODEL IDENTIFIER
          - API KEY (IF REQUIRED)

     3.3  INITIALIZING THE SYSTEM

               $ prism32

          ALTERNATIVELY, THE SYSTEM MAY BE INVOKED WITHOUT
          INSTALLATION:

               $ python3 prism32.py --api http://127.0.0.1:8080

          WINDOWS INSTALLATION:

               PS> powershell -ExecutionPolicy Bypass -File install.ps1

          THE WINDOWS INSTALLER WRITES PRISM32 TO THE USER LOCAL
          APPLICATION DATA DIRECTORY AND CREATES A PRISM32.CMD SHIM.
          PYTHON 3.7+ IS REQUIRED.  OLDER WINDOWS SYSTEMS SUCH AS
          WINDOWS 7/VISTA-ERA INSTALLS NEED A COMPATIBLE PYTHON 3.7
          INSTALLATION; WINDOWS 10/11 CAN USE CURRENT PYTHON RELEASES.

      3.4  NETBSD/I386 PREPARATION

           NETBSD SYSTEMS MAY LACK THE REQUIRED DEPENDENCIES
           (PYTHON 3, BASH).  PREPARE THE SYSTEM AS FOLLOWS:

           A. INSTALL BASH:

                $ mkdir -p ~/tmp && cd ~/tmp
                $ ftp https://cdn.netbsd.org/pub/pkgsrc/packages/\
                      NetBSD/i386/10.1/All/bash-5.3.9.tgz
                $ tar xzf bash-5.3.9.tgz
                $ mkdir -p ~/bin
                $ cp bin/bash ~/bin/
                $ echo 'export PATH=$HOME/bin:$PATH' >> ~/.profile

           B. INSTALL PYTHON 3.12:

                $ ftp https://cdn.netbsd.org/pub/pkgsrc/packages/\
                      NetBSD/i386/10.1/All/python312-3.12.13.tgz
                $ tar xzf python312-3.12.13.tgz
                $ cp bin/python3.12 ~/bin/
                $ ln -sf ~/bin/python3.12 ~/bin/python3
                $ cp lib/libpython3.12.so* ~/lib/
                $ cp -r lib/python3.12 ~/lib/
                $ echo 'export LD_LIBRARY_PATH=$HOME/lib:\
                      $LD_LIBRARY_PATH' >> ~/.profile

           C. RUN THE PRISM32 INSTALLER:

                $ cd prism32-project
                $ source ~/.profile
                $ bash install.sh -y

           D. (OPTIONAL) MAKE A SYSTEM-WIDE COMMAND:

$ su root -c "mkdir -p /usr/local/bin && ln -sf \
                   /home/$USER/.local/bin/prism32 /usr/local/bin/prism32"

3.5  ANDROID / TERMUX INSTALLATION

     TERMUX IS THE SUPPORTED ANDROID ENVIRONMENT.  INSTALL PYTHON
     AND GIT, THEN RUN PRISM32 DIRECTLY:

              $ pkg update
              $ pkg install python git
              $ git clone https://github.com/your-org/prism32.git
              $ cd prism32
              $ python prism32.py --setup-runtime
              $ python prism32.py

     OPTIONAL STORAGE ACCESS:

              $ termux-setup-storage

     NOTES:

          - PACKAGE MANAGER DETECTS AS TERMUX PKG.
          - RUNTIME FILES ARE STORED IN ~/.PRISM32/.
          - IF COLORS OR FOOTER RENDER BADLY, USE:
              $ NO_COLOR=1 python prism32.py

3.6  SUNOS / ORACLE INSTALLATION

     ORACLE SOLARIS AND SUNOS ARE SUPPORTED WHEN PYTHON 3.7+
     IS AVAILABLE.  SUPPORTED ARCHITECTURE LABELS INCLUDE
     SPARC, SPARC64/SUN4U/SUN4V, AND SOLARIS X86/I86PC.

     ORACLE SOLARIS:

              $ python3 prism32.py --setup-runtime
              $ python3 prism32.py

     ORACLE SOLARIS PACKAGE MANAGERS ARE DETECTED AS:

              PKG       -> sudo pkg install <package>
              PKGADD    -> sudo pkgadd -d . <package>
              PKGUTIL   -> sudo pkgutil -i <package>

     ORACLE LINUX IS DETECTED THROUGH /ETC/OS-RELEASE AND USES
     ITS NATIVE PACKAGE MANAGER, USUALLY DNF OR YUM.

     NOTES:

          - PREFER /USR/BIN SH-COMPATIBLE COMMANDS.
          - AVOID GNU-ONLY FLAGS UNLESS GNU COREUTILS ARE INSTALLED.
          - NETWORK TOOLS DEFAULT TO IFCONFIG AND NETSTAT.

3.7  OBSCURE, SERVER, AND EMBEDDED TARGETS

     PRISM32 IS STDLIB-ONLY PYTHON 3.7+ AND USES BEST-EFFORT
     PLATFORM ADAPTATION.  IF PYTHON 3.7+ AND A COMMAND SHELL ARE
     AVAILABLE, PRISM32 SHOULD START AND PROVIDE AI/SHELL WORKFLOW.

     EXTRA SERVER AND EMBEDDED TARGETS INCLUDE:

          - CHROMEOS / CROSTINI, WSL / WSL2
          - DOCKER, PODMAN, KUBERNETES PODS, CI RUNNERS
          - PROXMOX VE, OPENMEDIAVAULT, UNRAID
          - TRUENAS / FREENAS, PFSENSE / OPNSENSE
          - STEAMOS / STEAM DECK
          - FEDORA COREOS, SILVERBLUE, KINOITE, RPM-OSTREE SYSTEMS
          - CLEAR LINUX, PHOTON OS, VMWARE APPLIANCES
          - NIXOS, GUIX SYSTEM, WOLFI / CHAINGUARD IMAGES
          - ILLUMOS, OPENINDIANA, OMNIOS, SMARTOS
          - OPENWRT, BUSYBOX, ENTWARE, YOCTO, BUILDROOT
          - SYNOLOGY DSM AND QNAP NAS SHELLS
          - HAIKU, QNX NEUTRINO, MINIX
          - CYGWIN, MSYS2, MINGW
          - ISH / JAILBROKEN IOS (BEST EFFORT)
          - IBM Z/OS AND IBM I PASE (EXPERIMENTAL)
          - OPENVMS (EXPERIMENTAL)

     PACKAGE MANAGERS DETECTED INCLUDE:

          APT/APT-GET, DNF, MICRODNF, TDNF, YUM, PACMAN, ZYPPER,
          APK, RPM-OSTREE, SWUPD, OPKG, IPKG, EMERGE, XBPS-INSTALL,
          EOPKG, SLACKPKG, GUIX, NIX-ENV, BREW, PORT, PKGIN,
          PKG_ADD, PKG, PKGADD, PKGUTIL, PKGMAN, SWINSTALL, INST,
          SETLD, INSTALLP, WINGET, CHOCO, SCOOP, SYNOPKG.

     FOR UNKNOWN UNIX OR EMBEDDED SYSTEMS:

              $ python3 prism32.py --setup-runtime
              $ python3 prism32.py

     IF ONLY BUSYBOX/ASH IS AVAILABLE, PREFER SIMPLE POSIX
     COMMANDS AND AVOID GNU-ONLY FLAGS.  STORE PLATFORM QUIRKS IN:

              ~/.prism32/startup_memory.md

3.8  FLOPPY DISK INSTALLATION

     PRISM32 FITS ON A STANDARD 1.44MB FLOPPY DISK (ALL FILES
     TOTAL APPROXIMATELY 260 KB, WITH 82% FREE SPACE).  THIS
     ENABLES BOOTSTRAPPING ON AIR-GAPPED OR LEGACY SYSTEMS.

     A.  BUILD THE FLOPPY IMAGE:

              $ python3 make_floppy.py

          THIS CREATES A FAT12 FLOPPY IMAGE AT
          /tmp/opencode/prism32_floppy.img.

     B.  WRITE THE IMAGE TO A FLOPPY DISK, SD CARD, OR USB FLASH
          DRIVE.  USE THE CROSS-PLATFORM INSTALLER SCRIPT:

              $ sh floppy-install.sh /tmp/opencode/prism32_floppy.img

          OR MANUALLY, IDENTIFY THE TARGET DEVICE:

          LINUX:
              $ sudo dd if=prism32_floppy.img of=/dev/sdX bs=512

          MACOS:
              $ sudo dd if=prism32_floppy.img of=/dev/diskX bs=512

          NETBSD:
              $ dd if=prism32_floppy.img of=/dev/rsdXc bs=512

     C.  INSTALL FROM THE FLOPPY:

          INSERT THE FLOPPY, THEN:

              $ mount /media/floppy   (OR /mnt/floppy)
              $ cd /media/floppy
              $ sh AUTORUN.SH

     D.  THE FLOPPY IMAGE WORKS WITH:

          - USB FLOPPY DRIVES (FLASHBASTER, etc.)
          - SD CARDS IN USB CARD READERS
          - USB FLASH DRIVES
          - VIRTUAL FLOPPY IMAGES (QEMU, VIRTUALBOX)
          - ANY DEVICE WITH >= 1.44MB CAPACITY

3.6  PERFORMANCE FLAGS

           FOR SYSTEMS WITH LIMITED PROCESSING CAPACITY:

                $ prism32 --slow-cpu

           THIS DISABLES THE SPINNER, RESPONSE STREAMING, AND
           AUTO MEMORY FLUSHING FOR REDUCED OVERHEAD.

           TO EXPLICITLY ENABLE FULL SPEED (STREAMING + SPINNER,
           WHICH IS THE DEFAULT):

                $ prism32 --turbo

           THESE PARAMETERS MAY BE PERSISTED IN THE CONFIGURATION
           FILE (SEE SECTION 8.0).


                                                               PAGE 5
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

4.0  OPERATOR COMMANDS
     =================

     THE FOLLOWING COMMANDS ARE AVAILABLE.  COMMANDS MAY BE
     PREFIXED WITH '/' TO DISTINGUISH THEM FROM CONVERSATIONAL
     INPUT TO THE AI.

     4.1  AI INTERACTION

     +----------------------------------------------------------+
     | INPUT        | FUNCTION                                  |
     |--------------+-------------------------------------------|
     | (TEXT)       | SEND TEXT TO THE AI.  IF THE AI           |
     |              | RESPONDS WITH EXECUTE BLOCKS, THE         |
     |              | COMMANDS RUN AUTOMATICALLY AND RESULTS    |
     |              | ARE FED BACK UNTIL THE TASK IS DONE.      |
     |--------------+-------------------------------------------|
     | STREAM(TEXT) | SEND TEXT WITH STREAMED RESPONSE.         |
     |--------------+-------------------------------------------|
     | GOAL (TASK)  | INITIATE AUTONOMOUS GOAL MODE.            |
     +----------------------------------------------------------+

     4.2  MANUAL TOOLS

+----------------------------------------------------------+
      | COMMAND      | FUNCTION                                  |
      |--------------+-------------------------------------------|
      | BASH (CMD)   | EXECUTE A SHELL COMMAND                   |
      | EDIT (F,TEXT)| APPEND TEXT TO A FILE                     |
      | CAT (FILE)   | DISPLAY FILE CONTENTS                     |
      | LS (PATH)    | LIST DIRECTORY CONTENTS                   |
      | FIND (PAT)   | SEARCH FOR FILES BY NAME                  |
      | GREP (P,F)   | SEARCH FILE CONTENTS                      |
      | GIT          | GIT STATUS AND DIFF SUMMARY               |
      | IMAGE (P)    | SEND IMAGE TO AI (FILE OR URL)            |
      | ARCH         | SHOW OR OVERRIDE ARCHITECTURE LABEL       |
      +----------------------------------------------------------+

     4.3  SYSTEM INFORMATION

     +----------------------------------------------------------+
     | COMMAND      | FUNCTION                                  |
     |--------------+-------------------------------------------|
     | SYSINFO      | DISPLAY SYSTEM HARDWARE AND SOFTWARE      |
     | PROCS        | DISPLAY TOP PROCESSES AND MEMORY          |
     | NET          | DISPLAY NETWORK INTERFACES AND ROUTES     |
     | PORTS        | DISPLAY LISTENING PORTS                   |
     +----------------------------------------------------------+

     4.4  SESSION MANAGEMENT

     +----------------------------------------------------------+
     | COMMAND      | FUNCTION                                  |
     |--------------+-------------------------------------------|
     | HISTORY      | DISPLAY LAST 25 MESSAGES                  |
     | EXPORT (F)   | EXPORT SESSION TO FILE                    |
     | SAVE (NAME)  | SAVE CURRENT SESSION                      |
     | LOAD (ID)    | LOAD A SAVED SESSION                      |
     | SESSION (ID) | DISPLAY SESSION DETAILS                   |
     | RESUME       | BROWSE SESSIONS WITH MESSAGE PREVIEW      |
     | DELETE (ID)  | DELETE A SAVED SESSION                    |
     | CLEAR        | CLEAR CONVERSATION HISTORY                |
     +----------------------------------------------------------+

     4.5  CONFIGURATION

+----------------------------------------------------------+
      | COMMAND      | FUNCTION                                  |
      |--------------+-------------------------------------------|
      | MODEL (NAME) | SET OR DISPLAY AI MODEL                   |
      | PROVIDER     | SWITCH PROVIDER; PROVIDER MODELS <NAME>   |
      |              | TO BROWSE MODELS                          |
      | PROVIDER API | SET API ENDPOINT URL                      |
      | PROVIDER KEY | SET API AUTHENTICATION KEY                |
      | THEME        | CYCLE TO NEXT COLOR THEME                 |
      | PLUGINS      | LIST LOADED PLUGINS                       |
      | USAGE        | SHOW OPENROUTER USAGE STATS               |
      | CONFIG       | DISPLAY CURRENT CONFIGURATION             |
      | SAVECFG      | SAVE CONFIGURATION TO DISK                |
      | LOADCFG      | LOAD CONFIGURATION FROM DISK              |
      | MEMORY       | MEMORY STATS; SHOW/EDIT STARTUP MEMORY    |
      | MEMCTX (N)   | SET MEMORY CONTEXT CHARACTER LIMIT        |
      | HARNESS      | SCAN EXTERNAL AI AGENT HARNESSES          |
      | EVOLVE       | SELF-REPAIR DOCS, BASELINE, TOOL SCAN     |
      | THINKING (L) | SET REASONING EFFORT (OFF/LOW/MED/HIGH)   |
      | DEBUG        | TOGGLE DEBUG LOGGING                      |
      | LOG          | SHOW DEBUG LOG                            |
      | MAXSTEPS (N) | SET GOAL MODE MAXIMUM STEPS               |
      | MAXTOKENS (N)| SET MAXIMUM RESPONSE TOKENS                |
      | TEMPERATURE F| SET AI TEMPERATURE (0.0-2.0)              |
      | AUTOSAVE (N) | SET AUTO-SAVE INTERVAL IN SECONDS         |
      | AGENTNAME (N)| SET DISPLAY NAME FOR AI ASSISTANT         |
      | ROOTPASS (P) | SET ROOT PASSWORD FOR SU/SUDO COMMANDS    |
      | SOUL (OPTS)  | MANAGE PERSISTENT CUSTOM RULES            |
      |              | (SHOW/SET/APPEND/CLEAR/EDIT)              |
      +----------------------------------------------------------+

     4.6  SYSTEM

     +----------------------------------------------------------+
     | COMMAND      | FUNCTION                                  |
     |--------------+-------------------------------------------|
     | HELP         | DISPLAY COMMAND REFERENCE                 |
     | QUIT         | TERMINATE THE PROGRAM                     |
     +----------------------------------------------------------+

4.7  AUTOMATION

+----------------------------------------------------------+
      | COMMAND          | FUNCTION                              |
      |------------------+---------------------------------------|
      | AUTO <TEXT>      | CREATE AUTOMATION FROM NATURAL LANGUAGE|
      | AUTO LIST        | LIST ALL AUTOMATIONS                  |
      | AUTO SHOW <ID>   | SHOW AUTOMATION DETAILS               |
      | AUTO DELETE <ID> | DELETE AN AUTOMATION                  |
      | AUTO PAUSE <ID>  | PAUSE AN AUTOMATION                   |
      | AUTO RESUME <ID> | RESUME A PAUSED AUTOMATION            |
      | AUTO RUN <ID>    | EXECUTE AN AUTOMATION IMMEDIATELY     |
      +----------------------------------------------------------+

     AUTOMATIONS ARE SCHEDULED OR ONE-SHOT TASKS THAT RUN
     AUTONOMOUSLY VIA A BACKGROUND DAEMON THREAD CHECKING
     EVERY 30 SECONDS.  SCHEDULED TASKS REPEAT AT A FIXED
     INTERVAL.  ONE-SHOT TASKS FIRE ONCE AND COMPLETE.
     WHEN TRIGGERED, A SUBAGENT IS SPAWNED TO EXECUTE THE
     TASK DESCRIPTION USING THE AI.

     EXAMPLES:
       /auto check my email every morning
       /auto write a CNN top stories report in 3 days
       /auto scan my network for open ports every hour

4.8  SLASH COMMANDS

/HELP         /QUIT         /GOAL      /THEME
            /MODEL        /PROVIDER     /PLUGINS   /DEBUG
            /LOG          /CONFIG       /MEMORY    /MEMCTX
            /THINKING     /MAXSTEPS     /SAVECFG   /LOADCFG
            /IMAGE        /SOUL         /AGENTNAME /ROOTPASS
            /STREAM       /TEMPERATURE  /TIMEOUT   /AUTOSAVE
            /AUTO         /SHARD        /QUANTUM   /ARCH
            /DELEGATE     /SPAWN        /SUBAGENTS /COLLECT
            /SKILL-CREATE /SKILL-LIST   /SKILL-LOAD /SKILL-DELETE
            /REMEMBER     /RECALL       /FORGET   /MEMORIES
            /HARNESS      /EVOLVE


                                                               PAGE 9
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

5.0  AUTONOMOUS GOAL MODE
     =====================

     THE AUTONOMOUS GOAL MODE PERMITS THE OPERATOR TO SPECIFY
     HIGH-LEVEL TASK DESCRIPTIONS.  THE AI SUBSYSTEM DECOMPOSES
     THE TASK INTO DISCRETE STEPS, ISSUES SHELL COMMANDS,
     EVALUATES RESULTS, AND PROCEEDS ITERATIVELY.

          prism32> goal "Install nginx and configure it as a
          reverse proxy on port 8080"

     THE SYSTEM SHALL:

     A. ANALYZE THE TASK DESCRIPTION.
     B. FORMULATE A SEQUENCE OF SHELL COMMANDS.
     C. EXECUTE EACH COMMAND AND CAPTURE THE OUTPUT.
     D. EVALUATE THE RESULTS AND FORMULATE NEXT STEPS.
     E. CONTINUE UNTIL COMPLETE OR MAXIMUM STEPS REACHED
        (DEFAULT: 50, CONFIGURABLE VIA MAXSTEPS COMMAND).

     THE AI USES MARKUP BLOCKS TO STRUCTURE RESPONSES:

          ```ask
          PAUSES EXECUTION TO REQUEST OPERATOR INPUT.
          ```

          ```execute
          SPECIFIES SHELL COMMANDS TO BE RUN.
          THE SYSTEM CAPTURES STDOUT, STDERR, AND EXIT CODE.
          ```

          GOAL COMPLETE
          SIGNALS TASK COMPLETION.


                                                               PAGE 10
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

5.5  ACTIVE TASK MODE
     =================

     ACTIVE TASK MODE IS THE DEFAULT BEHAVIOR IN INTERACTIVE
     MODE.  WHEN THE AI SUBSYSTEM RESPONDS WITH EXECUTE BLOCKS,
     THE SYSTEM AUTOMATICALLY RUNS THE COMMANDS AND FEEDS THE
     RESULTS BACK TO THE AI.  THIS REPEATS UNTIL THE AI
     RESPONDS WITHOUT EXECUTE BLOCKS, INDICATING COMPLETION.

     NO SEPARATE COMMAND IS REQUIRED -- THE OPERATOR SIMPLY
     PROVIDES A TASK AND THE AI CONTINUES UNTIL FINISHED.

5.5.1  OPERATOR INTERJECTION

           DURING AI STREAMING, THE OPERATOR MAY TYPE AT ANY
           TIME.  THE PROMPT CHANGES TO "INTERJECT>" AND THE
           TYPED TEXT APPEARS IN THE FOOTER, SEPARATE FROM
           THE AI OUTPUT.  THE LEFT/RIGHT ARROW KEYS MOVE
           THE CURSOR WITHIN THE TEXT.  THE UP/DOWN ARROW
           KEYS CYCLE THROUGH PREVIOUS INTERJECTIONS.
           HOME AND END JUMP TO THE START OR END OF THE
           TEXT.  PRESSING ENTER INTERRUPTS THE AI AND
           SENDS THE MESSAGE AS NEW INPUT.  BACKSPACE
           AND CTRL-C ARE SUPPORTED.

      5.5.2  SESSION RESUME

          THE RESUME COMMAND PRESENTS AN INTERACTIVE BROWSER
          FOR SAVED SESSIONS.  SELECTING A SESSION SHOWS THE
          LAST 8 MESSAGES AS PREVIEW BEFORE CONFIRMING LOAD.

          RESUME> 1

          ⤻ LOADING: INSTALL_NGINX_20260610_143022
          ──────────────────────────────────────────────────
          YOU: INSTALL NGINX WITH SSL SUPPORT
            AI: LET ME CHECK IF NGINX IS INSTALLED...
            AI: RUNNING: WHICH NGINX
            ...
          ──────────────────────────────────────────────────
          LOAD? (Y/N):


                                                               PAGE 11
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

6.0  COMMAND LINE PARAMETERS
     =======================

     PARAMETER         ALIAS  FUNCTION
     ---------         -----  --------
     --MODEL NAME      -M     SET AI MODEL IDENTIFIER

     --API URL         -A     SET API ENDPOINT URL

     --API-KEY KEY     -K     SET API AUTHENTICATION KEY

     --THEME NAME      -T     SET COLOR THEME

--NO-BOOT               SUPPRESS THE BOOT SEQUENCE

      --TEMPERATURE F         SET AI TEMPERATURE (0.0-2.0)

      --GOAL TASK       -G     INITIATE GOAL MODE AND EXIT

      --TURBO                  EXPLICITLY ENABLE STREAMING
                               AND SPINNER (DEFAULT BEHAVIOR,
                               USEFUL TO OVERRIDE SAVED CONFIG)

      --SLOW-CPU               DISABLE STREAMING AND SPINNER
                                FOR REDUCED CPU OVERHEAD
                                (HIDDEN FLAG, NOT IN --HELP)

      --SET-TIMEOUT SECS        SET COMMAND TIMEOUT AND EXIT
                                (ONE-SHOT CONFIG UTILITY)

      --UPDATE PATH|URL         UPDATE PRISM32 FROM GIT PROJECT
                                DIRECTORY OR URL AND EXIT


                                                               PAGE 12
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

7.0  COLOR THEMES
      =============

      THE SYSTEM PROVIDES 31 COLOR THEMES:

           PHOSPHOR    GREEN ON BLACK (DEFAULT)
           AMBER       AMBER ON BLACK
           CYAN        CYAN ON BLACK
           VAPOR       PINK/PURPLE WITH CYAN
           NORD        LOW-CONTRAST BLUE-GRAY
           SOLARIZED   MUTED TEAL
           NEON        HIGH-BRIGHTNESS CYAN/PINK
           RETRO       AMBER/ORANGE TONES
           ICE         WHITE WITH COOL BLUE
           OCEAN       DEEP BLUE AND CYAN
           SUNSET      WARM ORANGE WITH PINK
           FOREST      GREEN AND EARTH TONES
           PLASMA      PURPLE AND PINK
           CLEAR       TERMINAL DEFAULT (TRANSPARENT-FRIENDLY)
           GLASS       TRANSLUCENT GRAY/CYAN
           GHOST       FAINT WHITE/GREEN
           SMOKE       CHARCOAL GRAY ON LIGHT BACKGROUND
           PAPER       BLACK ON WHITE
           INK         NAVY ON WHITE
           DAYLIGHT    DARK TEAL ON WHITE
           SLATE       DARK SLATE ON WHITE

      16-COLOR COMPATIBLE THEMES (ALL TERMINALS):

           SYNTHCITY   CYAN/MAGENTA RETRO SYNTHWAVE
           OUTRUN      HOT PINK/CYAN OUTRUN AESTHETIC
           LASERDISC   DEEP BLUE/CYAN 80S LASERDISC
           VAPORDARK   PURPLE/PINK/VAPORWAVE
           CHROMECRT   BRIGHT GREEN CRT PHOSPHOR
           SGI         IRIX INDIGO TEAL/GREY
           DEC         VT220 GREEN MONOCHROME
           MONOAMBER   AMBER MONOCHROME
           IRIS        IRIX CDE GREY/BLUE
           HPTERM      HP-UX GREEN/CYAN

     CYCLE THEMES AT THE CONSOLE:

          prism32> theme

     OR AT INVOCATION:

           $ prism32 --theme amber

      16-COLOR COMPATIBILITY:

           THE 10 THEMES ABOVE (SYNTHCITY THROUGH HPTERM) USE
           ONLY STANDARD ANSI 16-COLOR CODES (30-37, 90-97,
           40-47) WITH SGR ATTRIBUTES (1-7). THEY ARE COMPATIBLE
           WITH:
           - IRIX (IRIS-ANSI TERMINAL, XSGI)
           - HP-UX (HPTERM, XTERM)
           - AIX (AIXTERM, XTERM)
           - SOLARIS (CDE, XTERM)
           - TRU64 (XTERM)
           - ALL VT100/VT220/VT320 COMPATIBLE TERMINALS
           - OLD XTERM, RXVTR, PUTTY, SCREEN, TMUX

      LEGACY OS DETECTION:

           PRISM32 AUTO-DETECTS IRIX, HP-UX, AIX, SOLARIS,
           AND TRU64 AND ADJUSTS SYSTEM COMMANDS (PS, IFCONFIG,
           NETSTAT, VMSTAT) AND CPU/RAM/UPTIME QUERIES TO USE
           OS-NATIVE UTILITIES. PACKAGE MANAGERS (INST, SWINSTALL,
           INSTALLP, PKGADD, SETLD) ARE DETECTED AUTOMATICALLY.

      CUSTOM ARCHITECTURE:

           SET PRISM32_ARCH ENV VAR TO OVERRIDE ARCHITECTURE
           LABEL. USE /ARCH SET <LABEL> TO PERSIST A CUSTOM
           MAPPING, OR ADD PATTERNS TO CUSTOM_ARCH_MAP IN
           CONFIG.JSON (SUPPORTS * WILDCARD).


                                                                PAGE 13
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

8.0  CONFIGURATION FILE
     ===================

     THE CONFIGURATION FILE IS STORED AT:

          ~/.PRISM32/CONFIG.JSON

     PARAMETERS:

+--------------------------------------------------------------+
      | PARAMETER            | DEFAULT     | FUNCTION                |
      |----------------------+-------------+-------------------------|
      | THEME                | PHOSPHOR    | COLOR THEME             |
      | API_BASE             | HTTP://     | API ENDPOINT URL        |
      |                      | 127.0.0.1   |                         |
      |                      | :8080       |                         |
| MODEL                | DEEPSEEK/   | AI MODEL IDENTIFIER     |
|                      | DEEPSEEK-V4 |                         |
|                      | -FLASH      |                         |
      | API_KEY              | ""          | API AUTHENTICATION KEY  |
      | PROVIDER             | LOCAL       | ACTIVE PROVIDER         |
      | MAX_HISTORY          | 2000        | MAX MESSAGES IN HISTORY |
      | MAX_RESPONSE_TOKENS  | 8192        | RESPONSE TOKEN LIMIT    |
      | CMD_TIMEOUT          | 600         | COMMAND TIMEOUT (SECS)  |
      | GOAL_MAX_STEPS       | 50          | MAX GOAL STEPS          |
      | AUTO_SAVE_INTERVAL   | 0           | AUTO-SAVE INTERVAL      |
      |                      |             | (0 = SAVE ON INTERACT)  |
      | STREAM               | FALSE       | ENABLE STREAMING        |
      | DEBUG                | FALSE       | DEBUG LOGGING           |
      | MAX_MEMORY_CTX       | 1024        | MEMORY CONTEXT CHARS    |
      | SLOW_CPU             | FALSE       | SLOW-CPU MODE           |
      | THINKING_EFFORT      | ""          | REASONING EFFORT        |
      |                      |             | (OFF/LOW/MEDIUM/HIGH)   |
      | AGENT_NAME           | MDS         | AI DISPLAY NAME         |
      | ROOT_PASS            | ""          | ROOT PASSWORD FOR SU    |
      | SUBAGENT_MODEL       | ""          | MODEL FOR SUBAGENTS     |
      +--------------------------------------------------------------+

     COMMANDS:

          SAVECFG    SAVE CONFIGURATION TO DISK
          LOADCFG    LOAD CONFIGURATION FROM DISK
          CONFIG     DISPLAY CURRENT CONFIGURATION


                                                               PAGE 14
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

9.0  API PROVIDER CONFIGURATION
     ==========================

     BUILT-IN PROVIDERS:

          PROVIDER     DEFAULT ENDPOINT
          --------     ----------------
          LOCAL        HTTP://127.0.0.1:8080
          OLLAMA       HTTP://LOCALHOST:11434/V1
          OPENAI       HTTPS://API.OPENAI.COM/V1
          ANTHROPIC    HTTPS://API.ANTHROPIC.COM/V1
          GROQ         HTTPS://API.GROQ.COM/OPENAI/V1
          TOGETHER     HTTPS://API.TOGETHER.XYZ/V1
          OPENROUTER   HTTPS://OPENROUTER.AI/API/V1
          CUSTOM       (OPERATOR-SPECIFIED)

SWITCHING:

           prism32> provider openrouter

      SET API ENDPOINT:

           prism32> provider api https://custom.api.com/v1

      SET API KEY:

           prism32> provider key sk-or-v1-...

      LIST PROVIDERS:

           prism32> provider list

     BROWSE MODELS:

          prism32> provider models openrouter

     ADD CUSTOM PROVIDER:

          prism32> provider add <name> <api_base> <model>


                                                               PAGE 15
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

10.0 PLUGIN PROGRAMMING INTERFACE
     =============================

     PLUGINS ARE PYTHON SOURCE FILES IN ~/.PRISM32/PLUGINS/.
     THEY ARE LOADED AUTOMATICALLY AT STARTUP.

     10.1 PLUGIN REGISTRATION

          EACH PLUGIN DEFINES A REGISTER() FUNCTION THAT RECEIVES
          A PLUGINAPI OBJECT:

          +------------------------------------------------------+
          | ATTRIBUTE/METHOD    | FUNCTION                       |
          |---------------------+--------------------------------|
          | REGISTRY            | REGISTER CUSTOM COMMANDS       |
          | REGISTER_PROVIDER() | REGISTER AI PROVIDER           |
          | REGISTER_THEME()    | REGISTER COLOR THEME           |
          | CONFIG              | ACCESS SYSTEM CONFIG           |
          | MEMORY              | READ MEMORY DATA               |
          | HISTORY             | CURRENT SESSION HISTORY        |
          | INJECT_CONTEXT()    | INJECT INTO AI SYSTEM PROMPT   |
          | HTTP_GET()          | PERFORM HTTP GET REQUEST       |
          | HTTP_POST()         | PERFORM HTTP POST REQUEST      |
          | SCHEDULE()          | SCHEDULE TIMED CALLBACK        |
          | LOG()               | WRITE DIAGNOSTIC MESSAGE       |
          +------------------------------------------------------+

     10.2 LIFECYCLE HOOKS

          DEF ON_BOOT(API):
               CALLED AT STARTUP AFTER SESSION INITIALIZATION.

          DEF ON_SHUTDOWN(API):
               CALLED DURING GRACEFUL TERMINATION.

          DEF ON_MESSAGE(API, TEXT):
               CALLED FOR EVERY OPERATOR INPUT.

          DEF ON_RESPONSE(API, TEXT):
               CALLED AFTER EVERY AI RESPONSE.

          DEF ON_COMMAND(API, NAME, ARGS, RESULT):
               CALLED AFTER ANY COMMAND IS DISPATCHED.

          DEF ON_TICK(API):
               CALLED APPROXIMATELY EVERY 5 SECONDS.

     10.3 EXAMPLE

DEF REGISTER(API):
          API.REGISTRY.REGISTER("HELLO", CMD_HELLO)
          API.REGISTRY.REGISTER("STATS", CMD_STATS)

      DEF ON_MESSAGE(API, TEXT):
          IF "PING" IN TEXT.LOWER():
              API.INJECT_CONTEXT("(PING DETECTED)")

      DEF CMD_HELLO(ARGS, HISTORY, CMD_LOG):
          PRINT("HELLO, WORLD!")

      DEF CMD_STATS(ARGS, HISTORY, CMD_LOG):
          PRINT(F"SESSION LENGTH: {LEN(HISTORY)} MESSAGES")

      # PLACE IN ~/.PRISM32/PLUGINS/HELLO.PY
      # LOADED AUTOMATICALLY ON NEXT STARTUP

      10.4 PLUGIN COMMANDS IN EXECUTE BLOCKS

           PLUGIN COMMANDS ARE LISTED IN THE AI SYSTEM PROMPT
           AND CALLABLE VIA EXECUTE BLOCKS.  BUILT-IN PLUGIN:

           WEB_SCRAPER (PLUGINS/WEB_SCRAPER.PY):
             /SCRAPE <URL>         FETCH AND DISPLAY WEB CONTENT
             AUTO-URL DETECTION    INJECTS SCRAPED TEXT WHEN URLS
                                   ARE DETECTED IN OPERATOR INPUT
             STDLIB ONLY           USES API.HTTP_GET(), NO PIP

      10.5 AI PLUGIN GENERATION PROMPT

           COPY AND PASTE THE FOLLOWING PROMPT TO ANY AI CHATBOT
           TO GENERATE A PRISM32 PLUGIN:

```
You are a Python 3.7+ code generator. Generate a PRISM32 plugin
following these specifications:

## File location
Save to ~/.prism32/plugins/<name>.py

## API object (PluginAPI) passed to register()
- api.registry: CommandRegistry
  - .register(name, handler, aliases=[], description="", category="", hidden=False)
    handler sig: def handler(args_str, history, cmd_log): print(...)
  - .dispatch_capture(name, args_str) -> str  (captures print output)
  - .get(name) -> Command
  - .names() -> set
- api.register_provider(id, **config)  -- register AI provider
- api.register_theme(name, **colors)   -- register color theme
- api.config: Config object (MODEL, API_BASE, API_KEY, THEME, etc.)
- api.memory: dict {command_stats, error_patterns, session_count, ...}
- api.history: list of {"role": ..., "content": ...} dicts
- api.inject_context(text)  -- add text to AI system prompt
- api.schedule(interval_sec, callback)  -- periodic callback
- api.http_get(url, headers={}, timeout=10) -> str
- api.http_post(url, data=None, headers={}, timeout=10) -> str
- api.log(msg)  -- print with [plugin:name] prefix
- api.plugins: dict of loaded modules

## Lifecycle hooks (define any subset in your module)
def on_boot(api):          -- called at startup
def on_shutdown(api):      -- called on graceful exit
def on_message(api, text):  -- called per user input
def on_response(api, text): -- called per AI response
def on_command(api, name, args, result): -- called after any command
def on_tick(api):           -- called every ~5 seconds

## Module-level function required
def register(api):
    # Register commands, providers, themes, hooks here

## Requirements
- Pure stdlib Python 3.7+ only (no pip)
- Use api.log() for diagnostics, not print()
- Plugin path: ~/.prism32/plugins/<name>.py
- Loaded automatically on next startup
```

      10.6 EXAMPLE USAGE

           PROVIDE THE FOLLOWING TO THE AI CHATBOT AFTER THE ABOVE
           PROMPT TO GENERATE A SPECIFIC PLUGIN:

```
Generate a PRISM32 plugin called "weather" that:
1. Registers a /weather <city> command
2. Uses api.http_get() to fetch weather from wttr.in
3. Displays temperature and conditions in a styled box
4. No pip dependencies
```


11.0 QUANTUM ENTANGLEMENT SHARED CONTEXT
     =====================================

     A THREAD-SAFE KEY-VALUE STORE SYNCHRONIZING DATA BETWEEN
     THE CAPTAIN AGENT AND ALL SUBAGENTS.  CONTEXT IS INJECTED
     INTO EVERY SYSTEM PROMPT.  A "Q" INDICATOR APPEARS IN THE
     STATUS BAR WHEN ACCESSED.

     11.1 COMMANDS

             /QUANTUM                  VIEW ALL KEYS
             /QUANTUM <KEY>:<VALUE>    SET A KEY
             /QUANTUM <KEY>:           GET A KEY

     11.2 SUBAGENT ACCESS VIA EXECUTE BLOCKS

             ```execute
             /quantum target_url:https://example.com
             ```

     11.3 AUTO-SYNC

             subagent:<id>:result    RESULT TEXT
             subagent:<id>:task       ORIGINAL TASK
             secret:<id>:<name>      APPROVED SECRETS


12.0 PROMPTSHARD SYSTEM
     ====================

     PROMPTSHARD.MD (~/.PRISM32/PROMPTSHARD.MD) IS A MODULAR
     JOB ASSIGNMENT FILE.  THE CAPTAIN AGENT READS THE SHARD
     AND DEPLOYS SPECIALIZED SUBAGENT TEAMS.

     12.1 FORMAT

           # PROMPTSHARD: <ID>
           ## OBJECTIVE: <GOAL>
           ## AGENT: CAPTAIN|SPECIALIST
           ## MODEL_CAPABILITIES: CHAT,VISION,3D,FAST
           ## TOOLS: BASH,GIT,PYTHON3
           ## PROMPT: |-
             YOU ARE AN EXPERT IN <FIELD>.
           ## SECRETS_REQUESTED: <NAME>
           ## STATUS: ACTIVE|COMPLETED|EXPIRED

     12.2 SECRETS VAULT

        SECRETS STORED IN ~/.PRISM32/.SECRETS.JSON (SEPARATE
        FROM THE PROMPT TO PREVENT INJECTION).

             prism32> /shard secrets db_pass:mypassword

     12.3 COMMANDS

             /SHARD [SHOW]          DISPLAY CURRENT SHARD
             /SHARD DEPLOY          SPAWN SUBAGENT FROM SHARD
             /SHARD COMPLETE        MARK AS DONE
             /SHARD SET <K>:<V>    UPDATE A FIELD
             /SHARD SECRETS         MANAGE SECRETS VAULT

     12.4 CAPTAIN AGENT TEAMS

        THE CAPTAIN COORDINATES SPECIALIST TEAMS:

           CAPTAIN
              |-- /DELEGATE SCAN PORTS   (SUBAGENT A)
              |-- /SPAWN WRITE REPORT    (SUBAGENT B)
              V
           QUANTUM SYNC -> /COLLECT A, B -> RESULTS


13.0 DIAGNOSTIC INFORMATION
      =======================

      13.1 LOG FILES

          ~/.PRISM32/INSTALL.LOG    INSTALLATION LOG
          ~/.PRISM32/DEBUG.LOG      DEBUG LOG (/DEBUG COMMAND)
          ~/.PRISM32/ERRORLOG.TXT   GOAL MODE CAPTURE

     13.2 MEMORY SYSTEM

          ~/.PRISM32/MEMORY.JSON TRACKS COMMAND USAGE, ERROR
          PATTERNS, SYSTEM PROFILE, AND SESSION COUNT.  AUTOMATICALLY
          CONSOLIDATED TO TOP 30 COMMANDS AND TOP 15 ERROR PATTERNS.

          ~/.PRISM32/STARTUP_MEMORY.MD IS A HUMAN-EDITABLE STARTUP
          MEMORY FILE.  IT IS INJECTED INTO AI CONTEXT AT STARTUP
          AND IS INTENDED FOR HARDWARE NOTES, SOFTWARE TIPS,
          TERMINAL/SHELL QUIRKS, USER WORKFLOW, AND RECURRING FIXES.

          COMMANDS:

               /MEMORY             DISPLAY MEMORY STATS
               /MEMORY SHOW        SHOW STARTUP_MEMORY.MD
               /MEMORY EDIT        EDIT STARTUP_MEMORY.MD
               /MEMORY APPEND TXT  APPEND A NOTE
               /MEMORY REFRESH     REFRESH AUTO-DETECTED SNAPSHOT
               /MEMORY PATH        SHOW FILE LOCATIONS
               /MEMCTX N           SET CONTEXT CHARACTER LIMIT (0=OFF)

13.3 HARNESS ABSORPTION

           ~/.PRISM32/HARNESSES.JSON STORES DETECTED EXTERNAL AI
           AGENT COMMANDS SUCH AS OPENCODE, CODEX, CLAUDE CODE,
           KIMICODE, AIDER, GEMINI, GOOSE, AND CURSOR-AGENT.
           DETECTED CAPABILITIES ARE INJECTED INTO THE AI SYSTEM
           CONTEXT SO PRISM32 CAN USE THEM AS ADDITIONAL TOOLS.

           COMMANDS:

               /HARNESS             SHOW DETECTED HARNESSES
               /HARNESS SCAN        RESCAN PATH FOR AI AGENT CLIS
               /HARNESS CONTEXT     SHOW AGENT-VISIBLE CONTEXT
               /HARNESS DELEGATE T  SPAWN SUPER SUBAGENT FOR TASK T
               /HARNESS PATH        SHOW HARNESSES.JSON LOCATION

13.4 EVOLVE MODE

           ~/.PRISM32/EVOLVE/ CONTAINS SYSTEM DOCUMENTATION,
           TOOL SCANS, TEMPORARY PLUGIN SPACE, AND A BASELINE COPY
           OF PRISM32.PY PLUS A DEFAULT CONFIG SNAPSHOT.

           EVOLVE MODE INJECTS SELF-REPAIR AND PLUGIN-CREATION
           DOCUMENTATION INTO AI CONTEXT.  IT HELPS THE AGENT
           COMPARE AGAINST THE BASELINE, CREATE TEMPORARY OR
           PERMANENT PLUGINS, AND SEE WHICH LOCAL TOOLS EXIST.

           COMMANDS:

               /EVOLVE ON              ENABLE EVOLVE CONTEXT
               /EVOLVE OFF             DISABLE EVOLVE CONTEXT
               /EVOLVE DOCS            SHOW GENERATED DOCS
               /EVOLVE TOOLS           RESCAN LOCAL TOOLS
               /EVOLVE DIFF            DIFF CURRENT FILE VS BASELINE
               /EVOLVE BASELINE        SHOW BASELINE PATHS
               /EVOLVE PLUGIN TEMP N   CREATE TEMP PLUGIN TEMPLATE
               /EVOLVE PLUGIN PERMANENT N CREATE PERMANENT TEMPLATE

13.5 API USAGE

           /USAGE DISPLAYS API CONSUMPTION (OPENROUTER ONLY).

13.6 SESSION STORAGE

           SESSIONS ARE AUTO-SAVED TO ~/.PRISM32/SESSIONS/
           AFTER EACH INTERACTION (CONFIGURABLE VIA AUTOSAVE
           COMMAND).  USE THE RESUME COMMAND TO BROWSE AND
           LOAD.


                                                               PAGE 18
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

12.0 RESTRICTIONS AND LIMITATIONS
     =============================

     12.1 NETWORK DEPENDENCY

          THE SYSTEM REQUIRES CONNECTIVITY TO THE AI MODEL API
          ENDPOINT.

     12.2 AI MODEL CHARACTERISTICS

          CAPABILITIES ARE DETERMINED BY THE UNDERLYING LANGUAGE
          MODEL.  THE SYSTEM PROVIDES NO GUARANTEE OF CORRECTNESS
          OR SUITABILITY OF AI-GENERATED CONTENT.

     12.3 SHELL COMMAND EXECUTION

          COMMANDS ARE INVOKED WITH THE PRIVILEGES OF THE
          CURRENT USER.  CAUTION IS ADVISED IN AUTONOMOUS
          MODES.

     12.4 MICROSOFT WINDOWS LIMITATIONS

          WINDOWS IS SUPPORTED WHEN PYTHON 3.7+ IS AVAILABLE.
          PRACTICAL LEGACY FLOOR: WINDOWS 7/VISTA-ERA SYSTEMS WITH
          A COMPATIBLE PYTHON 3.7 INSTALLATION.  WINDOWS 10/11 ARE
          SUPPORTED WITH CURRENT PYTHON RELEASES.

          THE READLINE MODULE IS NOT AVAILABLE, LIMITING COMMAND
          HISTORY AND LINE EDITING.  SELECT() DOES NOT SUPPORT STDIN
          POLLING, SO STREAMING INTERJECTION IS DISABLED ON WINDOWS.
          OLD CONSOLES WITHOUT ANSI/VT SUPPORT FALL BACK TO A PLAIN
          PROMPT INSTEAD OF THE PERSISTENT FOOTER.

          NATIVE WINDOWS FALLBACKS ARE USED FOR COMMON SYSTEM TOOLS:
          PROCS=TASKLIST, NET=IPCONFIG/ROUTE PRINT, PORTS=NETSTAT,
          GREP=FINDSTR, FIND=DIR.

     12.5 OBSCURE AND EMBEDDED PLATFORM LIMITATIONS

          PRISM32 CAN RUN ONLY WHERE PYTHON 3.7+ AND A USABLE SHELL
          EXIST.  SOME SERVER AND EMBEDDED OPERATING SYSTEMS HAVE
          NON-GNU USERLANDS, LIMITED TERMINALS, READ-ONLY ROOT FILE
          SYSTEMS, MISSING SSL CERTIFICATES, OR NO PACKAGE MANAGER.

          ON UNKNOWN UNIX, BUSYBOX, SOLARIS, AIX, HP-UX, IRIX,
          TRU64, QNX, NAS, AND APPLIANCE SHELLS, PREFER PORTABLE
          POSIX SH COMMANDS AND AVOID GNU-ONLY OPTIONS UNLESS
          DETECTED.  USE /MEMORY EDIT TO RECORD PLATFORM QUIRKS.

          IN CONTAINERS, CI RUNNERS, WSL, AND CHROMEOS/CROSTINI,
          NETWORKING, MOUNTS, SYSTEMD, PRIVILEGE ESCALATION, AND
          PACKAGE INSTALLATION MAY BE NAMESPACE-LIMITED.  INSPECT
          THE ENVIRONMENT BEFORE MODIFYING SYSTEM STATE.

          ON APPLIANCE OR IMMUTABLE SYSTEMS SUCH AS PROXMOX,
          TRUENAS, PFSENSE, OPNSENSE, UNRAID, STEAMOS, FEDORA
          COREOS/SILVERBLUE/KINOITE, CLEAR LINUX, AND PHOTON OS,
          USE VENDOR-SUPPORTED TOOLS AND AVOID HOST STORAGE OR
          NETWORK CHANGES UNLESS EXPLICITLY REQUESTED.

     12.6 DISCLAIMER

          THIS SOFTWARE IS PROVIDED WITHOUT WARRANTY OF ANY
          KIND, EXPRESS OR IMPLIED.  SEE THE LICENSE FILE FOR
          COMPLETE TERMS.


                                                               PAGE 19
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

13.0 SYSTEM MESSAGES
     ================

     +----------------------------------------------------------+
     | MESSAGE                         | MEANING                |
     |---------------------------------+------------------------|
     | CONNECTION FAILED               | UNABLE TO REACH API    |
     |                                 | ENDPOINT               |
     |---------------------------------+------------------------|
     | API ERROR, RETRYING...          | API RETURNED ERROR.    |
     |                                 | RETRYING WITH REDUCED  |
     |                                 | CONTEXT                |
     |---------------------------------+------------------------|
     | [PLUGIN] LOADED: NAME           | PLUGIN MODULE LOADED   |
     |                                 | SUCCESSFULLY           |
     |---------------------------------+------------------------|
     | [PLUGIN] ERROR LOADING NAME     | PLUGIN FAILED TO LOAD  |
     |---------------------------------+------------------------|
     | GOAL COMPLETE                   | GOAL MODE FINISHED     |
     |                                 | SUCCESSFULLY           |
     |---------------------------------+------------------------|
     | GOAL FAILED                     | GOAL MODE TERMINATED   |
     |                                 | WITH ERROR             |
     |---------------------------------+------------------------|
     | SESSION SAVED: ID               | SESSION PERSISTED TO   |
     |                                 | DISK                   |
     |---------------------------------+------------------------|
     | SHUTTING DOWN...                | SYSTEM IS TERMINATING  |
     +----------------------------------------------------------+


                                                               PAGE 20
PRISM32(TM) V6.7 OPERATOR'S GUIDE                         MDS-P32-67

14.0 INDEX
     =======

- A -

     ACTIVE TASK MODE .................... 10
     ANDROID / TERMUX .................... 3
     API ENDPOINT ........................ 13, 14
     API KEY ............................. 11, 13
     AUTOMATION SYSTEM ................... 9
     AUTONOMOUS GOAL MODE ................ 9
     AUTO-SAVE INTERVAL .................. 13

     - C -

     CAPTAIN AGENT TEAMS ................. 11, 12
     COLOR THEMES ........................ 12
     COMMAND LINE PARAMETERS ............. 11
     CONFIGURATION FILE .................. 13
     CURSOR MANAGEMENT ................... 10

     - D -

     DEBUG LOG ........................... 17

     - E -

      EMBEDDED TARGETS .................... 3
      EVOLVE MODE ......................... 17

     - G -

     GOAL MODE ........................... 9

     - H -

      HARNESS ABSORPTION .................. 17
      HISTORY COMMAND ..................... 7
      HOOKS, LIFECYCLE .................... 15

     - I -

     INSTALLATION ........................ 3
     INTERJECT, OPERATOR ................. 10

     - L -

     LICENSE ............................. 18
     LIFECYCLE HOOKS .................... 15
     LOG FILES ........................... 17

     - M -

     MEMORY SYSTEM ....................... 17
     MESSAGES, SYSTEM .................... 19
     MODEL, AI ........................... 11

- P -

      PLUGINS ............................. 15
      PLUGIN COMMANDS IN EXECUTE BLOCKS .. 16
      PLUGIN GENERATION PROMPT ........... 16
      PROMPTSHARD SYSTEM .................. 17
     PROVIDER CONFIGURATION .............. 14

     - Q -

     QUANTUM ENTANGLEMENT CONTEXT ....... 11

     - R -

     RESUME COMMAND ...................... 10

     - S -

     SCRAPE COMMAND ...................... 15
     SECRETS VAULT ....................... 12
     SESSION MANAGEMENT .................. 7
     SHELL COMMAND EXECUTION ............. 7
      SLOW-CPU MODE .................... 11, 13
      SOLARIS / SUNOS / ORACLE ............ 3
      STARTUP MEMORY ...................... 17
      SUBAGENTS ........................... 10
     SYSTEM MESSAGES ..................... 19

     - T -

     THEMES, COLOR ....................... 12
     TICK INTERVAL ....................... 16

     - W -

     WINDOWS LIMITATIONS ................. 18


END OF DOCUMENT
