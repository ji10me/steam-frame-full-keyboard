"""Small opt-in extension for the installed 0.8.2 Steam-only bridge.

The original default ignores an already open keyboard. A coordinator handing
back from a local app may nominate exactly one existing Steam owner instead.
No input text is inspected and the normal readiness/owner checks still apply.
"""
import pathlib


def patch(directory):
    directory = pathlib.Path(directory)
    js = directory / 'steam_bridge.js'
    source = js.read_text(encoding='utf-8')
    replacements = [
        ('function installNativeBridge(root, testStore, externalSupported)',
         'function installNativeBridge(root, testStore, externalSupported, initialTargetKey)'),
        ('let ignoreOpen = native.open, rawDeadline = 0, restoringUntil = 0;',
         'let initialPending = initialTargetKey === "current-steam" || typeof initialTargetKey === "string" && ownSteam(initialTargetKey);\n'
         '    let ignoreOpen = native.open, rawDeadline = 0, restoringUntil = 0;'),
        ('lease = frame.ready ? now() + LEASE_MS : 0;',
         'lease = frame.ready ? now() + LEASE_MS : 0;\n'
         '                    if (initialPending && frame.ready) {\n'
         '                        initialPending = false;\n'
         '                        const current = nativeStatus();\n'
         '                        if (current.open && ownSteam(current.key) &&\n'
         '                            (initialTargetKey === "current-steam" || current.key === initialTargetKey)) {\n'
         '                            ignoreOpen = false; previousOpen = false; previousKey = "";\n'
         '                        }\n'
         '                    }'),
    ]
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError('Unsupported bridge revision')
        source = source.replace(old, new)
    js.write_text(source, encoding='utf-8')
    py = directory / 'native_bridge.py'
    source = py.read_text(encoding='utf-8')
    old = '{str(external_supported).lower()}); '
    new = '{str(external_supported).lower()}, {json.dumps(os.environ.get("FRAMEKEYBOARD_NATIVE_INITIAL_TARGET", ""))}); '
    # Use single quotes inside the generated f-string on Python 3.11 as well.
    new = new.replace('get("FRAMEKEYBOARD_NATIVE_INITIAL_TARGET", "")', "get('FRAMEKEYBOARD_NATIVE_INITIAL_TARGET', '')")
    if source.count(old) != 1:
        raise ValueError('Unsupported transport revision')
    py.write_text(source.replace(old, new), encoding='utf-8')


if __name__ == '__main__':
    import sys
    patch(sys.argv[1])
