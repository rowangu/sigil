# core/ — the fixed core

`lifecycle.adg` is HAI's fixed core, written as an Ampersand v0.7 graph.

The notebook's rules for the core:

* it never updates its own code — there is no `update_core_code`
  anywhere; changing the core means recompiling, offline, on purpose;
* its knowledge is a WORM boot manifest: written once at power-on,
  locked for life (Ampersand LAW 2);
* variables are wiped every cycle (Ampersand LAW 3 + the per-cycle
  variable arena reset);
* it must terminate by itself (LAW 6) — no infinite loops, no daemon.

The graph implements the notebook's five lifecycle stages:

```
entry -> validate -> score -> route -> end
```

and walks the word network word-number by word-number (1 → 1176, the
manifest counts) until the range is done, then opens the end gate and
stops. Compile it and watch:

```bash
ampersand compile lifecycle.adg
#   [cycle 1]    word=1   score=1   validate=1 ...
#   [cycle 1176] word=1176 score=1176 validate=0 end=1
#   Lifecycle terminated at cycle 1176
```

Strings, vectors, and models are **not** allowed in the core. If a
lifecycle stage needs a number from the learning side, it gets it through
the file bridge described in `patches/ampersand_call_op.patch`:

```
node function ask_toolbelt { op: call, mem: 1 };  # reads $HAI_BRIDGE/ask_toolbelt.in
```

One file, one double, deterministic. The toolbelt writes it; the core
reads it. Toolbelt, not the brain.
