---
sidebar: true
---

# Installing on Windows

The Arcsecond CLI is a Python package, so installing it on Windows means
making sure Python and `pip` are available, then letting `pip` drop the
`arcsecond` executable somewhere Windows can find it. The default Windows
setup gets in the way of all three of those steps, so this page walks
through the common pitfalls in order.

If you are on macOS or Linux, see [Install & Login](/install) instead.

## 1. Install Python

You need a real Python interpreter. We recommend installing it from
[python.org/downloads](https://www.python.org/downloads/) rather than the
Microsoft Store: the python.org installer is more predictable, and the
Store variant ("Python install manager") has historically not added the
scripts directory to `PATH` automatically.

When running the python.org installer, **tick "Add python.exe to PATH"**
on the very first screen before clicking *Install Now*. That single
checkbox is the cause of most "`pip` is not recognized" reports.

Open a **new** PowerShell window after the install (already-open
terminals do not pick up `PATH` changes) and check:

```powershell
python --version
```

You should get something like `Python 3.12.x`. If instead PowerShell
opens the Microsoft Store, jump to [App execution aliases](#app-execution-aliases-when-python-opens-the-store)
below.

## 2. About `pip` and `pipx`

A common reflex on Windows is to install `pipx` first. **For the
Arcsecond CLI you do not need it.** The package is small, has no
conflicting dependencies, and is happy in your user `site-packages`.

- Use plain `pip` for Arcsecond — it ships with Python and is enough.
- Use `pipx` only if you already use it for other Python CLIs and want
  Arcsecond isolated alongside them. In that case run `pipx install arcsecond`.
- Do **not** mix the two on the same machine for the same tool. Pick one.

If `pip` says it is out of date, that is fine; the upgrade notice from
`pip` itself does not need to be acted on to install Arcsecond.

## 3. Install Arcsecond

In the new PowerShell window:

```powershell
python -m pip install --upgrade arcsecond
```

We deliberately use `python -m pip` rather than the bare `pip` command:
`python -m pip` always invokes the `pip` that belongs to the Python you
just ran, which avoids ambiguity when several Pythons are installed.

If you see a long list of `Requirement already satisfied:` lines and no
errors, the install succeeded.

## 4. Verify the install

```powershell
arcsecond -v
```

If that prints a version number, you are done — head to
[Install & Login](/install#authentication) for the login step.

If instead you get:

```
arcsecond : The term 'arcsecond' is not recognized as the name of a
cmdlet, function, script file, or operable program.
```

…then the install worked, but the directory where `pip` placed the
`arcsecond.exe` entry point is not on `PATH`. Continue with
[Scripts directory not on PATH](#scripts-directory-not-on-path) below.

::: tip
`python -m arcsecond` does **not** work as a fallback. The package does
not expose a `__main__.py`, so you will see
`No module named arcsecond.__main__`. The fix is always to add the
Scripts directory to `PATH`, not to invoke the module directly.
:::

## Troubleshooting

### `pip is not recognized`

Symptom:

```
pip : The term 'pip' is not recognized as the name of a cmdlet...
pipx : The term 'pipx' is not recognized...
pip3 : The term 'pip3' is not recognized...
```

This means Python itself is not on `PATH`. Either Python is not
installed, or it was installed without the "Add python.exe to PATH"
checkbox.

Fix:

1. Run `python --version` and `py --version` to see which (if any) is
   recognised.
2. If `py` works but `python` does not, use the launcher:
   `py -m pip install --upgrade arcsecond`.
3. If neither works, reinstall Python from
   [python.org/downloads](https://www.python.org/downloads/) and tick
   the PATH checkbox.
4. Always open a **new** PowerShell window after changing `PATH`.

### App execution aliases (when `python` opens the Store)

Windows ships stub executables for `python.exe` and `python3.exe` that
redirect to the Microsoft Store. If you have a real Python installed,
those stubs hide it.

Disable them:

1. Open *Settings → Apps → Advanced app settings → App execution aliases*.
2. Turn **off** the toggles for `python.exe` and `python3.exe` (and
   `Python (default)` if present).
3. Close PowerShell and open a new window.

`python --version` should now show your real interpreter.

### Scripts directory not on `PATH`

Symptom: `python -m pip install arcsecond` succeeds, but
`arcsecond -v` returns `CommandNotFoundException`.

This is common with the Microsoft Store "Python install manager"
variant, which installs into
`C:\Users\<you>\AppData\Local\Python\PythonCore-<version>\` and does
not put the matching `Scripts\` folder on `PATH`.

**Step 1 — find the exact Scripts path:**

```powershell
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
```

This prints the directory where `pip` installs console-script
executables. Example output:

```
C:\Users\WEO\AppData\Local\Python\PythonCore-3.14-64\Scripts
```

**Step 2 — confirm `arcsecond.exe` is actually there:**

```powershell
dir "<paste-the-path>\arcsecond*"
```

You should see `arcsecond.exe`. If you do not, the entry point was not
installed; reinstall with:

```powershell
python -m pip install --force-reinstall arcsecond
```

**Step 3 — sanity-check by running the full path:**

```powershell
& "<paste-the-path>\arcsecond.exe" -v
```

If that prints a version, the install is fine — only `PATH` is wrong.

**Step 4 — add the Scripts directory to `PATH` permanently:**

```powershell
$scripts = python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
$current = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$current;$scripts", "User")
```

Close PowerShell completely and open a fresh window. `arcsecond -v`
should now work.

If you prefer the GUI: *Settings → System → About → Advanced system
settings → Environment Variables*, edit your user `Path`, and add the
Scripts folder as a new entry.

### `No module named arcsecond.__main__`

You ran `python -m arcsecond`. That is not how Arcsecond is invoked —
it ships as a console script (`arcsecond.exe`), not as a runnable
module. Fix `PATH` as described above and call `arcsecond` directly.

### PowerShell execution-policy errors

If PowerShell refuses to run scripts at all (red text about execution
policy), open *PowerShell as Administrator* and run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Then reopen a normal PowerShell window.

## Once it works

Continue with [Authentication](/install#authentication) to log in with
your Access or Upload Key.
