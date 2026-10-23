#!/usr/bin/env python3
# LG Reverse Lab — USB Scout 0.1.1
# Runs ONLY on a Windows notebook with Python 3; NEVER executes on the LG.
# Stdlib only; optional local Ollama via localhost. No firmware writing.
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
LAB = BASE / 'LG_LAB_DADOS'
SESSIONS = LAB / 'sessoes'
ACTIVE = LAB / 'sessao_ativa.txt'
TESTS = BASE / 'LG_TESTES'
VERSION = '0.1.1'
FIRMWARE_SHA256 = '27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a'
ALLOWED_TEST_EXT = {'.mp3', '.jpg', '.jpeg'}
BANNED_UPDATE_EXT = {'.rom', '.epm', '.hex', '.bin', '.upd'}
IGNORED_FOLDERS = {'LG_LAB_DADOS', 'System Volume Information', '$RECYCLE.BIN', '.Spotlight-V100', '.Trashes'}
MAX_FILES = 5000
MAX_HASH_BYTES = 64 * 1024 * 1024
MAX_EVIDENCE_BYTES = 150 * 1024 * 1024
TEST_TYPES = [
    'USB - detect flash drive',
    'MP3 - left channel',
    'MP3 - right channel',
    'MP3 - alternating channels',
    'JPEG - display image',
    'USB - manually started recording',
    'IR - ordinary button',
    'Audio - AUX / surround',
    'Other non-destructive test',
]


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.partial')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def read_json(path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_media():
    if not TESTS.is_dir():
        raise RuntimeError('LG_TESTES folder not found: extract the complete ZIP file.')
    rows = []
    for p in sorted(TESTS.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() in BANNED_UPDATE_EXT:
            raise RuntimeError('Update files are not allowed in LG_TESTES: ' + p.name)
        if p.suffix.lower() not in ALLOWED_TEST_EXT:
            raise RuntimeError('Unexpected format in LG_TESTES: ' + p.name)
        rows.append({'file': p.name, 'size': p.stat().st_size, 'sha256': sha(p)})
    if len(rows) != 5:
        raise RuntimeError('Expected 5 media files; found: ' + str(len(rows)))
    return rows


def new_session():
    SESSIONS.mkdir(parents=True, exist_ok=True)
    ident = dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:5]
    path = SESSIONS / ident
    path.mkdir(parents=True, exist_ok=False)
    ACTIVE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE.write_text(ident, encoding='utf-8')
    atomic_json(path / 'sessao.json', {
        'schema': 1, 'tool': 'LG USB Scout', 'tool_version': VERSION,
        'session_id': ident, 'created_at_utc': now(),
        'equipment': 'LG HT306SU-A2',
        'firmware_reference_sha256_from_user_attachment': FIRMWARE_SHA256,
        'note': 'External Windows tool. No access to LG internals or firmware changes.',
    })
    return path


def current_session(create=True):
    if ACTIVE.exists():
        ident = ACTIVE.read_text(encoding='utf-8').strip()
        if ident and (SESSIONS / ident).is_dir() and '/' not in ident and '\\' not in ident:
            return SESSIONS / ident
    if create:
        return new_session()
    raise RuntimeError('No session has been started.')


def snapshot():
    result = {'tool_version': VERSION, 'taken_at_utc': now(), 'drive_root': str(BASE),
              'note': 'Dedicated flash drive only. Windows read the drive; the LG did not generate these data.',
              'files': [], 'errors': []}
    count = 0
    for folder, dirs, names in os.walk(BASE, topdown=True, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_FOLDERS and not d.startswith('.'))
        for name in sorted(names):
            if name.startswith('.') or name.startswith('LG_USB_SCOUT_RETORNO_'):
                continue
            path = Path(folder) / name
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                rel = path.relative_to(BASE).as_posix()
                if count >= MAX_FILES:
                    result['errors'].append('The 5,000-file limit was exceeded: inventory is incomplete.')
                    return result
                stat = path.stat()
                item = {'path': rel, 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
                if stat.st_size <= MAX_HASH_BYTES:
                    item['sha256'] = sha(path)
                result['files'].append(item)
                count += 1
            except (OSError, PermissionError) as e:
                result['errors'].append(f'{name}: {e}')
    return result


def compare(before, after):
    a = {x['path']: x for x in before.get('files', [])}
    b = {x['path']: x for x in after.get('files', [])}
    def changed(x, y):
        return x['size'] != y['size'] or (x.get('sha256') and y.get('sha256') and x['sha256'] != y['sha256'])
    return {
        'new': [b[k] for k in sorted(b.keys() - a.keys())],
        'removed': [a[k] for k in sorted(a.keys() - b.keys())],
        'modified': [{'before': a[k], 'after': b[k]} for k in sorted(a.keys() & b.keys()) if changed(a[k], b[k])]
    }


def take_snapshot(stage):
    if stage not in ('antes', 'depois'):
        raise ValueError('Invalid stage')
    path = current_session()
    data = snapshot()
    atomic_json(path / f'inventario_{stage}.json', data)
    if stage == 'depois':
        before = read_json(path / 'inventario_antes.json')
        if before:
            atomic_json(path / 'diferencas.json', compare(before, data))
    return data


def add_observation(test, seen, heard, note):
    path = current_session()
    record = {'at_utc': now(), 'test': str(test)[:150],
              'display_or_tv': str(seen)[:4000], 'audio': str(heard)[:4000],
              'notes': str(note)[:8000], 'source': 'human-entered observation, not telemetry'}
    with (path / 'observacoes.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
    return record


def attach_file(source):
    src = Path(source).resolve()
    if not src.is_file():
        raise FileNotFoundError(src)
    size = src.stat().st_size
    if size > MAX_EVIDENCE_BYTES:
        raise ValueError('Evidence exceeds 150 MB; choose a smaller file.')
    dst_dir = current_session() / 'evidencias'
    dst_dir.mkdir(parents=True, exist_ok=True)
    dest = dst_dir / (uuid.uuid4().hex[:8] + '-' + src.name.replace('\\', '_').replace('/', '_'))
    shutil.copy2(src, dest)
    return dest


def summary():
    s = current_session()
    obs = []
    if (s / 'observacoes.jsonl').exists():
        for line in (s / 'observacoes.jsonl').read_text(encoding='utf-8').splitlines():
            try: obs.append(json.loads(line))
            except json.JSONDecodeError: pass
    return {'created_at_utc': now(), 'tool': 'LG USB Scout', 'version': VERSION,
            'device': 'LG HT306SU-A2', 'session': s.name, 'media': verify_media(),
            'observations': obs, 'diff': read_json(s / 'diferencas.json', {}),
            'interpretation_limits': [
                'The LG does not execute this program; it runs only on the notebook.',
                'File changes do not demonstrate RAM/EEPROM access or internal commands.',
                'No changes to USB files are normal and do not mean that the tests failed.',
                'Human-entered observations are not instrument measurements.',
                'No code, firmware, or update is sent to the home theater.'
            ]}


def export_bundle():
    s = current_session()
    atomic_json(s / 'RESUMO_PARA_CHATGPT.json', summary())
    out = BASE / ('LG_USB_SCOUT_RETORNO_' + s.name + '.zip')
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in s.rglob('*'):
            if p.is_file():
                z.write(p, Path('sessao') / p.relative_to(s))
    return out



def capture_webcam():
    """One user-triggered frame from laptop camera; requires optional opencv-python."""
    try:
        import cv2
    except ImportError as e:
        raise RuntimeError('To use the webcam, install on the notebook: py -3 -m pip install opencv-python') from e
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY)
    try:
        if not cam.isOpened():
            raise RuntimeError('Could not open webcam 0. Check Windows permissions.')
        frame = None
        for _ in range(12):
            success, candidate = cam.read()
            if success: frame = candidate
        if frame is None:
            raise RuntimeError('The webcam did not return any frames.')
        dest = current_session() / 'evidencias' / ('WEBCAM_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S') + '.jpg')
        dest.parent.mkdir(exist_ok=True, parents=True)
        if not cv2.imwrite(str(dest), frame):
            raise RuntimeError('Could not save the webcam image.')
        return dest
    finally:
        cam.release()


def record_microphone(seconds=5):
    """5 seconds; explicit user click; optional sounddevice + numpy."""
    try:
        import sounddevice as sd
    except ImportError as e:
        raise RuntimeError('To use the microphone, install on the notebook: py -3 -m pip install sounddevice numpy') from e
    import wave
    duration = int(seconds)
    if duration < 1 or duration > 30:
        raise ValueError('Invalid duration')
    rate = 16000
    audio = sd.rec(int(duration * rate), samplerate=rate, channels=1, dtype='int16')
    sd.wait()
    dest = current_session() / 'evidencias' / ('MIC_' + dt.datetime.now().strftime('%Y%m%d_%H%M%S') + '.wav')
    dest.parent.mkdir(exist_ok=True, parents=True)
    with wave.open(str(dest), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(audio.tobytes())
    return dest


def local_ollama(model='llama3.2:3b'):
    # Explicit opt-in, local-only, no generated code execution.
    info = summary()
    excerpt = {'observations': info['observations'][-40:], 'diff': info['diff'],
               'interpretation_limits': info['interpretation_limits']}
    instruction = ('You are an offline documentation assistant for the LG HT306SU-A2. '
        'Summarize ONLY evidence that was actually observed and suggest one next non-destructive test. '
        'Do not invent LG capabilities. Do not recommend updates, EEPROM, ROM, HEX, EPM, '
        'service codes, or a direct USB-A↔USB-A connection. '
        'Distinguish human observations from measurements. Data:\n')
    data = json.dumps({'model': model, 'prompt': instruction + json.dumps(excerpt,ensure_ascii=False),
                       'stream': False, 'options': {'temperature': 0.2}},ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=data,
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=120) as res:
        payload = json.loads(res.read(1024 * 1024).decode('utf-8'))
    answer = payload.get('response', '(no response)')[:16000]
    current_session().joinpath('ANALISE_OLLAMA_LOCAL.txt').write_text(
        'Generated by local model: ' + model + '\nThis is not GPT-6 or technical validation.\n\n' + answer,encoding='utf-8')
    return answer


def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
    root=tk.Tk()
    root.title(f'LG Reverse Lab — USB Scout {VERSION} (Windows only)')
    root.geometry('850x720')
    viewport=ttk.Frame(root)
    viewport.pack(fill='both',expand=True)
    canvas=tk.Canvas(viewport,highlightthickness=0,background=root.cget('background'))
    scrollbar=ttk.Scrollbar(viewport,orient='vertical',command=canvas.yview)
    scrollbar.pack(side='right',fill='y')
    canvas.pack(side='left',fill='both',expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)
    main=ttk.Frame(canvas,padding=16)
    content=canvas.create_window((0,0),window=main,anchor='nw')
    main.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda event:canvas.itemconfigure(content,width=event.width))
    root.bind('<MouseWheel>',lambda event:canvas.yview_scroll(-1 if event.delta>0 else 1,'units'))
    ttk.Label(main,text=f'LG Reverse Lab — USB Scout {VERSION}',font=('Segoe UI',17,'bold')).pack(anchor='w')
    ttk.Label(main,text='Runs ON THE NOTEBOOK. The LG only plays MP3/JPEG files and can record to USB when started manually.',wraplength=810).pack(anchor='w',pady=(4,10))
    ttk.Label(main,text='Use a dedicated FAT32 flash drive. Do not use ROM, EPM, or HEX files. Do not connect the LG USB-A port to the PC USB-A port.',foreground='#9c332a',wraplength=810).pack(anchor='w')
    ttk.Label(main,text=f'Program/flash drive location: {BASE}',wraplength=800).pack(anchor='w',pady=8)
    status=tk.StringVar(value='Ready. Record BEFORE, run tests on the device, then record AFTER.')
    try:
        active=current_session(create=False)
        if (active/'inventario_depois.json').is_file():
            status.set(f'Session {active.name}: AFTER inventory saved. Record your observations and create the ZIP file.')
        elif (active/'inventario_antes.json').is_file():
            status.set(f'Session {active.name}: BEFORE inventory already saved. Next: test LG_TESTES on the LG.')
        else:
            status.set(f'Session {active.name} started. Click 1. BEFORE inventory.')
    except RuntimeError:
        pass
    feedback=ttk.LabelFrame(main,text='Last action result',padding=7)
    feedback.pack(fill='x',pady=(0,6))
    ttk.Label(feedback,textvariable=status,wraplength=790,foreground='#07578a').pack(anchor='w',fill='x')

    def act(fn, ok=None, notify=False):
        try:
            result=fn()
            status.set(ok(result) if callable(ok) else (ok or str(result)[:240]))
            if notify:
                messagebox.showinfo('LG USB Scout — Done',status.get(),parent=root)
            return result
        except Exception as e:
            status.set('Error: '+str(e))
            messagebox.showerror('LG USB Scout',str(e))
            return None

    bar=ttk.Frame(main);bar.pack(fill='x',pady=8)
    ttk.Button(bar,text='New session',command=lambda:act(new_session,lambda s:f'New session started: {s.name}. Click 1. BEFORE inventory.',notify=True)).pack(side='left',padx=(0,6))
    ttk.Button(bar,text='1. BEFORE inventory',command=lambda:act(lambda:take_snapshot('antes'),lambda d:f"BEFORE inventory saved: {len(d['files'])} files, {len(d['errors'])} error(s).\nClose the program, eject the flash drive, and test the LG_TESTES folder on the LG.",notify=True)).pack(side='left',padx=6)
    def after_message(data):
        if (current_session()/'inventario_antes.json').is_file():
            return f"AFTER inventory and differences saved: {len(data['files'])} files, {len(data['errors'])} error(s). Record your observations."
        return 'AFTER inventory saved, but this session has no BEFORE inventory to compare.'
    ttk.Button(bar,text='2. AFTER inventory',command=lambda:act(lambda:take_snapshot('depois'),after_message,notify=True)).pack(side='left',padx=6)
    ttk.Button(bar,text='Verify media',command=lambda:act(verify_media,lambda rows:f'{len(rows)} test files found and read successfully.\nNext: record BEFORE, if not already saved, and test playback on the LG.',notify=True)).pack(side='left',padx=6)

    form=ttk.LabelFrame(main,text='3. Describe what you observed (do not invent telemetry)',padding=10)
    form.pack(fill='x',pady=12)
    test=tk.StringVar(value=TEST_TYPES[0])
    ttk.Label(form,text='Experiment:').grid(row=0,column=0,sticky='w')
    ttk.Combobox(form,textvariable=test,values=TEST_TYPES,state='readonly',width=53).grid(row=0,column=1,sticky='ew',padx=8,pady=3)
    seen=tk.StringVar();heard=tk.StringVar()
    ttk.Label(form,text='Display/TV:').grid(row=1,column=0,sticky='w')
    ttk.Entry(form,textvariable=seen).grid(row=1,column=1,sticky='ew',padx=8,pady=3)
    ttk.Label(form,text='Audio/speakers:').grid(row=2,column=0,sticky='w')
    ttk.Entry(form,textvariable=heard).grid(row=2,column=1,sticky='ew',padx=8,pady=3)
    ttk.Label(form,text='Notes:').grid(row=3,column=0,sticky='nw')
    notes=tk.Text(form,width=62,height=4); notes.grid(row=3,column=1,sticky='ew',padx=8,pady=3)
    form.columnconfigure(1,weight=1)
    def save_obs():
        r=act(lambda:add_observation(test.get(),seen.get(),heard.get(),notes.get('1.0','end').strip()),'Observation saved in this session.')
        if r:
            seen.set('');heard.set('');notes.delete('1.0','end')
    ttk.Button(form,text='Save observation',command=save_obs).grid(row=4,column=1,sticky='e',pady=5)

    attach=ttk.LabelFrame(main,text='4. Evidence and export for ChatGPT',padding=10)
    attach.pack(fill='x',pady=7)
    def attach_callback():
        filenames=filedialog.askopenfilenames(title='Choose photos, videos, or audio you recorded')
        for fname in filenames:
            if not act(lambda p=fname:attach_file(p)):
                return
        if filenames:status.set(f'{len(filenames)} attachment(s) copied to this session.')
    ttk.Button(attach,text='Attach photo, video, or audio',command=attach_callback).pack(side='left',padx=4)
    def do_export():
        out=act(export_bundle)
        if out:
            messagebox.showinfo('Ready to share','Send this ZIP file to ChatGPT:\n'+str(out))
    ttk.Button(attach,text='5. CREATE ZIP FOR CHATGPT',command=do_export).pack(side='left',padx=8)

    evidence_tools=ttk.Frame(main)
    evidence_tools.pack(fill='x',pady=5)
    ttk.Label(evidence_tools,text='Optional capture on the notebook (never on the LG):').pack(side='left',padx=4)
    ttk.Button(evidence_tools,text='Webcam photo',command=lambda:act(capture_webcam,'Photo saved; point the webcam at the display/TV if needed.')).pack(side='left',padx=5)
    ttk.Button(evidence_tools,text='Record microphone for 5 s',command=lambda:act(record_microphone,'Five seconds of audio saved in this session.')).pack(side='left',padx=5)

    ai=ttk.LabelFrame(main,text='Optional: LOCAL language model (Ollama installed on Windows)',padding=10)
    ai.pack(fill='x',pady=10)
    ttk.Label(ai,text='Local model:').pack(side='left')
    model=tk.StringVar(value='llama3.2:3b')
    ttk.Entry(ai,textvariable=model,width=22).pack(side='left',padx=7)
    result_box=scrolledtext.ScrolledText(main,height=3,wrap='word');result_box.pack(fill='both',expand=True,pady=5)
    def query_ai():
        r=act(lambda:local_ollama(model.get()),'Local summary saved in this session. Create the ZIP again to include it.')
        if r:
            result_box.delete('1.0','end');result_box.insert('end',r)
    ttk.Button(ai,text='Summarize with local AI',command=query_ai).pack(side='left',padx=4)
    ttk.Label(ai,text='Requires Ollama and a downloaded model; no automatic ChatGPT connection.').pack(side='left',padx=6)

    root.mainloop()


def main():
    p=argparse.ArgumentParser(description='LG USB Scout: runs on the PC, never on the home theater')
    p.add_argument('--new',action='store_true',help='start a new session')
    p.add_argument('--snapshot',choices=['before','after','antes','depois'],help='save a drive inventory before or after testing (legacy aliases: antes/depois)')
    p.add_argument('--export',action='store_true',help='export the current session as a ZIP file')
    p.add_argument('--verify',action='store_true',help='verify the five test media files')
    p.add_argument('--no-gui',action='store_true',help='do not launch the graphical interface')
    args=p.parse_args()
    if args.new: print('Session:',new_session())
    if args.verify: print(json.dumps(verify_media(),indent=2))
    if args.snapshot:
        stage={'before':'antes','after':'depois'}.get(args.snapshot,args.snapshot)
        print('Inventory:',len(take_snapshot(stage)['files']),'files')
    if args.export: print('File:',export_bundle())
    if not any((args.new,args.verify,args.snapshot,args.export,args.no_gui)):
        launch_gui()

if __name__=='__main__':
    main()
