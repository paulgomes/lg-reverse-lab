import shutil
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import messagebox, ttk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lg_scout as scout


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class GuiFeedbackTests(unittest.TestCase):
    def test_callbacks_feedback_and_session_reopen(self):
        real_tk = tk.Tk
        popups = []
        with tempfile.TemporaryDirectory(prefix='lg_scout_gui_test_') as folder:
            base = Path(folder)
            shutil.copytree(scout.TESTS, base / 'LG_TESTES')
            paths = dict(BASE=base, LAB=base / 'LG_LAB_DADOS',
                         SESSIONS=base / 'LG_LAB_DADOS/sessoes',
                         ACTIVE=base / 'LG_LAB_DADOS/sessao_ativa.txt',
                         TESTS=base / 'LG_TESTES')

            def hidden_window(reopen=False):
                root = real_tk()
                root.withdraw()

                def check():
                    try:
                        root.update_idletasks()
                        widgets = list(descendants(root))
                        feedback = next(w for w in widgets if isinstance(w, ttk.LabelFrame)
                                        and w.cget('text') == 'Last action result')
                        label = feedback.winfo_children()[0]
                        status = lambda: root.getvar(str(label.cget('textvariable')))
                        if reopen:
                            self.assertIn(scout.current_session().name, status())
                            self.assertIn('AFTER inventory saved', status())
                            return
                        form = next(w for w in widgets if isinstance(w, ttk.LabelFrame)
                                    and str(w.cget('text')).startswith('3.'))
                        self.assertLess(feedback.winfo_y(), form.winfo_y())
                        self.assertLess(feedback.winfo_y() + feedback.winfo_reqheight(), 720)
                        self.assertTrue(any(isinstance(w, ttk.Scrollbar) for w in widgets))
                        buttons = {str(w.cget('text')): w for w in widgets if isinstance(w, ttk.Button)}
                        buttons['Verify media'].invoke()
                        self.assertIn('5 test files', popups[-1])
                        buttons['New session'].invoke()
                        session = scout.current_session(create=False)
                        buttons['1. BEFORE inventory'].invoke()
                        self.assertTrue((session / 'inventario_antes.json').is_file())
                        self.assertIn('BEFORE inventory saved', status())
                        (base / 'SIMULACAO_NO_PC.txt').write_text('Isolated test; not created by the LG.')
                        buttons['2. AFTER inventory'].invoke()
                        diff = scout.read_json(session / 'diferencas.json')
                        self.assertEqual([row['path'] for row in diff['new']], ['SIMULACAO_NO_PC.txt'])
                        buttons['5. CREATE ZIP FOR CHATGPT'].invoke()
                        self.assertTrue(list(base.glob('LG_USB_SCOUT_RETORNO_*.zip')))
                        self.assertEqual(len(popups), 5)
                    finally:
                        root.destroy()

                root.mainloop = check
                return root

            def fail_dialog(title, message, **kwargs):
                self.fail(message)

            with patch.multiple(scout, **paths), \
                 patch.object(messagebox, 'showinfo', side_effect=lambda title, message, **kw: popups.append(message)), \
                 patch.object(messagebox, 'showerror', side_effect=fail_dialog):
                with patch.object(tk, 'Tk', side_effect=hidden_window):
                    scout.launch_gui()
                active = scout.ACTIVE.read_text(encoding='utf-8')
                with patch.object(tk, 'Tk', side_effect=lambda: hidden_window(reopen=True)):
                    scout.launch_gui()
                self.assertEqual(scout.ACTIVE.read_text(encoding='utf-8'), active)


if __name__ == '__main__':
    unittest.main()
