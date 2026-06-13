PRISM32(TM) V6.6 - INTERACTIVE TERMINAL AGENT
MEGADYNE SYSTEMS (MDS) - LICENSED SOFTWARE

                      (C) COPYRIGHT 2026
           MEGADYNE SYSTEMS - ALL RIGHTS RESERVED

                      DOCUMENT NO. MDS-P32-66
                    FIRST EDITION (JUNE 2026)


                        -----------------
                        PRISM32(TM) V6.6
                        -----------------

                   MEGADYNE SYSTEMS CORPORATION

                     OPERATOR'S GUIDE AND
                 SYSTEM PROGRAMMING REFERENCE



                                                       MDS-P32-66

PRISM32(TM) V6.6 OPERATOR'S GUIDE

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
  11.0 DIAGNOSTIC INFORMATION ..................................... 17
  12.0 RESTRICTIONS AND LIMITATIONS ............................... 18
  13.0 SYSTEM MESSAGES ............................................ 19
  14.0 INDEX ...................................................... 20


                                                               PAGE 1
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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

     D. OPERATOR INTERJECTION - DURING ACTIVE TASKS, THE
        OPERATOR MAY TYPE MESSAGES AT ANY TIME.  THESE ARE
        QUEUED AND DELIVERED TO THE AI BETWEEN STEPS, NEVER
        MID-COMMAND.  ALT+^ RECALLS THE LAST INTERJECTION.

     E. PLUGIN EXTENSION - EXTERNAL MODULES MAY REGISTER
        COMMANDS, PROVIDERS, THEMES, AND LIFECYCLE HOOKS.

     F. SELF-EVOLVING MEMORY - THE SYSTEM TRACKS COMMAND
        USAGE PATTERNS AND INJECTS CONTEXT INTO THE AI
        SYSTEM PROMPT.


                                                               PAGE 2
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

2.0  PROGRAM REQUIREMENTS
     ====================

     2.1  HARDWARE REQUIREMENTS

          +--------------------------------------------------+
          | COMPONENT   | MINIMUM       | RECOMMENDED        |
          |-------------+---------------+--------------------|
          | PROCESSOR   | 486           | pentium            |
          |             | OR EQUIVALENT |                    |
          |-------------+---------------+--------------------|
          | MEMORY      | 64 MB         | 512 MB             |
          |-------------+---------------+--------------------|
          | DISK        | 10 MB         | 100 MB             |
          |-------------+---------------+--------------------|
          | TERMINAL    | ANSI (VT100)  | ANSI (VT220)       |
          |             | OR EQUIVALENT | OR EQUIVALENT      |
          +--------------------------------------------------+

          NOTE: FOR SYSTEMS WITH LIMITED PROCESSING CAPACITY
                USE THE --SLOW-CPU FLAG IF .  THIS DISABLES THE
                SPINNER THREAD, RESPONSE STREAMING, AND AUTO
                MEMORY FLUSHING FOR REDUCED OVERHEAD.

     2.2  SOFTWARE REQUIREMENTS

          - PYTHON INTERPRETER, VERSION 3.7 OR LATER
          - NETWORK CONNECTION TO THE AI MODEL API ENDPOINT
          - BASH SHELL (FOR THE INSTALLER PROGRAM)
          - OPTIONAL: PARAMIKO (FOR REMOTE SSH FUNCTIONS)


                                                               PAGE 3
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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
          I. VERIFY INSTALLATION.

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

      3.5  SLOW-CPU MODE

          FOR SYSTEMS WITH LIMITED PROCESSING CAPACITY:

               $ prism32 --slow-cpu

          THIS PARAMETER MAY BE PERSISTED IN THE CONFIGURATION
          FILE (SEE SECTION 8.0).


                                                               PAGE 5
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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
     | PROVIDER (N) | SWITCH PROVIDER; PROVIDER MODELS <NAME>   |
     |              | TO BROWSE MODELS                          |
     | THEME        | CYCLE TO NEXT COLOR THEME                 |
     | PLUGINS      | LIST LOADED PLUGINS                       |
     | API (URL)    | SET API ENDPOINT                          |
     | APIKEY (KEY) | SET API AUTHENTICATION KEY                |
     | USAGE        | SHOW OPENROUTER USAGE STATS               |
     | CONFIG       | DISPLAY CURRENT CONFIGURATION             |
     | SAVECFG      | SAVE CONFIGURATION TO DISK                |
     | LOADCFG      | LOAD CONFIGURATION FROM DISK              |
     | MEMORY       | DISPLAY SELF-EVOLVING MEMORY STATS        |
     | MEMCTX (N)   | SET MEMORY CONTEXT CHARACTER LIMIT        |
     | THINKING (L) | SET REASONING EFFORT (OFF/LOW/MED/HIGH)   |
     | DEBUG        | TOGGLE DEBUG LOGGING                      |
     | MAXSTEPS (N) | SET GOAL MODE MAXIMUM STEPS               |
     | MAXTOKENS (N)| SET MAXIMUM RESPONSE TOKENS                |
     | TEMPERATURE F| SET AI TEMPERATURE (0.0-2.0)              |
     | AUTOSAVE (N) | SET AUTO-SAVE INTERVAL IN SECONDS         |
     +----------------------------------------------------------+

     4.6  SYSTEM

     +----------------------------------------------------------+
     | COMMAND      | FUNCTION                                  |
     |--------------+-------------------------------------------|
     | HELP         | DISPLAY COMMAND REFERENCE                 |
     | QUIT         | TERMINATE THE PROGRAM                     |
     +----------------------------------------------------------+

     4.7  SLASH COMMANDS

          /HELP         /QUIT         /GOAL      /THEME
          /MODEL        /PROVIDER     /PLUGINS   /DEBUG
          /LOG          /CONFIG       /MEMORY    /MEMCTX
          /THINKING     /MAXSTEPS     /SAVECFG   /LOADCFG


                                                               PAGE 9
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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

          DURING ACTIVE TASK EXECUTION, THE OPERATOR MAY TYPE
          MESSAGES AT ANY TIME.  THESE ARE:

          A. QUEUED DURING AI STREAMING - COLLECTED BETWEEN
             TOKENS, DELIVERED AFTER THE RESPONSE.

          B. QUEUED DURING COMMAND EXECUTION - COLLECTED
             BETWEEN COMMANDS, DELIVERED ON THE NEXT AI
             ITERATION.  NEVER MID-COMMAND.

          C. DELIVERED AS "(INTERJECTION: <TEXT>)" USER
             MESSAGES IN THE SESSION HISTORY.

     5.5.2  INTERJECT RECALL (ALT+^)

          PRESSING CTRL+^ (ASCII 0X1E, OR ALT+^ ON MANY
          TERMINALS) AT THE PROMPT RECALLS THE LAST
          INTERJECTED TEXT FOR EDITING OR RESUBMISSION.
          THE PROMPT SHOWS A "(⚑ INTERJECT: <TEXT>)"
          INDICATOR WHEN RECALL TEXT IS AVAILABLE.

     5.5.3  SESSION RESUME

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
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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

     --SLOW-CPU               ENABLE SLOW-CPU MODE:
                              DISABLES SPINNER THREAD,
                              STREAMING, AND AUTO MEMORY FLUSH


                                                               PAGE 12
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

7.0  COLOR THEMES
     =============

     THE SYSTEM PROVIDES 13 COLOR THEMES:

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

     CYCLE THEMES AT THE CONSOLE:

          prism32> theme

     OR AT INVOCATION:

          $ prism32 --theme amber


                                                               PAGE 13
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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
     | MODEL                | MODEL.GGUF  | AI MODEL IDENTIFIER     |
     | API_KEY              | ""          | API AUTHENTICATION KEY  |
     | PROVIDER             | LOCAL       | ACTIVE PROVIDER         |
     | MAX_HISTORY          | 2000        | MAX MESSAGES IN HISTORY |
     | MAX_RESPONSE_TOKENS  | 8192        | RESPONSE TOKEN LIMIT    |
     | CMD_TIMEOUT          | 300         | COMMAND TIMEOUT (SECS)  |
     | TIMEOUT              | 120         | API TIMEOUT (SECS)      |
     | GOAL_MAX_STEPS       | 50          | MAX GOAL STEPS          |
     | AUTO_SAVE_INTERVAL   | 120         | AUTO-SAVE INTERVAL (S)  |
     | STREAM               | TRUE        | ENABLE STREAMING        |
     | DEBUG                | FALSE       | DEBUG LOGGING           |
     | NO_BOOT              | FALSE       | SUPPRESS BOOT           |
     | MAX_MEMORY_CTX       | 1024        | MEMORY CONTEXT CHARS    |
     | SLOW_CPU             | FALSE       | SLOW-CPU MODE           |
     | THINKING_EFFORT      | ""          | REASONING EFFORT        |
     |                      |             | (OFF/LOW/MEDIUM/HIGH)   |
     +--------------------------------------------------------------+

     COMMANDS:

          SAVECFG    SAVE CONFIGURATION TO DISK
          LOADCFG    LOAD CONFIGURATION FROM DISK
          CONFIG     DISPLAY CURRENT CONFIGURATION


                                                               PAGE 14
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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

     LIST PROVIDERS:

          prism32> provider list

     BROWSE MODELS:

          prism32> provider models openrouter

     ADD CUSTOM PROVIDER:

          prism32> provider add <name> <api_base> <model>


                                                               PAGE 15
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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

          DEF ON_MESSAGE(API, TEXT):
              IF "PING" IN TEXT.LOWER():
                  API.INJECT_CONTEXT("(PING DETECTED)")

          DEF CMD_HELLO(ARGS, HISTORY, CMD_LOG):
              PRINT("HELLO, WORLD!")


                                                               PAGE 17
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

11.0 DIAGNOSTIC INFORMATION
     =======================

     11.1 LOG FILES

          ~/.PRISM32/INSTALL.LOG    INSTALLATION LOG
          ~/.PRISM32/DEBUG.LOG      DEBUG LOG (/DEBUG COMMAND)
          ~/.PRISM32/ERRORLOG.TXT   GOAL MODE CAPTURE

     11.2 MEMORY SYSTEM

          ~/.PRISM32/MEMORY.JSON TRACKS COMMAND USAGE, ERROR
          PATTERNS, AND SESSION COUNT.  AUTOMATICALLY CONSOLIDATED
          TO TOP 30 COMMANDS AND TOP 15 ERROR PATTERNS.

          COMMANDS:

               /MEMORY    DISPLAY MEMORY STATS
               /MEMCTX N  SET CONTEXT CHARACTER LIMIT (0=OFF)

     11.3 API USAGE

          /USAGE DISPLAYS API CONSUMPTION (OPENROUTER ONLY).

     11.4 SESSION STORAGE

          SESSIONS ARE AUTO-SAVED TO ~/.PRISM32/SESSIONS/ EVERY
          120 SECONDS (CONFIGURABLE VIA AUTOSAVE COMMAND).
          USE THE RESUME COMMAND TO BROWSE AND LOAD.


                                                               PAGE 18
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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

          THE READLINE MODULE IS NOT AVAILABLE, LIMITING COMMAND
          HISTORY AND LINE EDITING.
          THE SIGTERM SIGNAL IS NOT AVAILABLE (USE CTRL+C).
          SELECT() DOES NOT SUPPORT STDIN POLLING.
          THE FIND AND GREP COMMANDS USE OS-FALLBACK PATHS.

     12.5 DISCLAIMER

          THIS SOFTWARE IS PROVIDED WITHOUT WARRANTY OF ANY
          KIND, EXPRESS OR IMPLIED.  SEE THE LICENSE FILE FOR
          COMPLETE TERMS.


                                                               PAGE 19
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

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
PRISM32(TM) V6.6 OPERATOR'S GUIDE                         MDS-P32-66

14.0 INDEX
     =======

     - A -

     ACTIVE TASK MODE .................... 10
     API ENDPOINT ........................ 13, 14
     API KEY ............................. 11, 13
     AUTONOMOUS GOAL MODE ................ 9
     AUTO-SAVE INTERVAL .................. 13

     - C -

     COLOR THEMES ........................ 12
     COMMAND LINE PARAMETERS ............. 11
     CONFIGURATION FILE .................. 13
     CURSOR MANAGEMENT ................... 10

     - D -

     DEBUG LOG ........................... 17

     - G -

     GOAL MODE ........................... 9

     - H -

     HISTORY COMMAND ..................... 7
     HOOKS, LIFECYCLE .................... 15

     - I -

     INSTALLATION ........................ 3
     INTERJECT, OPERATOR ................. 10
     INTERJECT RECALL (ALT+^) ............ 10

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
     PROVIDER CONFIGURATION .............. 14

     - R -

     RESUME COMMAND ...................... 10

     - S -

     SESSION MANAGEMENT .................. 7
     SHELL COMMAND EXECUTION ............. 7
     SLOW-CPU MODE ....................... 11, 13
     SYSTEM MESSAGES ..................... 19

     - T -

     THEMES, COLOR ....................... 12
     TICK INTERVAL ....................... 16

     - W -

     WINDOWS LIMITATIONS ................. 18


END OF DOCUMENT
