"""Local-only UI for a fixed-image OSD editor. No device or removable-drive I/O."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit
import webbrowser

from engine import Engine, EngineError, EXPECTED_SHA256
from glyph_preview import GlyphPreview

APP = Path(__file__).resolve().parent
WORKSPACE = APP.parent
LABELS = ['Inglês', 'Coreano (inferido)', 'Chinês simplificado / DRM (inferido)',
          'Francês', 'Espanhol', 'Alemão', 'Português', 'Italiano', 'Holandês',
          'Húngaro', 'Polonês', 'Russo (inferido)', 'Sueco', 'Tcheco',
          'Grego (inferido)', 'Chinês tradicional (inferido)', 'Japonês (inferido)',
          'Persa (inferido)', 'Tailandês (inferido)', 'Vietnamita', 'Turco',
          'Indonésio', 'Português do Brasil (inferido)', 'Romeno', 'Eslovaco']


class Application:
    def __init__(self):
        self.engine = Engine(WORKSPACE)
        catalog = self.engine.catalog()
        self.lock = threading.Lock()
        self.records = {}
        for language in catalog['languages']:
            language['label'] = LABELS[language['index']]
            for rec in language['records']:
                rec['max_chars'] = rec['max_length']
                self.records[(language['index'], rec['id'])] = rec
        self.catalog = {'firmware': catalog['original'], 'languages': catalog['languages'],
                        'language_count': 25, 'records_total': 13550,
                        'preview_only': True, 'version': '0.2.1', 'encoding': catalog['encoding'],
                        'outputs_dir': str(APP / 'outputs')}
        self.fonts = GlyphPreview(WORKSPACE, self.engine.source_path.read_bytes(), EXPECTED_SHA256)

    def preview(self, payload):
        if not isinstance(payload, dict) or set(payload) != {'language', 'id', 'text'}:
            raise EngineError('Escolha idioma, texto e uma nova versão para a prévia.')
        language, ident, text = payload['language'], payload['id'], payload['text']
        if type(language) is not int or type(ident) is not int or not isinstance(text, str):
            raise EngineError('Idioma, ID ou texto inválido.')
        rec = self.records.get((language, ident))
        if rec is None:
            raise EngineError('Registro não encontrado.')
        if not rec['editable']:
            if text != rec['text']:
                raise EngineError('Este registro pode ser consultado; a edição não está disponível.')
            image = '/api/image?' + urlencode({'language': language, 'id': ident})
            width = self.fonts.compose(language, ident).width
            return {'before': rec['text'], 'text': rec['text'], 'stored_text': rec['text'],
                    'max_chars': rec['max_chars'], 'padding': 0, 'read_only': True,
                    'unchanged': True, 'before_width': width, 'after_width': width,
                    'layout_warning': '', 'original_image': image, 'edited_image': image}
        unchanged = text == rec['text'] or text == rec['text'].rstrip(' ')
        if unchanged:
            stored = rec['raw_text']
        else:
            stored = self.engine.prepare_edit(payload)['stored_text']
        before = self.fonts.compose(language, ident)
        after = self.fonts.compose(language, ident, stored)
        query = {'language': language, 'id': ident}
        return {'before': rec['text'], 'text': text, 'stored_text': stored,
                'stored_display_text': stored.replace('@', ' '),
                'max_chars': rec['max_chars'], 'padding': len(stored) - len(text),
                'unchanged': unchanged, 'before_width': before.width, 'after_width': after.width,
                'layout_warning': 'Texto mais largo que o original; confira o espaço no menu.'
                                  if after.width > before.width else '',
                'original_image': '/api/image?' + urlencode(query),
                'edited_image': '/api/image?' + urlencode({**query, 'text': text})}

    def output_links(self, result):
        result = dict(result)
        result['size'] = self.engine.source_path.stat().st_size
        result['download_url'] = '/outputs/' + quote(result['name'])
        result['manifest_url'] = '/outputs/' + quote(Path(result['manifest_path']).name)
        result['restore_url'] = '/outputs/' + quote(Path(result['restore_manifest_path']).name)
        return result

    def outputs(self):
        result = []
        for path in sorted(self.engine.outputs_dir.glob('*.manifest.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            if path.is_symlink():
                continue
            try:
                manifest = json.loads(path.read_text(encoding='utf-8'))
                result.append(self.output_links({**manifest, 'restore_manifest_path':
                              str(self.engine.outputs_dir / manifest['restore_manifest'])}))
            except (OSError, ValueError, KeyError):
                continue
        return {'outputs': result[:30]}


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def local_request(self):
            allowed = {'127.0.0.1', 'localhost'}
            try:
                host = urlsplit('http://' + self.headers.get('Host', '')).hostname
                origin = self.headers.get('Origin')
                if host not in allowed:
                    raise ValueError()
                if origin:
                    parsed = urlsplit(origin)
                    if (parsed.scheme != 'http' or parsed.hostname not in allowed or
                            parsed.port != self.server.server_port):
                        raise ValueError()
            except ValueError:
                self.respond(403, {'error': 'Abra o editor pelo endereço local exibido no iniciador.'})
                return False
            return True

        def respond(self, status, body, content_type='application/json; charset=utf-8', attachment=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            if isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            if attachment:
                self.send_header('Content-Disposition', f'attachment; filename="{attachment}"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.local_request():
                return
            parsed = urlsplit(self.path)
            try:
                if parsed.path in ('/', '/index.html'):
                    self.respond(200, (APP / 'index.html').read_bytes(), 'text/html; charset=utf-8')
                elif parsed.path in ('/experimento', '/experimento/'):
                    self.respond(200, (WORKSPACE / 'AUDITORIA_ROM' / 'rotina_lg_lab' / 'execucao.html').read_bytes(), 'text/html; charset=utf-8')
                elif parsed.path == '/api/catalog':
                    self.respond(200, app.catalog)
                elif parsed.path == '/api/health':
                    self.respond(200, {'app': 'lg-reverse-lab-editor', 'version': '0.2.1', 'ready': True})
                elif parsed.path == '/api/outputs':
                    self.respond(200, app.outputs())
                elif parsed.path == '/api/image':
                    query = parse_qs(parsed.query, keep_blank_values=True)
                    language, ident = int(query['language'][0]), int(query['id'][0])
                    if (language, ident) not in app.records:
                        raise EngineError('Registro não encontrado.')
                    text = query.get('text', [None])[0]
                    if text is not None:
                        prepared = app.preview({'language': language, 'id': ident, 'text': text})
                        text = None if prepared.get('read_only') else prepared['stored_text']
                    self.respond(200, app.fonts.png(language, ident, text), 'image/png')
                elif parsed.path.startswith('/outputs/'):
                    name = unquote(parsed.path[len('/outputs/'):])
                    path = (app.engine.outputs_dir / name).resolve()
                    if (Path(name).name != name or path.parent != app.engine.outputs_dir.resolve()
                            or not name.endswith(('.preview.bin', '.manifest.json', '.restore.json'))
                            or not path.is_file()):
                        self.respond(404, {'error': 'Arquivo de saída não encontrado.'})
                        return
                    kind = 'application/json' if name.endswith('.json') else 'application/octet-stream'
                    self.respond(200, path.read_bytes(), kind, name)
                elif parsed.path == '/favicon.ico':
                    self.respond(204, b'')
                else:
                    self.respond(404, {'error': 'Página não encontrada.'})
            except (EngineError, ValueError, KeyError, IndexError) as exc:
                self.respond(400, {'error': str(exc)})

        def do_POST(self):
            if not self.local_request():
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 131072 or self.headers.get_content_type() != 'application/json':
                    raise EngineError('Envie uma solicitação JSON de até 128 KB.')
                payload = json.loads(self.rfile.read(size))
                if self.path == '/api/preview':
                    self.respond(200, app.preview(payload))
                elif self.path == '/api/build':
                    if (not isinstance(payload, dict) or set(payload) != {'edits'} or
                            not isinstance(payload['edits'], list) or len(payload['edits']) > 128):
                        raise EngineError('Selecione entre uma e 128 alterações.')
                    with app.lock:
                        result = app.engine.build(payload['edits'])
                    self.respond(200, app.output_links(result))
                else:
                    self.respond(404, {'error': 'Ação não encontrada.'})
            except (EngineError, ValueError, KeyError, TypeError) as exc:
                self.respond(400, {'error': str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8780)
    parser.add_argument('--open', action='store_true', help='Abrir a interface no navegador padrão')
    args = parser.parse_args()
    app = Application()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(app))
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'LG Reverse Lab Editor 0.2.1: {url}', flush=True)
    if args.open:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
