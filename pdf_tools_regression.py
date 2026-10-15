"""Portable PDF-tool decoding contracts; no Poppler installation needed for these tests."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import verify_artifact as audit

class PDFToolsRegression(unittest.TestCase):
    def test_metadata_encoding_and_page_count(self):
        self.assertEqual(audit.EXPECTED_PROJECT_ENTRIES,{'artifact','paper'})
        metadata=b'Title: '+ '研究资料'.encode('gbk')+b'\nPages: 40\n'
        with patch.object(audit.subprocess,'run',return_value=SimpleNamespace(stdout=metadata)) as run:
            self.assertEqual(audit._pdf_pages(Path('研究资料.pdf')),40)
            args,kwargs=run.call_args
            self.assertEqual(args[0],['pdfinfo','-enc','UTF-8','研究资料.pdf'])
            self.assertNotIn('encoding',kwargs)
            self.assertFalse(kwargs.get('text',False))
            self.assertTrue(kwargs['check'])

    def test_page_text_encoding_and_range(self):
        text='References\nRené, a title\n'
        with patch.object(audit.subprocess,'run',return_value=SimpleNamespace(stdout=text.encode('utf-8'))) as run:
            self.assertEqual(audit._pdf_page_text(Path('研究资料.pdf'),34),text)
            args,kwargs=run.call_args
            self.assertEqual(args[0],['pdftotext','-enc','UTF-8','-f','34','-l','34','研究资料.pdf','-'])
            self.assertNotIn('encoding',kwargs)
            self.assertFalse(kwargs.get('text',False))
            self.assertTrue(kwargs['check'])

if __name__=='__main__':
    unittest.main()
