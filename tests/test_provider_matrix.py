#!/usr/bin/env python3
"""
prism32 v7.2.8 — Provider API-key wiring verification matrix.

Verifies, for EVERY provider in PROVIDER_REGISTRY (built-ins + config-loaded
+ user-added), the full key lifecycle:

  F1  ACTIVE-KEY SET     /provider key <name> <key> when <name> is active
                         → Config.API_KEY (REPL handler ~L10399 / set_provider_entry L4431)
  F2  BOOT LIFT         config.json empty top-level api_key + providers.<name>.api_key
                         → load_config lifts (L4519-4526)
  F3  NON-EMPTY WINS    top-level key beats provider key
  F4  SWITCH            _switch_main_provider / _apply_model_selection wires
                         registry default_key; away+back, same-provider repick
  F5  SUBAGENT ROUTING  resolve_runtime(provider) → (base, key, model) +
                         header capture through ask_ai (Authorization/x-api-key)
  F6  SESSION-ONLY KEYS --api-key: session key works, disk key survives saves
  F7  PROVIDER TEST     cmd_provider_test(name) sends the provider's OWN key
  F8  INSTALLER KEYS    config.json exactly as install.sh writes it
  F9  CUSTOM BASE       base override must not break key routing
  F10 CLEARED KEYS      '-' wizard / api_key="" clears; no stale key

Run:  python3 -m pytest /tmp/opencode/test_provider_matrix.py -v
      (or: python3 /tmp/opencode/test_provider_matrix.py)

REPORT ONLY harness — no repo files touched. Scratch config.json lives in a
per-test tmpdir; all network is faked via urlopen_with_ssl monkeypatch.
A machine-readable table is dumped to /tmp/opencode/matrix_results.txt by the
last test in the file.
"""
import sys, os, io, json, shutil, tempfile, unittest, contextlib

REPO = os.environ.get("PRISM32_REPO", "/home/labcomputer5/Documents/Programs/Palmcoder95")
sys.path.insert(0, REPO)
exec(open(os.path.join(REPO, "prism32.py")).read().split("if __name__")[0])

# ── universe of providers under test (snapshot right after exec) ──────────
ALL_PROVIDERS = sorted(PROVIDER_REGISTRY)                       # 11 built-ins
FACTORY = {k: dict(v) for k, v in PROVIDER_REGISTRY.items()}    # factory rows
FACTORY_BASE = {k: (v.get("api_base") or "") for k, v in FACTORY.items()}
SYNTH_PROVIDERS = ["instprov", "userprov"]                      # config/user-added
RESULTS = []   # (flow, provider, status, evidence)

def record(flow, prov, ok, evidence):
    RESULTS.append((flow, prov, "PASS" if ok else "FAIL", str(evidence)[:220]))


class FakeResp:
    def __init__(self, body):
        self._b = body.encode() if isinstance(body, str) else body
    def read(self):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


OPENAI_BODY = json.dumps({"choices": [{"message": {"content": "ok"},
                                       "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                                    "total_tokens": 2}})
ANTHROPIC_BODY = json.dumps({"content": [{"type": "text", "text": "ok"}],
                             "usage": {"input_tokens": 1, "output_tokens": 1}})
MODELS_BODY = json.dumps({"data": [{"id": "m1"}, {"id": "m2"}]})


class MatrixHarness(unittest.TestCase):
    """Snapshot/restore everything the flows mutate; fake all network."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="p32mtx_")
        self.cfgfile = os.path.join(self.tmp, "config.json")
        # snapshot Config class state
        self._snap = {attr: getattr(Config, attr) for attr in
                      ("CONFIG_FILE", "API_KEY", "API_BASE", "PROVIDER", "MODEL",
                       "CUSTOM_API_BASE", "SUBAGENT_MODEL", "SUBAGENT_PROVIDER",
                       "MAX_RESPONSE_TOKENS")}
        self._sok = Config.SESSION_ONLY_KEYS
        self._reg = {k: dict(v) for k, v in PROVIDER_REGISTRY.items()}
        self._urlopen = urlopen_with_ssl
        self._reachable = check_endpoint_reachable
        Config.CONFIG_FILE = self.cfgfile
        Config.SESSION_ONLY_KEYS = set()
        # fake network: capture every request, return canned bodies
        self.captured = []

        def fake_urlopen(req, **kw):
            url = req.full_url
            hdrs = {k.lower(): v for k, v in req.header_items()}
            self.captured.append({"url": url, "headers": hdrs})
            if "/v1/models" in url:
                return FakeResp(MODELS_BODY)
            if "/v1/messages" in url:
                return FakeResp(ANTHROPIC_BODY)
            return FakeResp(OPENAI_BODY)

        globals()["urlopen_with_ssl"] = fake_urlopen
        globals()["check_endpoint_reachable"] = lambda base, timeout=3: (True, "")

    def tearDown(self):
        Config.CONFIG_FILE = self._snap["CONFIG_FILE"]
        for k, v in self._snap.items():
            setattr(Config, k, v)
        Config.SESSION_ONLY_KEYS = self._sok
        PROVIDER_REGISTRY.clear()
        PROVIDER_REGISTRY.update(self._reg)
        globals()["urlopen_with_ssl"] = self._urlopen
        globals()["check_endpoint_reachable"] = self._reachable
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── helpers ────────────────────────────────────────────────────────────
    def factory_reset(self):
        """Fresh boot state: factory registry, empty session. Deletes the
        scratch config (a truly fresh install)."""
        self._reset_session()
        if os.path.exists(self.cfgfile):
            os.remove(self.cfgfile)

    def reboot(self):
        """Simulate a process restart WITHOUT wiping config.json: registry
        back to factory (load_config repopulates it from the providers
        section) and Config session state cleared."""
        self._reset_session()

    def _reset_session(self):
        PROVIDER_REGISTRY.clear()
        PROVIDER_REGISTRY.update({k: dict(v) for k, v in FACTORY.items()})
        Config.API_KEY = ""
        Config.API_BASE = "http://127.0.0.1:8080"
        Config.PROVIDER = "local"
        Config.MODEL = ""
        Config.CUSTOM_API_BASE = False
        Config.SUBAGENT_PROVIDER = ""
        Config.SUBAGENT_MODEL = ""
        Config.SESSION_ONLY_KEYS = set()

    @staticmethod
    def anchor_for(name):
        """A second provider that is guaranteed != name (avoids duplicate
        dict keys when building two-provider configs)."""
        return "deepseek" if name != "deepseek" else "openai"

    def write_cfg(self, cfg):
        with open(self.cfgfile, "w") as f:
            json.dump(cfg, f)

    def disk(self):
        if not os.path.exists(self.cfgfile):
            return {}
        with open(self.cfgfile) as f:
            return json.load(f)

    def quiet(self, fn, *a, **kw):
        """Run fn with stdout swallowed; return its value."""
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*a, **kw)

    def ask(self, base, key, model):
        """Drive ask_ai exactly like a main-thread or subagent request."""
        return self.quiet(ask_ai, [{"role": "user", "content": "hi"}],
                          stream=False, retry=0, api_base=base, api_key=key,
                          model=model)

    def captured_auth(self):
        """Authorization / x-api-key header of the last captured request."""
        if not self.captured:
            return None
        h = self.captured[-1]["headers"]
        if "authorization" in h:
            return ("authorization", h["authorization"])
        if "x-api-key" in h:
            return ("x-api-key", h["x-api-key"])
        return (None, None)

    def provider_key_on_disk(self, name):
        return ((self.disk().get("providers") or {}).get(name) or {}).get("api_key")


# ══════════════════════════════════════════════════════════════════════════
# F1 — ACTIVE-KEY SET:  /provider key <name> <key>  (name active → API_KEY)
# ══════════════════════════════════════════════════════════════════════════
class F1_ActiveKeySet(MatrixHarness):

    def test_per_provider(self):
        for name in ALL_PROVIDERS + SYNTH_PROVIDERS:
            with self.subTest(provider=name):
                self.factory_reset()
                k = f"sk-F1-{name}"
                self.write_cfg({"provider": name, "api_key": "",
                                "providers": {}})
                Config.PROVIDER = name
                Config.API_KEY = ""
                # REPL handler L10399-10416 for the ACTIVE provider:
                # set_provider_entry + explicit API_KEY/save (redundant by design)
                ok = Config.set_provider_entry(name, api_key=k)
                Config.API_KEY = k.strip()
                Config.SESSION_ONLY_KEYS.discard("api_key")
                Config.save_config()
                good = (ok and Config.API_KEY == k
                        and self.disk().get("api_key") == k
                        and self.provider_key_on_disk(name) == k
                        and PROVIDER_REGISTRY[name].get("default_key") == k)
                record("F1", name, good,
                       f"API_KEY={Config.API_KEY!r} disk.top={self.disk().get('api_key')!r} "
                       f"disk.prov={self.provider_key_on_disk(name)!r} "
                       f"reg.default_key={PROVIDER_REGISTRY[name].get('default_key')!r}")
                self.assertTrue(good, f"{name}: {Config.API_KEY!r}")

    def test_nonactive_keeps_active_key(self):
        self.factory_reset()
        Config.PROVIDER = "openai"
        Config.API_KEY = "sk-active-main"
        self.write_cfg({"provider": "openai", "api_key": "sk-active-main",
                        "providers": {}})
        Config.set_provider_entry("groq", api_key="sk-groq-only")
        good = (Config.API_KEY == "sk-active-main"
                and self.provider_key_on_disk("groq") == "sk-groq-only"
                and self.disk().get("api_key") == "sk-active-main")
        record("F1", "groq(non-active)", good,
               f"API_KEY={Config.API_KEY!r} (unchanged) disk.groq={self.provider_key_on_disk('groq')!r}")
        self.assertTrue(good)

    def test_corrupt_config_quarantine_leaves_api_key_unwired(self):
        """GAP-1 (edge): set_provider_entry on a CORRUPT config.json returns
        False at L4419 (quarantine path) BEFORE the active-provider wiring at
        L4431-4434 — the key lands in the registry only, Config.API_KEY stays
        empty, and resolve_runtime() refuses registry keys for the ACTIVE
        provider (L12048 requires prov != Config.PROVIDER) → 401 no-key-sent.
        The /provider REPL handler masks this (it sets Config.API_KEY itself
        at L10411); /provider → edit (cmd_provider_edit) does not."""
        self.factory_reset()
        with open(self.cfgfile, "w") as f:
            f.write("{not json!!")
        Config.PROVIDER = "openai"
        Config.API_KEY = ""
        ok = Config.set_provider_entry("openai", api_key="sk-quarantine")
        base, key, mdl = resolve_runtime("openai")
        good = bool(key)   # desired: key reaches request path even after quarantine
        record("F1", "openai(corrupt-config)", good,
               f"set_provider_entry→{ok} API_KEY={Config.API_KEY!r} "
               f"resolve_runtime key={key!r} reg.default_key="
               f"{PROVIDER_REGISTRY['openai'].get('default_key')!r}  [GAP-1 edge]")
        self.assertTrue(good, "quarantine path drops the active key (GAP-1)")


# ══════════════════════════════════════════════════════════════════════════
# F2 — BOOT LIFT: empty top-level api_key + providers.<name>.api_key
# ══════════════════════════════════════════════════════════════════════════
class F2_BootLift(MatrixHarness):

    def _lift_case(self, tag, cfg):
        name = cfg["provider"]
        k = (cfg.get("providers", {}).get(name, {}) or {}).get("api_key")
        self.write_cfg(cfg)
        Config.load_config()
        good = Config.API_KEY == k
        record(tag, name, good, f"load_config→API_KEY={Config.API_KEY!r} (want {k!r})")
        self.assertEqual(Config.API_KEY, k)

    def test_empty_toplevel_lifts(self):
        for name in ALL_PROVIDERS + SYNTH_PROVIDERS:
            with self.subTest(provider=name):
                self.factory_reset()
                k = f"sk-F2-{name}"
                self._lift_case("F2", {
                    "provider": name, "api_key": "", "model": f"m-{name}",
                    "api_base": f"https://{name}.example.com/v1",
                    "providers": {name: {"api_base": f"https://{name}.example.com/v1",
                                         "model": f"m-{name}", "api_key": k}}})

    def test_missing_toplevel_key_installer_heredoc(self):
        """install.sh fresh-config heredoc has NO api_key key at all (only the
        post-merge step adds it when the provider key is non-empty)."""
        for name in ("neuralwatt", "openai", "instprov"):
            with self.subTest(provider=name):
                self.factory_reset()
                k = f"sk-F2b-{name}"
                self._lift_case("F2b", {
                    "provider": name, "model": "m", "api_base": "https://x.example/v1",
                    "providers": {name: {"api_base": "https://x.example/v1",
                                         "model": "m", "api_key": k}}})

    def test_empty_provider_key_no_lift(self):
        self.factory_reset()
        self.write_cfg({"provider": "local", "api_key": "",
                        "providers": {"local": {"api_base": "http://127.0.0.1:8080",
                                                "api_key": ""}}})
        Config.load_config()
        good = Config.API_KEY == ""
        record("F2", "local(empty prov key)", good,
               f"API_KEY={Config.API_KEY!r} (no stale key)")
        self.assertEqual(Config.API_KEY, "")

    def test_nonactive_provider_key_does_not_lift_toplevel(self):
        """Keys of NON-active providers stay in the registry for routing,
        but must not become the session key."""
        self.factory_reset()
        self.write_cfg({"provider": "local", "api_key": "",
                        "providers": {"openai": {"api_base": "https://api.openai.com/v1",
                                                 "api_key": "sk-o-only"}}})
        Config.load_config()
        good = (Config.API_KEY == ""
                and PROVIDER_REGISTRY["openai"].get("default_key") == "sk-o-only")
        record("F2", "openai(non-active)", good,
               f"API_KEY={Config.API_KEY!r} reg.openai.default_key="
               f"{PROVIDER_REGISTRY['openai'].get('default_key')!r}")
        self.assertTrue(good)


# ══════════════════════════════════════════════════════════════════════════
# F3 — NON-EMPTY TOP-LEVEL WINS
# ══════════════════════════════════════════════════════════════════════════
class F3_NonEmptyWins(MatrixHarness):

    def test_per_provider(self):
        for name in ALL_PROVIDERS + SYNTH_PROVIDERS:
            with self.subTest(provider=name):
                self.factory_reset()
                self.write_cfg({
                    "provider": name, "api_key": "sk-TOP-LEVEL", "model": "m",
                    "api_base": f"https://{name}.example.com/v1",
                    "providers": {name: {"api_base": f"https://{name}.example.com/v1",
                                         "model": "m", "api_key": f"sk-F3-{name}"}}})
                Config.load_config()
                good = Config.API_KEY == "sk-TOP-LEVEL"
                record("F3", name, good, f"API_KEY={Config.API_KEY!r}")
                self.assertEqual(Config.API_KEY, "sk-TOP-LEVEL")


# ══════════════════════════════════════════════════════════════════════════
# F4 — SWITCH: _apply_model_selection / _switch_main_provider key wiring
# ══════════════════════════════════════════════════════════════════════════
class F4_Switch(MatrixHarness):

    def test_switch_away_and_back(self):
        for name in ALL_PROVIDERS + SYNTH_PROVIDERS:
            with self.subTest(provider=name):
                self.factory_reset()
                anchor = self.anchor_for(name)
                ka = f"sk-F4-anchor-{anchor}"
                kp = f"sk-F4-{name}"
                bp = f"https://{name}.example.com/v1"
                self.write_cfg({"provider": anchor, "api_key": "",
                                "providers": {anchor: {"api_base": f"https://{anchor}.example.com/v1",
                                                       "model": "am", "api_key": ka}}})
                Config.load_config()
                self.assertEqual(Config.API_KEY, ka)
                # configure target provider like a user would (key+base+model)
                Config.set_provider_entry(name, api_base=bp, model="pm", api_key=kp)
                # switch AWAY to <name>
                self.quiet(_apply_model_selection, name, "pm", "main")
                away_ok = (Config.PROVIDER == name and Config.API_KEY == kp)
                # switch BACK to anchor
                self.quiet(_apply_model_selection, anchor, "am", "main")
                back_ok = (Config.PROVIDER == anchor and Config.API_KEY == ka)
                good = away_ok and back_ok
                record("F4", name, good,
                       f"away_ok={away_ok} (prov={name}, key={kp}) | "
                       f"back_ok={back_ok} (prov={anchor}, key={ka}) | final API_KEY={Config.API_KEY!r}")
                self.assertTrue(good, f"away_ok={away_ok} back_ok={back_ok}")

    def test_same_provider_repick_with_empty_active_key(self):
        for name in ALL_PROVIDERS + SYNTH_PROVIDERS:
            with self.subTest(provider=name):
                self.factory_reset()
                k = f"sk-F4b-{name}"
                self.write_cfg({"provider": name, "api_key": "",
                                "providers": {name: {"api_base": f"https://{name}.example.com/v1",
                                                     "model": "m1", "api_key": k}}})
                Config.load_config()
                Config.API_KEY = ""   # simulate the pre-fix runtime state
                self.quiet(_apply_model_selection, name, "m2", "main")
                good = Config.API_KEY == k
                record("F4b", name, good, f"repick→API_KEY={Config.API_KEY!r} (want {k!r})")
                self.assertEqual(Config.API_KEY, k)

    def test_switch_main_provider_function(self):
        for name in ALL_PROVIDERS + SYNTH_PROVIDERS:
            with self.subTest(provider=name):
                self.factory_reset()
                k = f"sk-F4c-{name}"
                anchor = self.anchor_for(name)
                # llamacpp-remote has no factory base/model → give it one first
                # (exactly what /provider api llamacpp-remote <url> does)
                extra = {} if FACTORY_BASE.get(name) else {"api_base": f"https://{name}.example.com/v1"}
                self.write_cfg({"provider": anchor, "api_key": "",
                                "providers": {anchor: {"api_base": f"https://{anchor}.example.com/v1",
                                                       "model": "am", "api_key": f"sk-F4c-{anchor}"},
                                              name: dict(extra, model="m", api_key=k)}})
                Config.load_config()
                self.quiet(_switch_main_provider, name)
                good = (Config.PROVIDER == name and Config.API_KEY == k
                        and Config.API_KEY == PROVIDER_REGISTRY[name].get("default_key", k))
                record("F4c", name, good,
                       f"_switch_main_provider→prov={Config.PROVIDER!r} API_KEY={Config.API_KEY!r} (want {k!r})")
                self.assertTrue(good)

    def test_switch_via_live_catalog_fetch(self):
        """llamacpp-remote straight off a factory install: no saved model →
        _switch_main_provider resolves runtime + fetches the live catalog
        (L12496-12506) before applying. The fetched-model path must still
        wire the registry key."""
        self.factory_reset()
        Config.set_provider_entry("llamacpp-remote",
                                  api_base="https://lr.example.com/v1",
                                  api_key="sk-lr-catalog")
        self.captured = []
        self.quiet(_switch_main_provider, "llamacpp-remote")
        good = (Config.PROVIDER == "llamacpp-remote"
                and Config.API_KEY == "sk-lr-catalog"
                and Config.MODEL == "m1"
                and any("/v1/models" in c["url"] for c in self.captured))
        record("F4c2", "llamacpp-remote(catalog fetch)", good,
               f"prov={Config.PROVIDER!r} API_KEY={Config.API_KEY!r} model={Config.MODEL!r}")
        self.assertTrue(good)

    def test_switch_to_keyless_provider_keeps_stale_key(self):
        """S-1 FIXED (v7.2.9): switching to a provider with NO key now CLEARS
        Config.API_KEY — the previous provider's key used to stay in the
        request path, get persisted as the top-level key, and survive
        reboot (leak vector to whatever base the new provider points at)."""
        self.factory_reset()
        self.write_cfg({"provider": "openai", "api_key": "",
                        "providers": {"openai": {"api_base": "https://api.openai.com/v1",
                                                  "model": "gpt-4o", "api_key": "sk-openai-real"}}})
        Config.load_config()
        self.quiet(_apply_model_selection, "local", "deepseek-v4-flash", "main")
        stale = Config.API_KEY
        self.quiet(Config.save_config)
        disk_key = self.disk().get("api_key")
        record("F4d", "local(keyless target)", stale == "",
               f"after switch API_KEY={stale!r} (disk top-level: {disk_key!r})  [S-1 fixed]")
        self.assertEqual(stale, "")


# ══════════════════════════════════════════════════════════════════════════
# F5 — SUBAGENT ROUTING: resolve_runtime + captured headers per provider
# ══════════════════════════════════════════════════════════════════════════
class F5_SubagentRouting(MatrixHarness):

    def _boot_two_providers(self, target, target_key, main=None):
        """Boot with `main` active; target carries a config-loaded key on its
        factory base (or a synthetic base when the factory has none)."""
        self.factory_reset()
        if main is None:
            main = self.anchor_for(target)
        tb = FACTORY_BASE.get(target) or f"https://{target}.example.com/v1"
        self.write_cfg({
            "provider": main, "api_key": "", "model": "mm",
            "api_base": f"https://{main}.example.com/v1",
            "providers": {main: {"api_base": f"https://{main}.example.com/v1",
                                 "model": "mm", "api_key": f"sk-main-{main}"},
                          target: {"api_base": tb, "model": "tm", "api_key": target_key}}})
        Config.load_config()

    def test_routing_and_headers_per_provider(self):
        for name in ALL_PROVIDERS + SYNTH_PROVIDERS:
            with self.subTest(provider=name):
                # ── Case A: name is ACTIVE — session wiring feeds resolve_runtime
                self.factory_reset()
                kA = f"sk-F5a-{name}"
                bA = FACTORY_BASE.get(name) or f"https://{name}.example.com/v1"
                self.write_cfg({"provider": name, "api_key": "", "model": "m",
                                "api_base": bA,
                                "providers": {name: {"api_base": bA, "model": "m",
                                                    "api_key": kA}}})
                Config.load_config()
                base, key, mdl = resolve_runtime(name)
                a_ok = (key == kA and base == bA)
                # ── Case B: name is a FOREIGN (subagent) provider — its own key+base
                kB = f"sk-F5b-{name}"
                self._boot_two_providers(name, kB)
                base, key, mdl = resolve_runtime(name)
                bB = FACTORY_BASE.get(name) or f"https://{name}.example.com/v1"
                b_ok = (key == kB and base == bB)
                # ── Case C: prove the header actually carries the key (ask_ai path,
                #    exactly how SubAgent._run_loop L7472-7499 calls it)
                self.captured = []
                self.ask(base, key, mdl)
                hdr_name, hdr_val = self.captured_auth()
                expect_native = "api.anthropic.com" in bB
                if expect_native:
                    c_ok = (hdr_name == "x-api-key" and hdr_val == kB)
                else:
                    c_ok = (hdr_name == "authorization" and hdr_val == f"Bearer {kB}"
                            and "/v1/chat/completions" in self.captured[-1]["url"])
                good = a_ok and b_ok and c_ok
                record("F5", name, good,
                       f"A(active): key={kA if a_ok else key!r} base={bA if a_ok else base!r} | "
                       f"B(foreign): key={key!r} base={base!r} | "
                       f"C(header): {hdr_name}={hdr_val!r} url={self.captured[-1]['url'] if self.captured else 'NONE'}")
                self.assertTrue(good, f"A={a_ok} B={b_ok} C={c_ok}")

    def test_main_path_ask_ai_uses_session_key(self):
        """Main-thread ask_ai() with no explicit key → Config.API_KEY."""
        self.factory_reset()
        self.write_cfg({"provider": "openai", "api_key": "",
                        "providers": {"openai": {"api_base": "https://api.openai.com/v1",
                                                  "model": "gpt-4o", "api_key": "sk-mainpath"}}})
        Config.load_config()
        self.captured = []
        self.quiet(ask_ai, [{"role": "user", "content": "hi"}], stream=False, retry=0)
        hdr_name, hdr_val = self.captured_auth()
        good = hdr_val == "Bearer sk-mainpath"
        record("F5", "openai(main-path)", good, f"{hdr_name}={hdr_val!r}")
        self.assertEqual(hdr_val, "Bearer sk-mainpath")

    def test_session_key_beats_registry_key_for_main_provider(self):
        """--api-key rotation safety: session key stays in charge for the
        MAIN provider even when a registry key exists (resolve_runtime docstring)."""
        self.factory_reset()
        self.write_cfg({"provider": "openai", "api_key": "",
                        "providers": {"openai": {"api_base": "https://api.openai.com/v1",
                                                  "model": "gpt-4o", "api_key": "sk-reg-old"}}})
        Config.load_config()
        Config.API_KEY = "sk-cli-session"      # simulate main() --api-key (L9982-9984)
        Config.SESSION_ONLY_KEYS.add("api_key")
        base, key, mdl = resolve_runtime("openai")
        good = key == "sk-cli-session"
        record("F5", "openai(session-key)", good, f"resolve_runtime key={key!r}")
        self.assertEqual(key, "sk-cli-session")

    def test_foreign_keyless_provider_inherits_session_key(self):
        """S-2 (documented behavior): a foreign provider with a base but NO
        registered key inherits the session/main key — the main provider's
        key is sent (Bearer) to that provider's endpoint. Cross-inherit guard
        at L12056 only applies when the foreign provider HAS its own key."""
        self.factory_reset()
        Config.PROVIDER = "openai"
        Config.API_KEY = "sk-openai-session"
        Config.API_BASE = "https://api.openai.com/v1"
        base, key, mdl = resolve_runtime("groq")   # factory groq: base, no key
        self.captured = []
        self.ask(base, key, mdl)
        hdr_name, hdr_val = self.captured_auth()
        good = (key == "sk-openai-session"
                and hdr_val == "Bearer sk-openai-session"
                and "api.groq.com" in self.captured[-1]["url"])
        record("F5", "groq(keyless foreign)", good,
               f"resolve→({base},{key!r}); header {hdr_val!r} sent to {self.captured[-1]['url']}  [S-2 WARN]")
        self.assertTrue(good)

    def test_keyonly_provider_entry_ignored_for_routing(self):
        """llamacpp-remote with a key but no base (possible right after
        /provider key llamacpp-remote K on a factory install): resolve_runtime
        refuses to route the key (L12058-62 misconfig guard) — falls back to
        session base+key."""
        self.factory_reset()
        Config.PROVIDER = "neuralwatt"
        Config.API_KEY = "sk-nw-main"
        Config.API_BASE = "https://api.neuralwatt.com/v1"
        Config.set_provider_entry("llamacpp-remote", api_key="sk-lr-only")  # no base
        base, key, mdl = resolve_runtime("llamacpp-remote")
        good = (key == "sk-nw-main" and base == "https://api.neuralwatt.com/v1")
        record("F5", "llamacpp-remote(key-only)", good,
               f"resolve→({base},{key!r}) — entry ignored by design (misconfig guard L12058)  [S-3]")
        self.assertTrue(good)

    def test_anthropic_main_hijacks_foreign_subagent_protocol(self):
        """GAP-2: ask_ai → _resolve_cache_support(api_base=...) with
        provider=None falls back to the MAIN provider's registry row
        (L7850-7858). A main=anthropic + foreign-base subagent (groq,
        neuralwatt, custom…) gets routed through the NATIVE Anthropic path:
        POST <foreign-base>/v1/messages with x-api-key instead of the
        OpenAI-compatible /v1/chat/completions + Bearer → 404/wrong protocol.
        The base-first domain checks only save api.anthropic.com/.openai.com/
        .deepseek.com bases."""
        self._boot_two_providers("groq", "sk-groq-sub", main="anthropic")
        base, key, mdl = resolve_runtime("groq")
        self.captured = []
        self.ask(base, key, mdl)
        url = self.captured[-1]["url"]
        hdr_name, hdr_val = self.captured_auth()
        hijacked = url.endswith("/v1/messages")
        good = not hijacked
        record("F5", "groq(sub of anthropic)", good,
               f"URL={url} header={hdr_name}:{hdr_val!r} — {'NATIVE hijack (GAP-2)' if hijacked else 'ok'}")
        self.assertFalse(hijacked,
                         "GAP-2: anthropic main hijacked the groq subagent request")

    def test_anthropic_subagent_of_openai_main_is_correct(self):
        """The healthy direction: anthropic subagent + openai main → base
        check fires first → native path with x-api-key (correct)."""
        self._boot_two_providers("anthropic", "sk-ant-sub", main="openai")
        base, key, mdl = resolve_runtime("anthropic")
        self.captured = []
        self.ask(base, key, mdl)
        url = self.captured[-1]["url"]
        hdr_name, hdr_val = self.captured_auth()
        good = (url.endswith("/v1/messages") and hdr_name == "x-api-key"
                and hdr_val == "sk-ant-sub")
        record("F5", "anthropic(sub of openai)", good,
               f"URL={url} header={hdr_name}={hdr_val!r}")
        self.assertTrue(good)


# ══════════════════════════════════════════════════════════════════════════
# F6 — SESSION-ONLY KEYS: --api-key
# ══════════════════════════════════════════════════════════════════════════
class F6_SessionOnlyKeys(MatrixHarness):

    def test_cli_key_flow(self):
        self.factory_reset()
        self.write_cfg({"provider": "openai", "api_key": "sk-disk-original",
                        "providers": {"openai": {"api_base": "https://api.openai.com/v1",
                                                 "model": "gpt-4o",
                                                 "api_key": "sk-disk-original"}}})
        Config.load_config()
        # ── simulate main() --api-key (L9982-9984)
        Config.API_KEY = "sk-cli-session"
        Config.SESSION_ONLY_KEYS.add("api_key")
        # 1) request path uses the session key
        self.captured = []
        self.quiet(ask_ai, [{"role": "user", "content": "hi"}], stream=False, retry=0)
        hdr_used = self.captured_auth()[1]
        # 2) save_config must NOT overwrite the disk key (L4387-4389 protection)
        self.quiet(Config.save_config)
        disk_after_save = self.disk().get("api_key")
        # 3) fresh boot from that disk: the stored key survives
        self.reboot()
        Config.load_config()
        reloaded = Config.API_KEY
        good = (hdr_used == "Bearer sk-cli-session"
                and disk_after_save == "sk-disk-original"
                and reloaded == "sk-disk-original")
        record("F6", "openai", good,
               f"header={hdr_used!r} disk-after-save={disk_after_save!r} reload={reloaded!r}")
        self.assertTrue(good)

    def test_interactive_key_change_clears_protection(self):
        """After --api-key, an interactive /provider key persists the new key
        (SESSION_ONLY_KEYS.discard at L4434 — protection is one-way only)."""
        self.factory_reset()
        self.write_cfg({"provider": "openai", "api_key": "sk-disk-original",
                        "providers": {"openai": {"api_base": "https://api.openai.com/v1",
                                                 "api_key": "sk-disk-original"}}})
        Config.load_config()
        Config.API_KEY = "sk-cli-session"
        Config.SESSION_ONLY_KEYS.add("api_key")
        Config.set_provider_entry("openai", api_key="sk-new-permanent")
        self.quiet(Config.save_config)
        disk_key = self.disk().get("api_key")
        good = (disk_key == "sk-new-permanent" and "api_key" not in Config.SESSION_ONLY_KEYS)
        record("F6b", "openai", good,
               f"disk={disk_key!r} protected={'api_key' in Config.SESSION_ONLY_KEYS}")
        self.assertTrue(good)


# ══════════════════════════════════════════════════════════════════════════
# F7 — PROVIDER TEST FLOW: cmd_provider_test uses the provider's OWN key
# ══════════════════════════════════════════════════════════════════════════
class F7_ProviderTest(MatrixHarness):

    def test_foreign_and_active(self):
        for name in ALL_PROVIDERS + SYNTH_PROVIDERS:
            if name == "llamacpp-remote":
                continue  # factory has no base — dedicated test below
            with self.subTest(provider=name):
                # foreign: main=anchor, target carries its own key
                self.factory_reset()
                anchor = self.anchor_for(name)
                k = f"sk-F7-{name}"
                tb = FACTORY_BASE.get(name) or f"https://{name}.example.com/v1"
                self.write_cfg({"provider": anchor, "api_key": "",
                                "providers": {anchor: {"api_base": f"https://{anchor}.example.com/v1",
                                                       "model": "am", "api_key": f"sk-F7-main-{anchor}"},
                                              name: {"api_base": tb, "model": "tm", "api_key": k}}})
                Config.load_config()
                self.captured = []
                self.quiet(cmd_provider_test, name)
                hdr_name, hdr_val = self.captured_auth()
                foreign_ok = (hdr_val == f"Bearer {k}")
                # active: testing the main provider sends Config.API_KEY
                self.captured = []
                self.quiet(cmd_provider_test, anchor)
                hdr_name2, hdr_val2 = self.captured_auth()
                active_ok = (hdr_val2 == f"Bearer sk-F7-main-{anchor}")
                good = foreign_ok and active_ok
                record("F7", name, good,
                       f"foreign test→{hdr_val!r} (want Bearer {k}) | "
                       f"active test→{hdr_val2!r} (want Bearer sk-F7-main-{anchor})")
                self.assertTrue(good)

    def test_keyonly_llamacpp_remote_tests_main_endpoint(self):
        """S-4 (documented behavior): /provider test llamacpp-remote when it has
        a key but no base — resolve_runtime falls back to the MAIN provider's
        base+key, so the diagnostic tests the WRONG endpoint and can report a
        false OK for an unconfigured provider."""
        self.factory_reset()
        Config.PROVIDER = "neuralwatt"
        Config.API_KEY = "sk-nw-main"
        Config.API_BASE = "https://api.neuralwatt.com/v1"
        Config.set_provider_entry("llamacpp-remote", api_key="sk-lr")
        self.captured = []
        self.quiet(cmd_provider_test, "llamacpp-remote")
        url = self.captured[-1]["url"] if self.captured else "NO REQUEST"
        hdr_val = self.captured_auth()[1] if self.captured else None
        good = ("neuralwatt" in url and hdr_val == "Bearer sk-nw-main")  # current behavior
        record("F7", "llamacpp-remote(key-only)", good,
               f"tested URL={url} key={hdr_val!r} — main's endpoint, not llamacpp-remote's  [S-4 WARN]")
        self.assertTrue(good)

    def test_no_base_early_exit(self):
        """cmd_provider_test with an empty resolved base prints 'No API base
        set' and sends nothing (L12542-44)."""
        self.factory_reset()
        Config.PROVIDER = ""
        Config.API_BASE = ""
        PROVIDER_REGISTRY["ghost"] = {"name": "Ghost", "api_base": ""}
        self.captured = []
        out = self.quiet(cmd_provider_test, "ghost")
        good = not self.captured
        record("F7", "ghost(no base)", good,
               f"requests sent: {len(self.captured)} (early exit, no request)")
        self.assertTrue(good)


# ══════════════════════════════════════════════════════════════════════════
# F8 — INSTALLER-WRITTEN CONFIG SHAPES
# ══════════════════════════════════════════════════════════════════════════
class F8_InstallerShapes(MatrixHarness):

    def _check(self, tag, name, cfg, want):
        self.factory_reset()
        self.write_cfg(cfg)
        Config.load_config()
        good = Config.API_KEY == want
        record(tag, name, good, f"load→API_KEY={Config.API_KEY!r} (want {want!r})")
        self.assertEqual(Config.API_KEY, want)

    def test_modern_install_lifted_toplevel(self):
        """install.sh post-merge shape: top-level api_key == ACTIVE provider's
        key (install.sh L635-639), plus other providers' keys in the section."""
        for name in ("openai", "neuralwatt", "instprov"):
            with self.subTest(provider=name):
                self._check("F8", name, {
                    "theme": "phosphor", "provider": name, "model": "m",
                    "api_base": f"https://{name}.example.com/v1",
                    "api_key": f"sk-inst-{name}",
                    "providers": {name: {"api_base": f"https://{name}.example.com/v1",
                                         "model": "m", "api_key": f"sk-inst-{name}"},
                                 "otherprov": {"api_base": "https://other.example/v1",
                                               "model": "om", "api_key": "sk-inst-otherprov"}}},
                    f"sk-inst-{name}")

    def test_auto_mode_local_defaults(self):
        """install.sh auto mode: local provider, no keys anywhere."""
        self._check("F8b", "local(auto-mode)", {
            "theme": "phosphor", "provider": "local", "model": "",
            "api_base": "http://127.0.0.1:8080", "providers": {}}, "")

    def test_legacy_bug_shape_still_lifts(self):
        """Pre-7.2.8 save shape (the original 401 bug): top-level api_key
        persisted as "" while providers.<name>.api_key held the real key."""
        self._check("F8c", "neuralwatt(legacy)", {
            "provider": "neuralwatt", "model": "glm-5.2", "api_key": "",
            "api_base": "https://api.neuralwatt.com/v1",
            "providers": {"neuralwatt": {"api_base": "https://api.neuralwatt.com/v1",
                                         "model": "glm-5.2", "api_key": "sk-legacy"}}}, "sk-legacy")

    def test_save_then_reload_roundtrip(self):
        """Full user session: installer shape → /provider key change → save →
        reboot → the NEW key must survive (the v7.2.8 headline scenario)."""
        self.factory_reset()
        self.write_cfg({"provider": "neuralwatt", "api_key": "",
                        "providers": {"neuralwatt": {"api_base": "https://api.neuralwatt.com/v1",
                                                       "model": "glm-5.2", "api_key": "sk-old"}}})
        Config.load_config()
        Config.set_provider_entry("neuralwatt", api_key="sk-rotated")
        self.reboot()
        Config.load_config()
        good = Config.API_KEY == "sk-rotated"
        record("F8d", "neuralwatt(rotation)", good,
               f"save+reboot→API_KEY={Config.API_KEY!r}")
        self.assertEqual(Config.API_KEY, "sk-rotated")


# ══════════════════════════════════════════════════════════════════════════
# F9 — CUSTOM BASE: base override must not break key routing
# ══════════════════════════════════════════════════════════════════════════
class F9_CustomBase(MatrixHarness):

    def test_set_custom_api_base_keeps_key(self):
        for name in ("openai", "neuralwatt", "userprov"):
            with self.subTest(provider=name):
                self.factory_reset()
                k = f"sk-F9-{name}"
                self.write_cfg({"provider": name, "api_key": "",
                                "providers": {name: {"api_base": f"https://{name}.example.com/v1",
                                                     "model": "m", "api_key": k}}})
                Config.load_config()
                self.quiet(set_custom_api_base, "https://proxy.example.com/v1")
                base, key, mdl = resolve_runtime(name)
                self.captured = []
                self.ask(base, key, mdl)
                hdr_name, hdr_val = self.captured_auth()
                good = (base == "https://proxy.example.com/v1" and key == k
                        and hdr_val == f"Bearer {k}"
                        and "proxy.example.com" in self.captured[-1]["url"])
                record("F9", name, good,
                       f"base={base} key={key!r} header={hdr_val!r} url={self.captured[-1]['url']}")
                self.assertTrue(good)

    def test_provider_scoped_base_keeps_key(self):
        """/provider api <other> <url> — foreign provider's key still routes."""
        self.factory_reset()
        Config.PROVIDER = "openai"
        Config.API_KEY = "sk-openai-main"
        Config.API_BASE = "https://api.openai.com/v1"
        Config.set_provider_entry("together", api_base="https://together.example.com/v1",
                                  model="tm", api_key="sk-tg")
        base, key, mdl = resolve_runtime("together")
        self.captured = []
        self.ask(base, key, mdl)
        hdr_val = self.captured_auth()[1]
        good = (base == "https://together.example.com/v1" and key == "sk-tg"
                and hdr_val == "Bearer sk-tg")
        record("F9b", "together(/provider api)", good,
               f"base={base} key={key!r} header={hdr_val!r}")
        self.assertTrue(good)

    def test_config_loaded_custom_flag(self):
        self.factory_reset()
        self.write_cfg({"provider": "openai", "api_key": "",
                        "custom_api_base": True,
                        "api_base": "https://proxy.example.com/v1",
                        "providers": {"openai": {"api_base": "https://api.openai.com/v1",
                                                 "model": "gpt-4o", "api_key": "sk-cfg"}}})
        Config.load_config()
        base, key, mdl = resolve_runtime("openai")
        good = (base == "https://proxy.example.com/v1" and key == "sk-cfg"
                and Config.CUSTOM_API_BASE is True)
        record("F9c", "openai(cfg custom flag)", good,
               f"base={base} key={key!r} custom={Config.CUSTOM_API_BASE}")
        self.assertTrue(good)

    def test_switch_clobbers_custom_base(self):
        """S-5 (documented behavior): _apply_model_selection L12247-12250
        overwrites a custom base when switching to a provider whose registered
        base differs — despite the CUSTOM_API_BASE docstring claiming
        protection. Key wiring itself stays correct."""
        self.factory_reset()
        Config.PROVIDER = "openai"
        Config.API_KEY = "sk-openai"
        Config.API_BASE = "https://api.openai.com/v1"
        self.quiet(set_custom_api_base, "https://proxy.example.com/v1")
        self.assertTrue(Config.CUSTOM_API_BASE)
        self.quiet(_apply_model_selection, "groq", "llama-3.3-70b-versatile", "main")
        good = (Config.API_BASE == "https://api.groq.com/openai/v1"
                and Config.CUSTOM_API_BASE is False)
        record("F9d", "groq(custom-base clobber)", good,
               f"after switch API_BASE={Config.API_BASE!r} custom={Config.CUSTOM_API_BASE}  [S-5 WARN]")
        self.assertTrue(good)


# ══════════════════════════════════════════════════════════════════════════
# F10 — CLEARED KEYS: '-' wizard / api_key="" — no stale key
# ══════════════════════════════════════════════════════════════════════════
class F10_ClearedKeys(MatrixHarness):

    def _prep(self, name, active=True):
        k = f"sk-F10-{name}"
        anchor = self.anchor_for(name)
        self.write_cfg({"provider": name if active else anchor, "api_key": "",
                        "providers": {name: {"api_base": f"https://{name}.example.com/v1",
                                             "model": "m", "api_key": k},
                                      anchor: {"api_base": f"https://{anchor}.example.com/v1",
                                               "model": "am", "api_key": f"sk-{anchor}-keep"}}})
        Config.load_config()
        return k

    def test_edit_wizard_dash_clears_active(self):
        for name in ("openai", "neuralwatt", "userprov"):
            with self.subTest(provider=name):
                self.factory_reset()
                self._prep(name, active=True)
                self.assertTrue(PROVIDER_REGISTRY[name].get("default_key"))
                inputs = iter(["", "-", "", "n"])   # keep base / CLEAR key / keep model / no test
                self.quiet(cmd_provider_edit, name, input_fn=lambda p="": next(inputs))
                h = build_headers(api_key=Config.API_KEY, api_base=Config.API_BASE)
                good = (Config.API_KEY == ""
                        and not PROVIDER_REGISTRY[name].get("default_key")
                        and self.provider_key_on_disk(name) == ""
                        and self.disk().get("api_key") == ""
                        and "Authorization" not in h)
                record("F10", name, good,
                       f"API_KEY={Config.API_KEY!r} reg.default_key="
                       f"{PROVIDER_REGISTRY[name].get('default_key')!r} "
                       f"disk.prov={self.provider_key_on_disk(name)!r} "
                       f"disk.top={self.disk().get('api_key')!r} hdrAuth={'Authorization' in h}")
                self.assertTrue(good)

    def test_direct_empty_key_clears(self):
        for name in ALL_PROVIDERS + SYNTH_PROVIDERS:
            with self.subTest(provider=name):
                self.factory_reset()
                self._prep(name, active=True)
                Config.set_provider_entry(name, api_key="")
                good = (Config.API_KEY == ""
                        and not PROVIDER_REGISTRY[name].get("default_key")
                        and self.provider_key_on_disk(name) == ""
                        and self.disk().get("api_key") == "")
                record("F10b", name, good,
                       f"API_KEY={Config.API_KEY!r} reg.default_key="
                       f"{PROVIDER_REGISTRY[name].get('default_key')!r} "
                       f"disk.prov={self.provider_key_on_disk(name)!r}")
                self.assertTrue(good)

    def test_clear_nonactive_leaves_active_alone(self):
        self.factory_reset()
        self._prep("openai", active=False)   # anchor provider active
        anchor = self.anchor_for("openai")
        Config.set_provider_entry("openai", api_key="")
        good = (Config.API_KEY == f"sk-{anchor}-keep"
                and not PROVIDER_REGISTRY["openai"].get("default_key")
                and self.provider_key_on_disk(anchor) == f"sk-{anchor}-keep")
        record("F10c", "openai(non-active clear)", good,
               f"API_KEY={Config.API_KEY!r} (active key untouched)")
        self.assertTrue(good)

    def test_cleared_survives_reboot(self):
        self.factory_reset()
        self._prep("neuralwatt", active=True)
        Config.set_provider_entry("neuralwatt", api_key="")
        self.reboot()
        Config.load_config()
        h = build_headers(api_key=Config.API_KEY, api_base=Config.API_BASE)
        good = (Config.API_KEY == "" and "Authorization" not in h)
        record("F10d", "neuralwatt(reboot after clear)", good,
               f"API_KEY={Config.API_KEY!r} hdrAuth={'Authorization' in h}")
        self.assertTrue(good)

    def test_builtin_reset_keeps_stale_key(self):
        """S-6 FIXED (v7.2.9): /provider rm <builtin> while it is the active
        provider now clears Config.API_KEY when the factory row has no key —
        the user's old key used to remain in memory AND as the persisted
        top-level api_key after a 'reset to defaults'."""
        self.factory_reset()
        self._prep("neuralwatt", active=True)
        self.quiet(cmd_provider_remove, "neuralwatt")
        self.quiet(Config.save_config)
        good = (Config.API_KEY == ""
                and self.disk().get("api_key", "") == "")
        record("F10e", "neuralwatt(builtin reset)", good,
               f"after reset API_KEY={Config.API_KEY!r} disk.top={self.disk().get('api_key')!r}  [S-6 fixed]")
        self.assertTrue(good)


# ══════════════════════════════════════════════════════════════════════════
# Report dump (runs last — file order)
# ══════════════════════════════════════════════════════════════════════════
class ZZ_Report(unittest.TestCase):

    def test_dump_matrix(self):
        out = io.StringIO()
        w = out.write
        w(f"{'FLOW':<6} {'PROVIDER':<34} {'STATUS':<6} EVIDENCE\n")
        w("─" * 118 + "\n")
        fails = warns = passes = 0
        for flow, prov, status, ev in sorted(RESULTS):
            tag = status
            if "[S-" in ev and status == "PASS":
                tag = "WARN*"
                warns += 1
            elif status == "PASS":
                passes += 1
            else:
                fails += 1
            w(f"{flow:<6} {prov:<34} {tag:<6} {ev}\n")
        w("─" * 118 + "\n")
        w(f"TOTAL: {len(RESULTS)}  PASS: {passes}  FAIL: {fails}  "
          f"WARN(documented/flagged): {warns}\n")
        table = out.getvalue()
        with open("/tmp/opencode/matrix_results.txt", "w") as f:
            f.write(table)
        print("\n" + table)


if __name__ == "__main__":
    unittest.main(verbosity=2)
