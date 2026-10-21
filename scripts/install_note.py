#!/usr/bin/env python3
"""Preview or explicitly apply one managed note to an agreed UTF-8 file."""
import argparse
import os
import stat
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- agent-ezh-catalog:start -->'
END = '<!-- agent-ezh-catalog:end -->'


def updated_text(current, note, remove=False):
    starts, ends = current.count(START), current.count(END)
    if starts != ends or starts > 1:
        raise ValueError('Ambiguous note markers; inspect the target file manually.')
    block = START + '\n' + note.strip() + '\n' + END
    if not starts:
        if remove:
            return current
        separator = '' if not current else ('\n' if current.endswith('\n') else '\n\n')
        return current + separator + block + '\n'
    first = current.index(START)
    last = current.index(END)
    if last < first:
        raise ValueError('Invalid note marker order.')
    after = last + len(END)
    if remove:
        if current[after:after + 1] == '\n':
            after += 1
        return current[:first] + current[after:]
    return current[:first] + block + current[after:]


def install(target, *, apply=False, remove=False):
    target = Path(target).expanduser()
    if target.is_symlink():
        raise ValueError('Choose the actual target file instead of a symlink.')
    original = target.read_bytes() if target.exists() else b''
    current = original.decode('utf-8')
    note = (ROOT / 'notes' / 'catalog-note.md').read_text(encoding='utf-8')
    result = updated_text(current, note, remove=remove).encode('utf-8')
    changed = result != original
    if apply and changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o600
        fd, tmp = tempfile.mkstemp(prefix='.agent-ezh-note-', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(result)
            os.chmod(tmp, mode)
            latest = target.read_bytes() if target.exists() else b''
            if target.is_symlink() or latest != original:
                raise ValueError('Target changed during preview; run again.')
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return {'target': str(target), 'mode': 'apply' if apply else 'preview',
            'action': 'remove' if remove else 'save', 'changed': changed,
            'note': '' if remove else note.strip()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path,
                        help='Owner-agreed personal instruction file')
    parser.add_argument('--apply', action='store_true', help='Write the reviewed change')
    parser.add_argument('--remove', action='store_true', help='Remove only this managed note')
    args = parser.parse_args()
    result = install(args.target, apply=args.apply, remove=args.remove)
    for key in ['mode', 'action', 'target', 'changed']:
        print(f'{key}: {result[key]}')
    if result['note']:
        print('\n' + result['note'])
    if not args.apply:
        print('\nNothing was written. Use --apply only after owner agreement.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        raise SystemExit(f'Note was not changed: {exc}')
